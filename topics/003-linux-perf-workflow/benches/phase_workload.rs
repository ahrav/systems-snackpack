//! Measures whole-workload elapsed time for the deterministic phase probe.

use std::{hint::black_box, time::Instant};
use systems_snackpack_topic_003::{PhaseConfig, PhaseResult, run_alternating};

const CONFIG: PhaseConfig = PhaseConfig::new(32, 100_000, 0x1234_5678_9abc_def0);
const WARMUPS: usize = 8;
const TRIALS: usize = 31;

fn measure() -> (u128, PhaseResult) {
    let start = Instant::now();
    let result = black_box(run_alternating(black_box(CONFIG)));
    (start.elapsed().as_nanos(), result)
}

fn main() {
    for _ in 0..WARMUPS {
        black_box(measure());
    }

    let mut samples = Vec::with_capacity(TRIALS);
    let mut expected = None;
    for _ in 0..TRIALS {
        let (elapsed, result) = measure();
        assert_eq!(*expected.get_or_insert(result), result);
        samples.push(elapsed);
    }
    samples.sort_unstable();

    let median_nanoseconds = samples[TRIALS / 2];
    let iterations_per_second = CONFIG.rounds as f64 * CONFIG.iterations_per_phase as f64 * 2.0
        / (median_nanoseconds as f64 / 1_000_000_000.0);
    println!("median={median_nanoseconds} ns");
    println!("throughput={iterations_per_second:.0} inner iterations/s");
}
