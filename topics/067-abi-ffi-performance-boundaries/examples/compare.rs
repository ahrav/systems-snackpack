//! One independent benchmark process; checks all candidates before timing one.
use std::{hint::black_box, time::Instant};
use topic_067_abi_ffi_performance_boundaries::{Candidate, input, oracle, run};
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 4, "usage: compare CANDIDATE LEN ROUNDS");
    let candidate = Candidate::parse(&args[1]).expect("candidate");
    let n: usize = args[2].parse().unwrap();
    let rounds: u32 = args[3].parse().unwrap();
    let setup = Instant::now();
    let xs = input(n);
    let setup_ns = setup.elapsed().as_nanos();
    let expected = oracle(&xs, rounds);
    for c in [
        Candidate::Rust,
        Candidate::Scalar,
        Candidate::Chunk256,
        Candidate::Batch,
        Candidate::Copy,
    ] {
        assert_eq!(run(c, &xs, rounds), expected);
    }
    let start = Instant::now();
    assert_eq!(
        black_box(run(black_box(candidate), black_box(&xs), black_box(rounds))),
        expected
    );
    let first_after_check_ns = start.elapsed().as_nanos();
    // Calibration doubles work until >=10ms, then fixes the timed iteration count.
    let mut iterations = 1_u64;
    loop {
        let start = Instant::now();
        for _ in 0..iterations {
            black_box(run(black_box(candidate), black_box(&xs), black_box(rounds)));
        }
        if start.elapsed().as_millis() >= 10 {
            break;
        }
        iterations = iterations.checked_mul(2).expect("calibration overflow");
    }
    let start = Instant::now();
    let mut check = 0_u64;
    for _ in 0..iterations {
        check = check.wrapping_add(black_box(run(
            black_box(candidate),
            black_box(&xs),
            black_box(rounds),
        )));
    }
    let elapsed = start.elapsed().as_nanos();
    assert_eq!(check, expected.wrapping_mul(iterations));
    println!(
        "{{\"candidate\":\"{}\",\"n\":{n},\"rounds\":{rounds},\"iterations\":{iterations},\"elapsed_ns\":{elapsed},\"ns_request\":{},\"setup_ns\":{setup_ns},\"first_after_check_ns\":{first_after_check_ns},\"checksum\":{expected}}}",
        args[1],
        elapsed as f64 / iterations as f64
    );
}
