//! Fixed-order smoke benchmark for the two chain widths.
//!
//! One process warms the cycle once, then runs one lane before eight lanes. The
//! output checks that both treatments execute, but supplies neither
//! process-level replication nor order balance for a performance comparison.

use memory_level_parallelism::{Cycle, walk, walk_one};
use std::hint::black_box;
use std::time::Instant;

fn main() {
    // The default 262,144 nodes occupy 16 MiB, excluding allocator metadata.
    let nodes: usize = std::env::var("TOPIC20_SMOKE_NODES")
        .map_or(1 << 18, |value| value.parse().expect("invalid node count"));
    // The default executes 4,194,304 useful link loads per treatment.
    let loads: usize = std::env::var("TOPIC20_SMOKE_LOADS")
        .map_or(1 << 22, |value| value.parse().expect("invalid load count"));
    assert!(loads > 0 && loads.is_multiple_of(8));

    // Matches `chain_probe`'s default permutation at the same node count.
    let cycle = Cycle::new(nodes, 0xd1b5_4a32_d192_ed03);
    black_box(walk_one(&cycle, cycle.start(0), cycle.node_count()));
    for lanes in [1, 8] {
        let start = Instant::now();
        let sink = black_box(walk(&cycle, lanes, loads));
        let elapsed = start.elapsed();
        println!(
            "lanes={lanes} steady_ns={} ns_per_load={:.9} sink={sink}",
            elapsed.as_nanos(),
            elapsed.as_nanos() as f64 / loads as f64
        );
    }
}
