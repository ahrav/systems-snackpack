//! Defines the harness-free checksum target compiled by
//! `cargo bench --workspace --no-run`.
//!
//! The workspace gate checks compilation only. Running this target traverses
//! an 8 MiB vector eight times without reporting elapsed time or samples.

use advanced_benchmarking_methodology::checksum;
use std::hint::black_box;

fn main() {
    let words = vec![0x9e37_79b9_7f4a_7c15u64; 1024 * 1024];
    for _ in 0..8 {
        black_box(checksum(black_box(&words)));
    }
}
