//! Process-level scan measurement. Setup, first scan, and warm scans are separate.
use std::hint::black_box;
use std::time::Instant;
use topic065_query_execution::{Columns, batched, dispatched, fused, morsels};

fn main() {
    let start = Instant::now();
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 6, "probe MODE ROWS MASK BATCH REPEATS");
    let n = args[2].parse().unwrap();
    let mask = args[3].parse().unwrap();
    let batch = args[4].parse().unwrap();
    let repeats: u32 = args[5].parse().unwrap();
    assert!(n > 0 && repeats > 0 && batch > 0);
    let data = Columns::generated(n);
    let expected = data.oracle(mask);
    let scan = || match args[1].as_str() {
        "row" => dispatched(black_box(&data), black_box(mask)),
        "batch" => batched(black_box(&data), black_box(mask), black_box(batch)),
        "fused" => fused(black_box(&data), black_box(mask)),
        _ => panic!("unknown mode"),
    };
    let setup_ns = start.elapsed().as_nanos();
    let first = Instant::now();
    let result = scan();
    let first_ns = first.elapsed().as_nanos();
    assert_eq!(result, expected);
    for _ in 0..2 {
        assert_eq!(scan(), expected);
    }
    let warm = Instant::now();
    for _ in 0..repeats {
        assert_eq!(black_box(scan()), expected);
    }
    let warm_ns = warm.elapsed().as_nanos();
    assert_eq!(morsels(&data, mask, 65536, 4), expected);
    println!(
        "mode={},n={n},mask={mask},batch={batch},repeats={repeats},sum={expected},setup_ns={setup_ns},first_ns={first_ns},warm_ns={warm_ns}",
        args[1]
    );
}
