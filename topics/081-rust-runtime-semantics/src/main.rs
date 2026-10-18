//! Controlled process benchmark. Allocation and output are outside the timed loop.
use std::{hint::black_box, time::Instant};
use topic081_rust_runtime::*;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 6, "variant policy length repetitions seed");
    let variant = args[1].as_str();
    let policy = args[2].as_str();
    let n: usize = args[3].parse().unwrap();
    let reps: u64 = args[4].parse().unwrap();
    let seed: u64 = args[5].parse().unwrap();
    assert!(reps > 0 && n <= 1_048_576);
    assert!(matches!(policy, "add" | "mix"));
    let xs = data(n, seed);
    let ys = data(n, seed.wrapping_add(17));
    let k = black_box(7);
    let add = Add(k);
    let mix = Mix(k);
    let choice = if policy == "add" {
        Choice::Add(Add(k))
    } else {
        Choice::Mix(Mix(k))
    };
    let dyn_policy: &dyn Policy = if policy == "add" { &add } else { &mix };
    let dyn_policy = black_box(dyn_policy);
    let choice = black_box(&choice);
    let start = Instant::now();
    let mut checksum = 0u64;
    // Select a loop once. Every iteration exposes runtime input and consumes the result.
    macro_rules! run {
        ($f:expr) => {
            for _ in 0..reps {
                checksum = checksum.wrapping_add(black_box($f));
            }
        };
    }
    match variant {
        "generic" => {
            if policy == "add" {
                run!(generic(black_box(&add), black_box(&xs)))
            } else {
                run!(generic(black_box(&mix), black_box(&xs)))
            }
        }
        "enum" => run!(enumerated(choice, black_box(&xs))),
        "dyn-item" => run!(dyn_item(dyn_policy, black_box(&xs))),
        "dyn-batch" => run!(dyn_batch(dyn_policy, black_box(&xs))),
        "index" => run!(dot_index(black_box(&xs), black_box(&ys))),
        "zip" => run!(dot_zip(black_box(&xs), black_box(&ys))),
        _ => panic!("unknown variant"),
    }
    let ns = start.elapsed().as_nanos();
    println!("{variant},{policy},{n},{reps},{seed},{checksum},{ns}");
}
