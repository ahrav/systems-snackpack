//! Run stdin oracle batches or timed count-maintenance workloads.
use incremental_computation::{Method, View};
use std::io::{self, BufRead};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args[1] == "check" {
        let n: usize = args[2].parse().unwrap();
        let mut delta = View::new(vec![0; n], vec![0; n]).unwrap();
        let mut full = delta.clone();
        for line in io::stdin().lock().lines() {
            let line = line.unwrap();
            let words: Vec<i64> = line
                .split_whitespace()
                .map(|s| s.parse().unwrap())
                .collect();
            assert_eq!(words.len() % 3, 0);
            let batch: Vec<_> = words
                .chunks(3)
                .map(|x| (x[0] as usize, x[1], x[2]))
                .collect();
            let a = delta.apply(&batch, Method::Delta);
            let b = full.apply(&batch, Method::Recompute);
            assert_eq!(a, b);
            assert_eq!(delta, full);
            println!("{} {}", if a.is_ok() { "ok" } else { "err" }, delta.total());
        }
        return;
    }
    let method = match args[1].as_str() {
        "delta" => Method::Delta,
        "recompute" => Method::Recompute,
        _ => panic!("method"),
    };
    let n: usize = args[2].parse().unwrap();
    let k: usize = args[3].parse().unwrap();
    let rounds: usize = args[4].parse().unwrap();
    assert!(k <= n);
    let mut view = View::new(vec![2; n], vec![3; n]).unwrap();
    let plus: Vec<_> = (0..k).map(|i| (i, 1, -1)).collect();
    let minus: Vec<_> = (0..k).map(|i| (i, -1, 1)).collect();
    let start = Instant::now();
    let mut checksum = 0i128;
    for round in 0..rounds {
        let batch = if round % 2 == 0 { &plus } else { &minus };
        checksum += std::hint::black_box(view.apply(std::hint::black_box(batch), method).unwrap());
    }
    let ns = start.elapsed().as_nanos();
    assert_eq!(checksum, (n as i128) * 6 * (rounds as i128));
    println!(
        "{{\"ns_per_batch\":{},\"checksum\":{checksum}}}",
        ns as f64 / rounds as f64
    );
}
