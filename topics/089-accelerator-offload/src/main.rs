//! Run model cases, oracle fixtures, and warm-buffer CPU measurements.

use accelerator_offload::{element_major, round_major, schedule};
use std::{hint::black_box, time::Instant};

fn transform(mode: &str, input: &[u32], output: &mut [u32], rounds: u32) {
    match mode {
        "element" => element_major(input, output, rounds),
        "round" => round_major(input, output, rounds),
        _ => panic!("mode must be element or round"),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("model-grid") => {
            println!("jobs,slots,h,k,d,total");
            for jobs in 0..=8 {
                for slots in 1..=4 {
                    for h in 0..=4 {
                        for k in 0..=4 {
                            for d in 0..=4 {
                                let rows = schedule(jobs, slots, [h, k, d]).unwrap();
                                let total = rows.last().map_or(0, |b| b.end[2]);
                                println!("{jobs},{slots},{h},{k},{d},{total}");
                            }
                        }
                    }
                }
            }
        }
        Some(action @ ("values" | "bench")) => {
            let mode = &args[2];
            let n: usize = args[3].parse().unwrap();
            let rounds: u32 = args[4].parse().unwrap();
            let input: Vec<u32> = (0..n)
                .map(|i| (i as u32).wrapping_mul(2_654_435_761))
                .collect();
            let mut output = vec![0; n];
            transform(mode, &input, &mut output, rounds);
            if action == "values" {
                for value in output {
                    println!("{value}");
                }
                return;
            }
            let reps: u32 = args[5].parse().unwrap();
            assert!(reps > 0);
            let start = Instant::now();
            for _ in 0..reps {
                transform(
                    black_box(mode),
                    black_box(&input),
                    black_box(&mut output),
                    black_box(rounds),
                );
                black_box(&output);
            }
            let elapsed = start.elapsed().as_nanos();
            let checksum: u64 = output.iter().map(|&v| u64::from(v)).sum();
            println!("{mode},{n},{rounds},{reps},{elapsed},{checksum}");
        }
        _ => panic!(
            "usage: accelerator-offload model-grid | values MODE N ROUNDS | bench MODE N ROUNDS REPS"
        ),
    }
}
