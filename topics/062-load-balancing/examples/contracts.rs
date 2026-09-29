//! Print deterministic load-selection controls without wall-clock measurements.
use topic062_load_balancing::{burst_example, drain_time, shortest_completion};
fn main() {
    let (stale, reserved, pairs) = burst_example();
    println!("stale={stale:?}");
    println!("reserved={reserved:?}");
    println!("all_ordered_pairs={pairs:?}");
    println!(
        "round_robin_batch_drain={:?}",
        drain_time(&[10, 10, 10, 10], &[4, 4, 1, 1])
    );
    println!(
        "weighted_batch_drain={:?}",
        drain_time(&[16, 16, 4, 4], &[4, 4, 1, 1])
    );
    println!(
        "completion_time_choice={:?}",
        shortest_completion(&[3, 0], &[4, 1])
    );
    println!(
        "boundary=finite deterministic model; no production latency or throughput measurements"
    );
}
