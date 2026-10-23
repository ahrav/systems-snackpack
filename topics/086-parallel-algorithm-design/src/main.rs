//! Command-line correctness and complete-operation timing probe.
use parallel_algorithm_design::{local_add, serial, totals_rescan};
use std::{
    hint::black_box,
    io::{self, BufRead},
    time::Instant,
};

fn run(variant: &str, input: &[u64], out: &mut [u64], workers: usize) -> u64 {
    assert!(workers > 0);
    match variant {
        "serial" => serial(input, out),
        "local" => local_add(input, out, workers),
        "rescan" => totals_rescan(input, out, workers),
        _ => panic!("unknown variant: {variant}"),
    }
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    match args.get(1).map(String::as_str).unwrap_or("demo") {
        "demo" => {
            let input = [3, 1, 4, 1, 5, 9, 2, 6];
            for variant in ["serial", "local", "rescan"] {
                let mut out = [0; 8];
                let total = run(variant, &input, &mut out, 4);
                assert_eq!(out, [0, 3, 4, 8, 9, 14, 23, 25]);
                println!("{variant}: {out:?}; total={total}");
            }
        }
        "oracle" => {
            for line in io::stdin().lock().lines() {
                let line = line.unwrap();
                let mut parts = line.split_whitespace();
                let variant = parts.next().unwrap();
                let workers = parts.next().unwrap().parse().unwrap();
                let input: Vec<u64> = parts.map(|s| s.parse().unwrap()).collect();
                let mut out = vec![0; input.len()];
                let total = run(variant, &input, &mut out, workers);
                println!(
                    "{total};{}",
                    out.iter().map(u64::to_string).collect::<Vec<_>>().join(",")
                );
            }
        }
        "bench" => {
            assert_eq!(args.len(), 6, "bench VARIANT N WORKERS REPEATS");
            let variant = &args[2];
            let n: usize = args[3].parse().unwrap();
            let workers = args[4].parse().unwrap();
            let repeats: usize = args[5].parse().unwrap();
            assert!((1..=1 << 24).contains(&n) && repeats > 0);
            let input: Vec<u64> = (1..=n as u64).collect();
            let mut out = vec![0; n];
            let expected_total = (n as u128 * (n as u128 + 1) / 2) as u64;
            for _ in 0..2 {
                assert_eq!(run(variant, &input, &mut out, workers), expected_total);
            }
            let start = Instant::now();
            let mut total = 0;
            for _ in 0..repeats {
                total = black_box(run(
                    variant,
                    black_box(&input),
                    black_box(&mut out),
                    workers,
                ));
                black_box(&out);
            }
            let ns = start.elapsed().as_nanos() as f64 / repeats as f64;
            assert_eq!(total, expected_total);
            // Closed-form oracle, independent of scan recurrence and chunking.
            for (i, &value) in out.iter().enumerate() {
                assert_eq!(value, (i as u128 * (i as u128 + 1) / 2) as u64);
            }
            println!("{variant},{n},{workers},{repeats},{ns:.3},{total}");
        }
        _ => panic!("expected demo, oracle, or bench"),
    }
}
