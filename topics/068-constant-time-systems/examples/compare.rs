//! Warm resident equality comparison; setup and oracle are outside the timer.
use constant_time_systems::{early, reviewed, xor};
use std::{hint::black_box, time::Instant};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let candidate = &args[1];
    let n: usize = args[2].parse().unwrap();
    let pattern = &args[3];
    assert!(n > 0);
    let f = match candidate.as_str() {
        "early" => early,
        "xor" => xor,
        "subtle" => reviewed,
        _ => panic!("candidate"),
    };
    let a: Vec<u8> = (0..n).map(|i| (i * 17) as u8).collect();
    let mut b = a.clone();
    match pattern.as_str() {
        "first" => b[0] ^= 1,
        "last" => b[n - 1] ^= 1,
        "equal" => (),
        _ => panic!("pattern"),
    }
    assert_eq!(f(&a, &b), a == b);
    // First invocation has already run for correctness. This is a warm, resident test.
    let run = |reps: u64| {
        let start = Instant::now();
        let mut sum = 0u64;
        for _ in 0..reps {
            sum += u64::from(black_box(f(black_box(&a), black_box(&b))));
        }
        let ns = start.elapsed().as_nanos();
        assert_eq!(sum, if pattern == "equal" { reps } else { 0 });
        ns
    };
    let mut reps = 1u64;
    while run(reps) < 5_000_000 {
        reps *= 2;
    }
    let ns = run(reps);
    println!(
        "{{\"candidate\":\"{candidate}\",\"n\":{n},\"pattern\":\"{pattern}\",\"reps\":{reps},\"elapsed_ns\":{ns},\"ns_call\":{}}}",
        ns as f64 / reps as f64
    );
}
