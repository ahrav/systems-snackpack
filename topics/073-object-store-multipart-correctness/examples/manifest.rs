//! Fresh-process benchmark of complete receipt normalization including teardown.
use multipart_correctness::{Candidate, Receipt, manifest};
use std::{hint::black_box, time::Instant};

fn main() {
    let a: Vec<_> = std::env::args().collect();
    assert_eq!(
        a.len(),
        5,
        "manifest <sort|tree|slots> <count> <ordered|reverse|shuffle> <copies>"
    );
    let c = match a[1].as_str() {
        "sort" => Candidate::Sort,
        "tree" => Candidate::Tree,
        "slots" => Candidate::Slots,
        _ => panic!("candidate"),
    };
    let n: usize = a[2].parse().unwrap();
    let copies: usize = a[4].parse().unwrap();
    assert!((1..=10_000).contains(&n) && (1..=4).contains(&copies));
    let oracle: Vec<_> = (1..=n)
        .map(|number| Receipt {
            number,
            token: number as u64 * 7919,
        })
        .collect();
    let mut rows = oracle.repeat(copies);
    match a[3].as_str() {
        "ordered" => rows.sort_by_key(|r| r.number),
        "reverse" => rows.sort_by_key(|r| std::cmp::Reverse(r.number)),
        "shuffle" => {
            let mut x = 73u64;
            for i in (1..rows.len()).rev() {
                x ^= x << 13;
                x ^= x >> 7;
                x ^= x << 17;
                rows.swap(i, x as usize % (i + 1));
            }
        }
        _ => panic!("order"),
    }
    assert_eq!(manifest(c, n, &rows).unwrap(), oracle);
    let iterations = (2_000_000 / rows.len()).clamp(20, 50_000);
    for _ in 0..20 {
        black_box(manifest(c, n, black_box(&rows)).unwrap());
    }
    let start = Instant::now();
    for _ in 0..iterations {
        black_box(manifest(c, n, black_box(&rows)).unwrap());
    }
    let ns = start.elapsed().as_nanos() as f64 / iterations as f64;
    println!(
        "{},{},{},{},{},{:.3}",
        a[1], n, a[3], copies, iterations, ns
    );
}
