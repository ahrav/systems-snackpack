//! Measures only the pure arithmetic used to interpret fault observations.

use std::hint::black_box;
use std::time::Instant;

use systems_snackpack_topic_012::{Observation, amortized_ns_per_fault, faults_per_page};

fn main() {
    let observation = Observation {
        pages: 8_192,
        touch_ns: 4_000_000_000,
        minor_faults: 512,
        major_faults: 8,
        resident_before: 0,
        resident_after: 8_192,
    };
    let iterations = 5_000_000_u64;
    let start = Instant::now();
    let mut checksum = 0.0;
    for _ in 0..iterations {
        checksum += black_box(amortized_ns_per_fault(black_box(observation))).unwrap_or(0.0);
        checksum += black_box(faults_per_page(black_box(observation))).unwrap_or(0.0);
    }
    let elapsed = start.elapsed();
    println!(
        "iterations={iterations} elapsed_ns={} checksum={checksum:.3}",
        elapsed.as_nanos()
    );
}
