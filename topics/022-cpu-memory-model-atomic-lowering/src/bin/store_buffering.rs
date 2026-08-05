//! Bounded Linux store-buffering observation with explicit thread affinity.

use std::env;
use std::hint::spin_loop;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;
use std::time::Instant;

const STOP: usize = usize::MAX;

#[repr(align(128))]
struct PaddedAtomic(AtomicUsize);

struct State {
    x: PaddedAtomic,
    y: PaddedAtomic,
    epoch: PaddedAtomic,
    done: PaddedAtomic,
    ready: PaddedAtomic,
    left_result: PaddedAtomic,
    right_result: PaddedAtomic,
}

impl State {
    fn new() -> Self {
        Self {
            x: PaddedAtomic(AtomicUsize::new(0)),
            y: PaddedAtomic(AtomicUsize::new(0)),
            epoch: PaddedAtomic(AtomicUsize::new(0)),
            done: PaddedAtomic(AtomicUsize::new(0)),
            ready: PaddedAtomic(AtomicUsize::new(0)),
            left_result: PaddedAtomic(AtomicUsize::new(2)),
            right_result: PaddedAtomic(AtomicUsize::new(2)),
        }
    }
}

#[cfg(target_os = "linux")]
#[repr(C)]
struct CpuSet {
    words: [usize; 1024 / (8 * std::mem::size_of::<usize>())],
}

#[cfg(target_os = "linux")]
unsafe extern "C" {
    fn sched_setaffinity(pid: i32, cpusetsize: usize, mask: *const CpuSet) -> i32;
}

#[cfg(target_os = "linux")]
fn pin_to(cpu: usize) {
    assert!(cpu < 1024, "CPU id exceeds the fixed affinity mask");
    let mut set = CpuSet {
        words: [0; 1024 / (8 * std::mem::size_of::<usize>())],
    };
    let word_bits = 8 * std::mem::size_of::<usize>();
    set.words[cpu / word_bits] |= 1_usize << (cpu % word_bits);
    // SAFETY: `set` is initialized, its size matches the pointer passed here,
    // and pid 0 asks Linux to update only the calling thread.
    let result = unsafe { sched_setaffinity(0, std::mem::size_of::<CpuSet>(), &set) };
    assert_eq!(
        result,
        0,
        "sched_setaffinity failed: {}",
        std::io::Error::last_os_error()
    );
}

#[cfg(not(target_os = "linux"))]
fn pin_to(cpu: usize) {
    // The reported CPU placement would be a lie on platforms where this
    // process cannot set thread affinity; fail fast instead of silently
    // measuring an unpinned schedule.
    let _ = cpu;
    panic!("thread pinning is only supported on Linux; refusing to run unpinned");
}

#[inline(always)]
fn store_then_load<const MODE: u8>(ours: &AtomicUsize, theirs: &AtomicUsize) -> usize {
    match MODE {
        0 => {
            ours.store(1, Ordering::Relaxed);
            theirs.load(Ordering::Relaxed)
        }
        1 => {
            ours.store(1, Ordering::Release);
            theirs.load(Ordering::Acquire)
        }
        _ => {
            ours.store(1, Ordering::SeqCst);
            theirs.load(Ordering::SeqCst)
        }
    }
}

fn worker<const MODE: u8>(state: Arc<State>, cpu: usize, left: bool) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        pin_to(cpu);
        state.ready.0.fetch_add(1, Ordering::Release);
        let mut seen_epoch = 0;
        loop {
            let epoch = loop {
                let value = state.epoch.0.load(Ordering::Acquire);
                if value != seen_epoch {
                    break value;
                }
                spin_loop();
            };
            if epoch == STOP {
                break;
            }
            seen_epoch = epoch;
            let observed = if left {
                store_then_load::<MODE>(&state.x.0, &state.y.0)
            } else {
                store_then_load::<MODE>(&state.y.0, &state.x.0)
            };
            if left {
                state.left_result.0.store(observed, Ordering::Relaxed);
            } else {
                state.right_result.0.store(observed, Ordering::Relaxed);
            }
            state.done.0.fetch_add(1, Ordering::Release);
        }
    })
}

fn run<const MODE: u8>(mode: &str, iterations: usize, cpus: [usize; 3]) {
    pin_to(cpus[2]);
    let state = Arc::new(State::new());
    let left = worker::<MODE>(Arc::clone(&state), cpus[0], true);
    let right = worker::<MODE>(Arc::clone(&state), cpus[1], false);
    while state.ready.0.load(Ordering::Acquire) != 2 {
        // A worker that fails thread pinning panics before incrementing
        // `ready`; fail closed instead of spinning forever. Its own panic
        // message (bad CPU id or sched_setaffinity error) is already on
        // stderr.
        assert!(
            !left.is_finished() && !right.is_finished(),
            "a worker exited before reporting ready; see its panic message above"
        );
        spin_loop();
    }

    let start = Instant::now();
    let mut counts = [0_u64; 4];
    for epoch in 1..=iterations {
        state.x.0.store(0, Ordering::Relaxed);
        state.y.0.store(0, Ordering::Relaxed);
        state.left_result.0.store(2, Ordering::Relaxed);
        state.right_result.0.store(2, Ordering::Relaxed);
        state.done.0.store(0, Ordering::Relaxed);
        state.epoch.0.store(epoch, Ordering::Release);
        while state.done.0.load(Ordering::Acquire) != 2 {
            spin_loop();
        }
        let left_result = state.left_result.0.load(Ordering::Relaxed);
        let right_result = state.right_result.0.load(Ordering::Relaxed);
        assert!(left_result <= 1 && right_result <= 1);
        counts[left_result * 2 + right_result] += 1;
    }
    let elapsed_ns = start.elapsed().as_nanos();
    state.epoch.0.store(STOP, Ordering::Release);
    left.join().expect("left worker panicked");
    right.join().expect("right worker panicked");

    println!(
        "mode={mode} iterations={iterations} cpu0={} cpu1={} coordinator_cpu={} \
         elapsed_ns={elapsed_ns} r00={} r01={} r10={} r11={} r00_rate={:.9}",
        cpus[0],
        cpus[1],
        cpus[2],
        counts[0],
        counts[1],
        counts[2],
        counts[3],
        counts[0] as f64 / iterations as f64
    );
    if MODE == 2 && counts[0] != 0 {
        eprintln!("observed an outcome forbidden by sequential consistency");
        std::process::exit(2);
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(
        args.len(),
        6,
        "usage: store-buffering MODE ITERATIONS CPU0 CPU1 COORDINATOR_CPU"
    );
    let mode = &args[1];
    let iterations = args[2].parse::<usize>().expect("invalid ITERATIONS");
    let cpus = [
        args[3].parse::<usize>().expect("invalid CPU0"),
        args[4].parse::<usize>().expect("invalid CPU1"),
        args[5].parse::<usize>().expect("invalid COORDINATOR_CPU"),
    ];
    assert!(iterations > 0 && iterations < STOP);
    assert!(cpus[0] != cpus[1] && cpus[0] != cpus[2] && cpus[1] != cpus[2]);
    match mode.as_str() {
        "relaxed" => run::<0>(mode, iterations, cpus),
        "release-acquire" => run::<1>(mode, iterations, cpus),
        "seqcst" => run::<2>(mode, iterations, cpus),
        _ => panic!("MODE must be relaxed, release-acquire, or seqcst"),
    }
}
