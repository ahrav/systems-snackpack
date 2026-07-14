//! Measures constant and runtime division chains.

use std::{hint::black_box, num::NonZeroU64, time::Instant};

use systems_snackpack_topic_004::{divide_constant_chain, divide_runtime_chain};

const ITERATIONS: u64 = 10_000_000;
const WARMUPS: usize = 6;
const TRIALS: usize = 21;
const BASE_SEED: u64 = 0x1234_5678_9abc_def0;

fn seed_for(index: usize) -> u64 {
    BASE_SEED.wrapping_add((index as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15))
}

fn measure_constant(seed: u64) -> (u64, u128) {
    let seed = black_box(seed);
    let iterations = black_box(ITERATIONS);
    let start = Instant::now();
    let result = divide_constant_chain(seed, iterations);
    let elapsed = start.elapsed().as_nanos();
    (black_box(result), elapsed)
}

fn measure_runtime(seed: u64, divisor: NonZeroU64) -> (u64, u128) {
    let seed = black_box(seed);
    let divisor = black_box(divisor);
    let iterations = black_box(ITERATIONS);
    let start = Instant::now();
    let result = divide_runtime_chain(seed, divisor, iterations);
    let elapsed = start.elapsed().as_nanos();
    (black_box(result), elapsed)
}

fn median(samples: &mut [u128]) -> u128 {
    samples.sort_unstable();
    samples[samples.len() / 2]
}

fn main() {
    let divisor = NonZeroU64::new(7).expect("seven is nonzero");

    for warmup in 0..WARMUPS {
        let seed = seed_for(warmup);
        let constant = black_box(divide_constant_chain(
            black_box(seed),
            black_box(ITERATIONS),
        ));
        let runtime = black_box(divide_runtime_chain(
            black_box(seed),
            black_box(divisor),
            black_box(ITERATIONS),
        ));
        assert_eq!(constant, runtime, "warmup={warmup}");
    }

    let mut constant_samples = Vec::with_capacity(TRIALS);
    let mut runtime_samples = Vec::with_capacity(TRIALS);

    for trial in 0..TRIALS {
        let seed = seed_for(WARMUPS + trial);
        let (constant, runtime) = if trial % 2 == 0 {
            let constant = measure_constant(seed);
            let runtime = measure_runtime(seed, divisor);
            (constant, runtime)
        } else {
            let runtime = measure_runtime(seed, divisor);
            let constant = measure_constant(seed);
            (constant, runtime)
        };

        assert_eq!(constant.0, runtime.0, "trial={trial} seed={seed:#018x}");
        constant_samples.push(constant.1);
        runtime_samples.push(runtime.1);
    }

    let constant_median = median(&mut constant_samples);
    let runtime_median = median(&mut runtime_samples);
    let constant_ns_per_iteration = constant_median as f64 / ITERATIONS as f64;
    let runtime_ns_per_iteration = runtime_median as f64 / ITERATIONS as f64;
    let runtime_over_constant = runtime_median as f64 / constant_median as f64;

    println!(
        "constant median_total_ns={constant_median} median_ns_per_iteration={constant_ns_per_iteration:.3}"
    );
    println!(
        "runtime median_total_ns={runtime_median} median_ns_per_iteration={runtime_ns_per_iteration:.3}"
    );
    println!("runtime_over_constant={runtime_over_constant:.3}");
}
