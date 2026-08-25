//! Linux probe for atomic read-modify-write false sharing.
//!
//! Two workers update distinct counters. `packed` places both counters within
//! one 128-byte region. `padded` gives each counter a 128-byte-aligned slot.
//! The executable verifies field offsets, successful pinning, beginning and
//! ending CPU IDs, and final counts. The publication runner separately verifies
//! that the selected CPUs are distinct physical cores in one package and that
//! the host reports 64-byte coherence lines.
//!
//! The timer starts after affinity setup. It includes the start barrier, the
//! increments, the ending-CPU checks, and the done barrier, but excludes worker
//! creation and joins. From the workspace root, run an x86-64 or AArch64 Linux
//! probe with:
//!
//! ```text
//! cargo run --release --package cache-coherence-false-sharing \
//!   --example cache_coherence_probe -- packed 100000 0 1
//! ```

#[cfg(all(
    target_os = "linux",
    target_pointer_width = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
))]
mod linux {
    use std::env;
    use std::io;
    use std::mem::{align_of, size_of};
    use std::process;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Arc, Barrier};
    use std::thread;
    use std::time::Instant;

    // Two 64-byte lines keep the measured layouts valid while making allocation
    // alignment and counter stride explicit in the output record.
    const SLOT_BYTES: usize = 128;
    // The FFI mask supports Linux CPU indices 0 through 1023.
    const CPU_SET_WORDS: usize = 16;

    #[repr(C)]
    #[derive(Clone, PartialEq)]
    struct CpuSet {
        bits: [u64; CPU_SET_WORDS],
    }

    unsafe extern "C" {
        fn sched_setaffinity(pid: i32, cpusetsize: usize, mask: *const CpuSet) -> i32;
        fn sched_getaffinity(pid: i32, cpusetsize: usize, mask: *mut CpuSet) -> i32;
        fn sched_getcpu() -> i32;
    }

    #[repr(C, align(128))]
    struct Packed {
        first: AtomicU64,
        second: AtomicU64,
    }

    #[repr(C, align(128))]
    struct CacheLineSlot(AtomicU64);

    #[repr(C, align(128))]
    struct Padded {
        first: CacheLineSlot,
        second: CacheLineSlot,
    }

    // Freeze every layout property used to classify a process result.
    const _: () = assert!(size_of::<AtomicU64>() == 8);
    const _: () = assert!(size_of::<Packed>() == SLOT_BYTES);
    const _: () = assert!(align_of::<Packed>() == SLOT_BYTES);
    const _: () = assert!(size_of::<CacheLineSlot>() == SLOT_BYTES);
    const _: () = assert!(align_of::<CacheLineSlot>() == SLOT_BYTES);
    const _: () = assert!(size_of::<Padded>() == 2 * SLOT_BYTES);

    #[derive(Clone)]
    enum Shared {
        Packed(Arc<Packed>),
        Padded(Arc<Padded>),
    }

    impl Shared {
        fn counter(&self, index: usize) -> &AtomicU64 {
            match (self, index) {
                (Self::Packed(value), 0) => &value.first,
                (Self::Packed(value), 1) => &value.second,
                (Self::Padded(value), 0) => &value.first.0,
                (Self::Padded(value), 1) => &value.second.0,
                _ => unreachable!("the probe has exactly two counters"),
            }
        }

        fn addresses(&self) -> (usize, usize) {
            (
                self.counter(0).as_ptr() as usize,
                self.counter(1).as_ptr() as usize,
            )
        }
    }

    #[derive(Debug)]
    struct WorkerResult {
        affinity_ok: bool,
        start_cpu: i32,
        end_cpu: i32,
    }

    fn one_cpu_set(cpu: usize) -> io::Result<CpuSet> {
        if cpu >= CPU_SET_WORDS * u64::BITS as usize {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "CPU index exceeds this probe's 1024-bit cpu_set_t model",
            ));
        }
        let mut set = CpuSet {
            bits: [0; CPU_SET_WORDS],
        };
        set.bits[cpu / u64::BITS as usize] |= 1_u64 << (cpu % u64::BITS as usize);
        Ok(set)
    }

    fn pin_to_cpu(cpu: usize) -> io::Result<()> {
        let expected = one_cpu_set(cpu)?;
        // SAFETY: `expected` is an initialized 128-byte mask that remains alive
        // for the call. This module compiles only for 64-bit Linux.
        let set_rc = unsafe { sched_setaffinity(0, size_of::<CpuSet>(), &expected) };
        if set_rc != 0 {
            return Err(io::Error::last_os_error());
        }
        let mut observed = CpuSet {
            bits: [0; CPU_SET_WORDS],
        };
        // SAFETY: `observed` is writable for `size_of::<CpuSet>()` bytes and
        // remains alive for the call.
        let get_rc = unsafe { sched_getaffinity(0, size_of::<CpuSet>(), &mut observed) };
        if get_rc != 0 {
            return Err(io::Error::last_os_error());
        }
        if observed != expected {
            return Err(io::Error::other(
                "kernel did not retain a one-CPU affinity mask",
            ));
        }
        Ok(())
    }

    fn current_cpu() -> io::Result<i32> {
        // SAFETY: `sched_getcpu` has no arguments or memory preconditions.
        let cpu = unsafe { sched_getcpu() };
        if cpu < 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(cpu)
        }
    }

    /// Runs the relaxed increments behind a named, non-inlined symbol.
    ///
    /// Its assembly establishes the emitted atomic operation, not the coherence
    /// transaction path taken at runtime.
    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) fn topic46_increment(counter: &AtomicU64, iterations: u64) {
        for _ in 0..iterations {
            counter.fetch_add(1, Ordering::Relaxed);
        }
    }

    fn parse<T: std::str::FromStr>(text: &str, what: &str) -> T {
        text.parse().unwrap_or_else(|_| {
            eprintln!("invalid {what}: {text}");
            process::exit(2);
        })
    }

    pub(super) fn run() {
        let args: Vec<String> = env::args().collect();
        if args.len() != 5 {
            eprintln!(
                "usage: {} <packed|padded> <iterations> <cpu0> <cpu1>",
                args[0]
            );
            process::exit(2);
        }
        let mode = args[1].as_str();
        let iterations: u64 = parse(&args[2], "iteration count");
        let cpu0: usize = parse(&args[3], "cpu0");
        let cpu1: usize = parse(&args[4], "cpu1");
        if cpu0 == cpu1 || iterations == 0 {
            eprintln!("CPUs must differ and iterations must be nonzero");
            process::exit(2);
        }

        let shared = match mode {
            "packed" => Shared::Packed(Arc::new(Packed {
                first: AtomicU64::new(0),
                second: AtomicU64::new(0),
            })),
            "padded" => Shared::Padded(Arc::new(Padded {
                first: CacheLineSlot(AtomicU64::new(0)),
                second: CacheLineSlot(AtomicU64::new(0)),
            })),
            _ => {
                eprintln!("mode must be packed or padded");
                process::exit(2);
            }
        };

        let (address0, address1) = shared.addresses();
        let address_delta = address1.abs_diff(address0);
        let layout_ok = address0 % SLOT_BYTES == 0
            && match mode {
                "packed" => address_delta == size_of::<AtomicU64>(),
                "padded" => address_delta == SLOT_BYTES,
                _ => false,
            };

        // Each barrier includes both workers and the coordinating main thread.
        let ready = Arc::new(Barrier::new(3));
        let start = Arc::new(Barrier::new(3));
        let done = Arc::new(Barrier::new(3));
        let mut workers = Vec::new();
        for (index, cpu) in [(0_usize, cpu0), (1_usize, cpu1)] {
            let local_shared = shared.clone();
            let local_ready = Arc::clone(&ready);
            let local_start = Arc::clone(&start);
            let local_done = Arc::clone(&done);
            workers.push(thread::spawn(move || {
                let affinity_ok = pin_to_cpu(cpu).is_ok();
                let start_cpu = current_cpu().unwrap_or(-1);
                local_ready.wait();
                local_start.wait();
                // Suppress work after a failed pin so invalid placement cannot
                // produce a timing record that appears usable.
                if affinity_ok && start_cpu == cpu as i32 {
                    topic46_increment(local_shared.counter(index), iterations);
                }
                let end_cpu = current_cpu().unwrap_or(-1);
                local_done.wait();
                WorkerResult {
                    affinity_ok,
                    start_cpu,
                    end_cpu,
                }
            }));
        }

        ready.wait();
        let timer = Instant::now();
        start.wait();
        done.wait();
        let elapsed_ns = timer.elapsed().as_nanos();
        let results: Vec<WorkerResult> = workers
            .into_iter()
            .map(|worker| {
                worker
                    .join()
                    .expect("worker panicked after synchronization")
            })
            .collect();

        let first = shared.counter(0).load(Ordering::Relaxed);
        let second = shared.counter(1).load(Ordering::Relaxed);
        let affinity_ok = results.iter().enumerate().all(|(index, result)| {
            let expected = if index == 0 { cpu0 } else { cpu1 } as i32;
            result.affinity_ok && result.start_cpu == expected && result.end_cpu == expected
        });
        let correct = first == iterations && second == iterations;

        println!(
            "{{\"mode\":\"{mode}\",\"iterations_per_thread\":{iterations},\"cpu0\":{cpu0},\"cpu1\":{cpu1},\"start_cpu0\":{},\"start_cpu1\":{},\"end_cpu0\":{},\"end_cpu1\":{},\"first\":{first},\"second\":{second},\"elapsed_ns\":{elapsed_ns},\"address0_mod_128\":{},\"address_delta\":{address_delta},\"packed_size\":{},\"padded_size\":{},\"slot_bytes\":{SLOT_BYTES},\"layout_ok\":{layout_ok},\"affinity_ok\":{affinity_ok},\"correct\":{correct}}}",
            results[0].start_cpu,
            results[1].start_cpu,
            results[0].end_cpu,
            results[1].end_cpu,
            address0 % SLOT_BYTES,
            size_of::<Packed>(),
            size_of::<Padded>(),
        );
        if !layout_ok || !affinity_ok || !correct {
            process::exit(1);
        }
    }
}

#[cfg(all(
    target_os = "linux",
    target_pointer_width = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
))]
fn main() {
    linux::run();
}

#[cfg(not(all(
    target_os = "linux",
    target_pointer_width = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
)))]
fn main() {
    println!("status=SKIP reason=probe_requires_64_bit_Linux_AArch64_or_x86_64");
}
