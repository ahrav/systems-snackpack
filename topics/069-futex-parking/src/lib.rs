//! Linux futex experiments. This is an instrumented teaching lock, not a production mutex.
//! Payloads stay atomic inside the lock so an exclusion defect cannot create a payload
//! data race. Finite checks can detect defects but do not prove exclusion or liveness.
//! Ordinary mutexes must also prove non-atomic data access.
//!
//! ```
//! assert_eq!(futex_parking::serial(2, 1), 2);
//! ```

/// Independent sequential oracle for the number of committed critical sections.
pub fn serial(threads: usize, iterations: usize) -> u64 {
    threads.checked_mul(iterations).unwrap().try_into().unwrap()
}

/// Supported Linux implementation and instrumented workload.
#[cfg(all(
    target_os = "linux",
    target_pointer_width = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
))]
pub mod linux {
    use std::ffi::{c_int, c_long};
    use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
    use std::sync::{Arc, Barrier};
    use std::time::{Duration, Instant};

    #[cfg(target_arch = "x86_64")]
    const SYS_FUTEX: c_long = 202;
    #[cfg(target_arch = "aarch64")]
    const SYS_FUTEX: c_long = 98;
    const WAIT_PRIVATE: c_int = 128;
    const WAKE_PRIVATE: c_int = 129;

    unsafe extern "C" {
        fn syscall(number: c_long, ...) -> c_long;
        fn clock_gettime(clock: c_int, out: *mut Timespec) -> c_int;
    }
    #[repr(C)]
    struct Timespec {
        sec: c_long,
        nsec: c_long,
    }

    fn cpu_ns() -> u64 {
        let mut t = Timespec { sec: 0, nsec: 0 };
        // SAFETY: valid writable timespec for the supported Linux 64-bit ABIs.
        assert_eq!(unsafe { clock_gettime(2, &mut t) }, 0);
        (t.sec as u64) * 1_000_000_000 + t.nsec as u64
    }

    fn wait(word: &AtomicU32) -> bool {
        // SAFETY: AtomicU32 provides a stable aligned 32-bit word for this call.
        // The borrow keeps it valid throughout this synchronous call. Workload Arcs
        // additionally retain it until all workers join. Timeout is null.
        let r = unsafe {
            syscall(
                SYS_FUTEX,
                word.as_ptr(),
                WAIT_PRIVATE,
                2_u32,
                std::ptr::null::<Timespec>(),
                0_usize,
                0_u32,
            )
        };
        if r == 0 {
            return false;
        }
        match std::io::Error::last_os_error().raw_os_error() {
            Some(11) => true, // EAGAIN: the compare rejected sleep.
            Some(4) => false, // EINTR: recheck the predicate.
            e => panic!("unexpected futex wait error: {e:?}"),
        }
    }
    fn wake(word: &AtomicU32, count: c_int) -> u64 {
        // SAFETY: same word lifetime/alignment contract as wait; private to this process.
        let r = unsafe {
            syscall(
                SYS_FUTEX,
                word.as_ptr(),
                WAKE_PRIVATE,
                count,
                std::ptr::null::<Timespec>(),
                0_usize,
                0_u32,
            )
        };
        assert!(r >= 0, "futex wake: {}", std::io::Error::last_os_error());
        r as u64
    }

    #[derive(Clone, Copy, Default)]
    struct Stats {
        waits: u64,
        again: u64,
        wakes: u64,
        woken: u64,
    }

    struct Lock {
        state: AtomicU32,
        policy: String,
    }
    struct Guard<'a> {
        lock: &'a Lock,
        stats: &'a mut Stats,
    }
    impl Drop for Guard<'_> {
        fn drop(&mut self) {
            if self.lock.state.swap(0, Ordering::Release) == 2 {
                self.stats.wakes += 1;
                self.stats.woken += wake(
                    &self.lock.state,
                    if self.lock.policy == "all" {
                        c_int::MAX
                    } else {
                        1
                    },
                );
            }
        }
    }
    impl Lock {
        fn acquire<'a>(&'a self, stats: &'a mut Stats) -> Guard<'a> {
            if self
                .state
                .compare_exchange(0, 1, Ordering::Acquire, Ordering::Relaxed)
                .is_ok()
            {
                return Guard { lock: self, stats };
            }
            let mut budget: u32 = if self.policy == "hybrid" { 100 } else { 0 };
            while self.policy == "spin" || budget > 0 {
                if self.state.load(Ordering::Relaxed) == 0
                    && self
                        .state
                        .compare_exchange(0, 1, Ordering::Acquire, Ordering::Relaxed)
                        .is_ok()
                {
                    return Guard { lock: self, stats };
                }
                std::hint::spin_loop();
                budget = budget.saturating_sub(1);
            }
            // A contended acquirer preserves state 2. Its eventual release must wake
            // another sleeper even if a newly arriving thread barges ahead of it.
            loop {
                if self.state.swap(2, Ordering::Acquire) == 0 {
                    return Guard { lock: self, stats };
                }
                stats.waits += 1;
                stats.again += u64::from(wait(&self.state));
            }
        }
    }

    /// A completed process interval. Syscall counts include only workload lock calls.
    pub struct Report {
        /// Wall time from releasing ready workers through joining them, in nanoseconds.
        pub wall_ns: u128,
        /// Process CPU time approximately bracketing the wall interval, in nanoseconds.
        pub cpu_ns: u64,
        /// Successful critical sections, checked against the serial oracle.
        pub operations: u64,
        /// FUTEX_WAIT attempts, not the number of actual sleeps.
        pub waits: u64,
        /// Attempts rejected with EAGAIN.
        pub again: u64,
        /// FUTEX_WAKE calls, not the number of scheduled workers.
        pub wakes: u64,
        /// Sum of successful FUTEX_WAKE return counts.
        pub woken: u64,
        /// Combined result of nontrivial critical-section arithmetic.
        pub checksum: u64,
    }

    /// Run a bounded workload with policy `spin`, `one`, `all`, or `hybrid`.
    /// `work` is the number of dependent arithmetic steps per critical section.
    /// `sleep_us` models a descheduled owner. Every worker must finish its full quota.
    /// No FIFO, starvation bound, cancellation, poisoning, robust-owner, or PI contract.
    /// Panics on invalid input, syscall errors, exclusion violations, or wrong totals.
    pub fn run(
        policy: &str,
        threads: usize,
        iterations: usize,
        work: usize,
        sleep_us: u64,
    ) -> Report {
        assert!(["spin", "one", "all", "hybrid"].contains(&policy));
        assert!((1..=64).contains(&threads) && iterations > 0 && work > 0);
        let lock = Arc::new(Lock {
            state: AtomicU32::new(0),
            policy: policy.to_owned(),
        });
        let counter = Arc::new(AtomicU64::new(0));
        let occupied = Arc::new(AtomicBool::new(false));
        let gate = Arc::new(Barrier::new(threads + 1));
        let mut handles = Vec::new();
        for _ in 0..threads {
            let (lock, counter, occupied, gate) = (
                lock.clone(),
                counter.clone(),
                occupied.clone(),
                gate.clone(),
            );
            handles.push(std::thread::spawn(move || {
                let mut stats = Stats::default();
                let mut checksum = 0_u64;
                gate.wait();
                gate.wait();
                for _ in 0..iterations {
                    let _guard = lock.acquire(&mut stats);
                    assert!(
                        !occupied.swap(true, Ordering::Relaxed),
                        "overlapping holders"
                    );
                    let n = counter.load(Ordering::Relaxed);
                    let mut x = n;
                    for _ in 0..work {
                        x = std::hint::black_box(
                            x.wrapping_mul(6364136223846793005).wrapping_add(1),
                        );
                    }
                    checksum = checksum.wrapping_add(x);
                    if sleep_us != 0 {
                        std::thread::sleep(Duration::from_micros(sleep_us));
                    }
                    counter.store(n + 1, Ordering::Relaxed);
                    occupied.store(false, Ordering::Relaxed);
                }
                (stats, checksum)
            }));
        }
        gate.wait(); // All workers have reached readiness before either clock starts.
        let cpu_start = cpu_ns();
        let start = Instant::now();
        gate.wait();
        let results: Vec<_> = handles.into_iter().map(|h| h.join().unwrap()).collect();
        let wall_ns = start.elapsed().as_nanos();
        let cpu_ns = cpu_ns() - cpu_start;
        let operations = super::serial(threads, iterations);
        assert_eq!(counter.load(Ordering::Relaxed), operations);
        let checksum = results.iter().fold(0_u64, |a, (_, v)| a.wrapping_add(*v));
        // Compare aggregate count and wrapping checksum with a sequential traversal.
        // Finite tests and a checksum can miss defects; this is not a proof.
        let expected = (0..operations).fold(0_u64, |a, mut x| {
            for _ in 0..work {
                x = x.wrapping_mul(6364136223846793005).wrapping_add(1);
            }
            a.wrapping_add(x)
        });
        assert_eq!(checksum, expected);
        Report {
            wall_ns,
            cpu_ns,
            operations,
            checksum,
            waits: results.iter().map(|(s, _)| s.waits).sum(),
            again: results.iter().map(|(s, _)| s.again).sum(),
            wakes: results.iter().map(|(s, _)| s.wakes).sum(),
            woken: results.iter().map(|(s, _)| s.woken).sum(),
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test]
        fn compare_rejects_obsolete_wait_and_wake_stores_no_permit() {
            let word = AtomicU32::new(0);
            assert_eq!(std::mem::align_of::<AtomicU32>(), 4);
            assert_eq!(wake(&word, 1), 0);
            assert!(wait(&word));
        }
        #[test]
        fn all_candidates_match_oracle() {
            for p in ["spin", "one", "all", "hybrid"] {
                for (t, n, w, s) in [(1, 1, 1, 0), (4, 2000, 1, 0), (8, 10, 9, 50)] {
                    assert_eq!(run(p, t, n, w, s).operations, super::super::serial(t, n));
                }
            }
        }
        #[test]
        fn guard_releases_on_panic() {
            let lock = Lock {
                state: AtomicU32::new(0),
                policy: "one".to_owned(),
            };
            let mut stats = Stats::default();
            let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let _guard = lock.acquire(&mut stats);
                panic!("injected");
            }));
            assert_eq!(lock.state.load(Ordering::Relaxed), 0);
            drop(lock.acquire(&mut stats));
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn serial_boundary() {
        assert_eq!(super::serial(1, 1), 1);
        assert_eq!(super::serial(0, 10), 0);
    }
}
