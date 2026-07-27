//! Exercises the block-summary analysis path 100,000 times.

use linkers_loaders_binary_layout::{block_log_contrast, summarize_log_contrasts};
use std::hint::black_box;
use std::time::Instant;

fn main() {
    let started = Instant::now();
    let mut checksum = 0.0;
    for iteration in 0..100_000 {
        let scale = 1.0 + (iteration & 7) as f64;
        let contrast = block_log_contrast(
            ['A', 'B', 'B', 'A'],
            [scale, scale * 1.01, scale * 1.01, scale],
        )
        .expect("positive balanced block");
        let estimate = summarize_log_contrasts(&[contrast; 12]).expect("twelve finite blocks");
        checksum += black_box(estimate.geometric_mean);
    }
    println!(
        "iterations=100000 elapsed_ns={} checksum={checksum:.6}",
        started.elapsed().as_nanos()
    );
}
