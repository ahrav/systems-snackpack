//! Fresh-process steady-loop cost probe for selected atomic operation shapes.

use std::env;
use std::hint::black_box;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

#[repr(align(128))]
struct AlignedAtomic(AtomicU64);

fn run(operation: &str, cell: &AtomicU64, iterations: u64) -> u64 {
    match operation {
        "store_relaxed" => {
            for value in 0..iterations {
                cell.store(value, Ordering::Relaxed);
            }
            cell.load(Ordering::Relaxed)
        }
        "store_release" => {
            for value in 0..iterations {
                cell.store(value, Ordering::Release);
            }
            cell.load(Ordering::Relaxed)
        }
        "store_seqcst" => {
            for value in 0..iterations {
                cell.store(value, Ordering::SeqCst);
            }
            cell.load(Ordering::Relaxed)
        }
        "fetch_add_relaxed" => {
            let mut checksum = 0;
            for _ in 0..iterations {
                checksum ^= cell.fetch_add(1, Ordering::Relaxed);
            }
            checksum ^ cell.load(Ordering::Relaxed)
        }
        "fetch_add_seqcst" => {
            let mut checksum = 0;
            for _ in 0..iterations {
                checksum ^= cell.fetch_add(1, Ordering::SeqCst);
            }
            checksum ^ cell.load(Ordering::Relaxed)
        }
        _ => panic!("unknown operation: {operation}"),
    }
}

fn main() {
    let main_enter = Instant::now();
    let mut args = env::args().skip(1);
    let operation = args.next().expect("usage: atomic-cost OP ITERATIONS");
    let iterations = args
        .next()
        .expect("usage: atomic-cost OP ITERATIONS")
        .parse::<u64>()
        .expect("ITERATIONS must be an integer");
    assert!(iterations > 0, "ITERATIONS must be nonzero");

    let cell = AlignedAtomic(AtomicU64::new(0));
    let setup_ns = main_enter.elapsed().as_nanos();
    let warmup_iterations = iterations.min(1_000_000);
    let warmup_start = Instant::now();
    black_box(run(&operation, black_box(&cell.0), warmup_iterations));
    let warmup_ns = warmup_start.elapsed().as_nanos();
    cell.0.store(0, Ordering::Relaxed);

    let start = Instant::now();
    let checksum = black_box(run(&operation, black_box(&cell.0), iterations));
    let elapsed_ns = start.elapsed().as_nanos();
    println!(
        "operation={operation} iterations={iterations} setup_ns={setup_ns} \
         warmup_iterations={warmup_iterations} warmup_ns={warmup_ns} \
         elapsed_ns={elapsed_ns} ns_per_operation={:.9} checksum={checksum}",
        elapsed_ns as f64 / iterations as f64
    );
}
