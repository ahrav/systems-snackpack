//! One-process timing probe for one or eight load-dependency chains.
//!
//! `setup_ns` covers cycle allocation and construction. `warm_ns` covers one
//! full-cycle, one-lane traversal. `steady_ns` covers the selected treatment.
//! Each invocation supplies one process-level observation; replication and
//! order balancing require separate invocations.

use memory_level_parallelism::{Cycle, walk, walk_one};
use std::hint::black_box;
use std::time::Instant;

// 4,194,304 nodes occupy 256 MiB, excluding allocator metadata.
const DEFAULT_NODES: usize = 1 << 22;
// Each selected treatment executes 33,554,432 useful link loads.
const DEFAULT_LOADS: usize = 1 << 25;
// Holds the permutation constant for a fixed node count and target.
const DEFAULT_SEED: u64 = 0xd1b5_4a32_d192_ed03;

fn parse_value<T: std::str::FromStr>(arguments: &[String], flag: &str, default: T) -> T {
    arguments
        .windows(2)
        .find(|pair| pair[0] == flag)
        .map_or(default, |pair| {
            pair[1]
                .parse()
                .unwrap_or_else(|_| panic!("invalid value for {flag}"))
        })
}

fn main() {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    let lanes = parse_value(&arguments, "--lanes", 0usize);
    let nodes = parse_value(&arguments, "--nodes", DEFAULT_NODES);
    let loads = parse_value(&arguments, "--loads", DEFAULT_LOADS);
    let seed = parse_value(&arguments, "--seed", DEFAULT_SEED);
    assert!(lanes == 1 || lanes == 8, "--lanes must be 1 or 8");
    assert!(loads > 0 && loads.is_multiple_of(8));

    let setup_start = Instant::now();
    let cycle = Cycle::new(nodes, seed);
    let setup_ns = setup_start.elapsed().as_nanos();

    let warm_start = Instant::now();
    black_box(walk_one(&cycle, cycle.start(0), cycle.node_count()));
    let warm_ns = warm_start.elapsed().as_nanos();

    let steady_start = Instant::now();
    let sink = black_box(walk(&cycle, lanes, loads));
    let steady_ns = steady_start.elapsed().as_nanos();
    let ns_per_load = steady_ns as f64 / loads as f64;

    println!(
        "lanes={lanes} nodes={} bytes={} loads={loads} seed={seed} \
         setup_ns={setup_ns} warm_ns={warm_ns} steady_ns={steady_ns} \
         ns_per_load={ns_per_load:.9} sink={sink}",
        cycle.node_count(),
        cycle.node_bytes()
    );
}
