//! Measures throughput for the Topic 1 byte-count implementations.

use std::{hint::black_box, time::Instant};
use systems_snackpack_topic_001::{count_eq_neon, count_eq_scalar, count_eq_swar_prefilter};

const BYTES: usize = 1 << 20;
const TRIALS: usize = 41;
type Counter = fn(&[u8], u8) -> usize;

fn measure(function: Counter, input: &[u8]) -> u128 {
    let start = Instant::now();
    black_box(function(black_box(input), black_box(17)));
    start.elapsed().as_nanos()
}

fn median(mut samples: Vec<u128>) -> u128 {
    samples.sort_unstable();
    samples[samples.len() / 2]
}

fn main() {
    let input: Vec<u8> = (0..BYTES).map(|index| (index % 251) as u8).collect();
    let functions = [
        ("scalar", count_eq_scalar as Counter),
        ("swar", count_eq_swar_prefilter),
        ("neon", count_eq_neon),
    ];
    let mut samples = [Vec::new(), Vec::new(), Vec::new()];

    for (_, function) in functions {
        for _ in 0..8 {
            black_box(measure(function, &input));
        }
    }

    for trial in 0..TRIALS {
        for offset in 0..functions.len() {
            let index = (trial + offset) % functions.len();
            samples[index].push(measure(functions[index].1, &input));
        }
    }

    for (index, (name, _)) in functions.iter().enumerate() {
        let elapsed = median(std::mem::take(&mut samples[index])) as f64;
        let gib_per_second = BYTES as f64 / elapsed * 1_000_000_000.0 / 1_073_741_824.0;
        println!("{name:6} {gib_per_second:8.3} GiB/s median");
    }
}
