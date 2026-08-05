//! Controlled dependent-load chains for studying memory-level parallelism.
//!
//! [`Cycle`] stores one seeded, deterministic random cycle in 64-byte nodes.
//! [`walk_one`] exposes one serial address-dependency chain. [`walk_eight`]
//! exposes eight lane-local chains; no lane's next address depends on another
//! lane's result. Both walkers perform the requested number of useful loads.
//!
//! The chain-width curve is a workload and machine observation. It does not
//! reveal a fill-buffer, MSHR, load-queue, or memory-controller queue count.
//!
//! # Runnable probe
//!
//! ```text
//! cargo run --release --package memory-level-parallelism \
//!   --example chain_probe -- --lanes 1 --nodes 262144 --loads 1048576
//! ```

use std::hint::black_box;

/// One 64-byte-aligned, 64-byte link in a dependent traversal.
///
/// Each step loads one `next` field from a 64-byte node. On a machine with
/// 64-byte cache lines, every node begins on a separate line. The type layout
/// does not establish a machine's cache-line size or where a load completes.
#[repr(C, align(64))]
#[derive(Clone)]
pub struct Node {
    next: u32,
    padding: [u8; 60],
}

/// One deterministic random cycle with sixteen entry points.
///
/// Adjacent entry points differ by either `floor(node_count / 16)` or
/// `ceil(node_count / 16)` steps along the cycle. Distinct cursors remain
/// distinct when each advances once per round because the links form a
/// permutation.
pub struct Cycle {
    nodes: Vec<Node>,
    starts: [usize; 16],
}

impl Cycle {
    /// Builds a deterministic random cycle over `node_count` 64-byte nodes.
    ///
    /// # Panics
    ///
    /// - If `node_count` is less than 16.
    /// - If `node_count` exceeds `u32::MAX`.
    pub fn new(node_count: usize, seed: u64) -> Self {
        assert!(node_count >= 16, "a cycle needs at least sixteen nodes");
        assert!(
            u32::try_from(node_count).is_ok(),
            "node indices must fit in u32"
        );

        let mut order: Vec<u32> = (0..node_count as u32).collect();
        let mut state = seed;
        for index in (1..node_count).rev() {
            let other = splitmix64(&mut state) as usize % (index + 1);
            order.swap(index, other);
        }

        let mut nodes = vec![
            Node {
                next: 0,
                padding: [0; 60],
            };
            node_count
        ];
        for index in 0..node_count {
            nodes[order[index] as usize].next = order[(index + 1) % node_count];
        }
        let starts = std::array::from_fn(|lane| order[lane * node_count / 16] as usize);

        Self { nodes, starts }
    }

    /// Returns the number of nodes in the cycle.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Returns initialized node payload bytes, excluding allocator overhead.
    pub fn node_bytes(&self) -> usize {
        self.nodes.len() * size_of::<Node>()
    }

    /// Returns the first cursor for a lane in `[0, 16)`.
    ///
    /// # Panics
    ///
    /// - If `lane` is at least 16.
    pub fn start(&self, lane: usize) -> usize {
        self.starts[lane]
    }

    #[inline]
    fn next(&self, cursor: usize) -> usize {
        self.nodes[cursor].next as usize
    }
}

/// Advances one load-dependent cursor and returns its final index.
///
/// The exported symbol name supports inspection of the final linked image.
///
/// # Panics
///
/// - If `loads` is positive and `cursor` is not a valid node index.
#[inline(never)]
#[unsafe(export_name = "topic20_walk_one")]
pub fn walk_one(cycle: &Cycle, mut cursor: usize, loads: usize) -> usize {
    for _ in 0..loads {
        cursor = cycle.next(cursor);
    }
    black_box(cursor)
}

/// Advances eight lane-local dependency chains and returns the XOR of their
/// final indices.
///
/// `loads` names the total useful loads across all lanes. The function rejects
/// a remainder so one- and eight-lane treatments perform identical load counts.
///
/// # Panics
///
/// - If `loads` is zero or is not divisible by eight.
/// - If any initial cursor is not a valid node index.
#[inline(never)]
#[unsafe(export_name = "topic20_walk_eight")]
pub fn walk_eight(cycle: &Cycle, mut cursors: [usize; 8], loads: usize) -> usize {
    assert!(loads > 0 && loads.is_multiple_of(8));
    for _ in 0..loads / 8 {
        cursors[0] = cycle.next(cursors[0]);
        cursors[1] = cycle.next(cursors[1]);
        cursors[2] = cycle.next(cursors[2]);
        cursors[3] = cycle.next(cursors[3]);
        cursors[4] = cycle.next(cursors[4]);
        cursors[5] = cycle.next(cursors[5]);
        cursors[6] = cycle.next(cursors[6]);
        cursors[7] = cycle.next(cursors[7]);
    }
    black_box(
        cursors
            .into_iter()
            .fold(0, |accumulator, value| accumulator ^ value),
    )
}

/// Runs the selected treatment with one or eight independent cursors.
///
/// # Panics
///
/// - If `lanes` is neither 1 nor 8.
/// - If `lanes` is 8 and `loads` is zero or is not divisible by eight.
pub fn walk(cycle: &Cycle, lanes: usize, loads: usize) -> usize {
    match lanes {
        1 => walk_one(cycle, cycle.start(0), loads),
        8 => {
            let cursors = std::array::from_fn(|lane| cycle.start(lane * 2));
            walk_eight(cycle, cursors, loads)
        }
        _ => panic!("lanes must be 1 or 8"),
    }
}

// Generates the permutation during `Cycle::new`; timed walks never call it.
fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

#[cfg(test)]
mod tests {
    use super::{Cycle, Node, walk, walk_eight, walk_one};

    #[test]
    fn node_is_64_bytes_and_64_byte_aligned() {
        assert_eq!(size_of::<Node>(), 64);
        assert_eq!(align_of::<Node>(), 64);
    }

    #[test]
    fn cycle_visits_every_node_once() {
        let cycle = Cycle::new(4096, 7);
        let start = cycle.start(0);
        let mut cursor = start;
        let mut seen = vec![false; cycle.node_count()];
        for _ in 0..cycle.node_count() {
            assert!(!seen[cursor]);
            seen[cursor] = true;
            cursor = cycle.next(cursor);
        }
        assert_eq!(cursor, start);
        assert!(seen.into_iter().all(|value| value));
    }

    #[test]
    fn explicit_walkers_match_reference_steps() {
        let cycle = Cycle::new(4096, 11);
        let loads = 8192;

        let mut expected_one = cycle.start(0);
        for _ in 0..loads {
            expected_one = cycle.next(expected_one);
        }
        assert_eq!(walk_one(&cycle, cycle.start(0), loads), expected_one);
        assert_eq!(walk(&cycle, 1, loads), expected_one);

        let starts: [usize; 8] = std::array::from_fn(|lane| cycle.start(lane * 2));
        let mut expected = starts;
        for _ in 0..loads / 8 {
            for cursor in &mut expected {
                *cursor = cycle.next(*cursor);
            }
        }
        let expected_sink = expected
            .into_iter()
            .fold(0, |accumulator, value| accumulator ^ value);
        assert_eq!(walk_eight(&cycle, starts, loads), expected_sink);
        assert_eq!(walk(&cycle, 8, loads), expected_sink);
    }
}
