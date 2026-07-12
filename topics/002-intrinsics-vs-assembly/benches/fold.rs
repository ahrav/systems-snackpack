//! Measures throughput for the Topic 2 reference, intrinsic, and assembly folds.

use std::{hint::black_box, time::Instant};
use systems_snackpack_topic_002::{fold_inline_asm, fold_intrinsic, fold_reference};

const WORDS: usize = 1 << 18;
const TRIALS: usize = 41;
type Folder = fn(&[u64]) -> u32;

fn measure(function: Folder, input: &[u64]) -> u128 {
    let start = Instant::now();
    black_box(function(black_box(input)));
    start.elapsed().as_nanos()
}

fn median(mut samples: Vec<u128>) -> u128 {
    samples.sort_unstable();
    samples[samples.len() / 2]
}

fn main() {
    let input: Vec<u64> = (0..WORDS)
        .map(|index| (index as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15))
        .collect();
    assert_eq!(fold_intrinsic(&input), fold_reference(&input));
    assert_eq!(fold_inline_asm(&input), fold_reference(&input));
    let functions = [
        ("intrinsic", fold_intrinsic as Folder),
        ("asm", fold_inline_asm),
    ];
    let mut samples = [Vec::new(), Vec::new()];

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
        let gib_per_second = WORDS as f64 * 8.0 / elapsed * 1_000_000_000.0 / 1_073_741_824.0;
        println!("{name:9} {gib_per_second:8.3} GiB/s median");
    }
}
