//! Batched correctness protocol and one-process timing sample.
use std::{
    hint::black_box,
    io::{self, BufRead},
    time::Instant,
};
use topic097_query_optimization::{choose, hash_count, nested_count, workload};

fn parse(s: &str) -> Vec<u32> {
    s.split(',')
        .filter(|s| !s.is_empty())
        .map(|s| s.parse().unwrap())
        .collect()
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("oracle") {
        for line in io::stdin().lock().lines() {
            let line = line.unwrap();
            let (a, b) = line.split_once(';').unwrap();
            let (a, b) = (parse(a), parse(b));
            println!("{} {}", nested_count(&a, &b), hash_count(&a, &b));
        }
        return;
    }
    assert_eq!(args.len(), 4, "MODE nested|hash REPEATS");
    let (left, right, estimated, actual) = workload(&args[1]);
    let f = match args[2].as_str() {
        "nested" => nested_count,
        "hash" => hash_count,
        _ => panic!("unknown algorithm"),
    };
    let reps: u32 = args[3].parse().unwrap();
    assert!(reps > 0);
    let result = f(&left, &right);
    let start = Instant::now();
    for _ in 0..reps {
        black_box(f(black_box(&left), black_box(&right)));
    }
    let ns = start.elapsed().as_nanos() as f64 / reps as f64;
    println!(
        "{{\"mode\":\"{}\",\"algorithm\":\"{}\",\"ns\":{},\"count\":{},\"estimated\":{},\"actual\":{},\"estimated_plan\":\"{}\",\"joint_plan\":\"{}\"}}",
        args[1],
        args[2],
        ns,
        result,
        estimated,
        actual,
        choose(estimated, 4096.0),
        choose(actual as f64, 4096.0)
    );
}
