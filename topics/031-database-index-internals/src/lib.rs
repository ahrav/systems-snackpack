//! A deterministic model of narrow and covering secondary-index layouts.
//!
//! The crate isolates in-memory lookup and data-layout costs. It does not model
//! a database buffer manager, concurrency, transactions, logging, or storage.

use std::hint::black_box;
use std::time::{Duration, Instant};

/// Default number of indexed rows.
pub const DEFAULT_ENTRIES: usize = 1 << 20;
/// Default number of keys in one query pass.
pub const DEFAULT_QUERIES: usize = 1 << 16;
/// Default number of timed query passes.
pub const DEFAULT_REPS: usize = 8;

/// The values returned for a matching key.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[repr(C)]
pub struct Payload {
    /// First projected value.
    pub first: u64,
    /// Second projected value.
    pub second: u64,
}

/// One narrow secondary-index entry.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct NarrowEntry {
    /// Sorted lookup key.
    pub key: u64,
    /// Position of the payload in the separate heap array.
    pub row_locator: usize,
}

/// One wider entry that covers the modeled query.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
pub struct CoveringEntry {
    /// Sorted lookup key.
    pub key: u64,
    /// Payload returned without a separate heap lookup.
    pub payload: Payload,
}

/// Deterministic data shared by both lookup layouts.
#[derive(Debug)]
pub struct Corpus {
    narrow: Vec<NarrowEntry>,
    covering: Vec<CoveringEntry>,
    heap: Vec<Payload>,
}

impl Corpus {
    /// Builds `len` rows. `len` must be a nonzero power of two.
    #[must_use]
    pub fn new(len: usize) -> Self {
        assert!(len.is_power_of_two() && len > 0);

        let mut narrow = Vec::with_capacity(len);
        let mut covering = Vec::with_capacity(len);
        let mut heap = vec![Payload::default(); len];
        let mask = len - 1;

        for row in 0..len {
            let key = key_for_row(row);
            let payload = payload_for_row(row);
            // Odd multiplication modulo a power of two is a permutation. It
            // makes adjacent index entries name distant heap positions.
            let row_locator = row.wrapping_mul(0x9e37_79b9_7f4a_7c15) & mask;
            heap[row_locator] = payload;
            narrow.push(NarrowEntry { key, row_locator });
            covering.push(CoveringEntry { key, payload });
        }

        Self {
            narrow,
            covering,
            heap,
        }
    }

    /// Returns the number of indexed rows.
    #[must_use]
    pub fn len(&self) -> usize {
        self.narrow.len()
    }

    /// Returns whether the corpus contains no rows.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.narrow.is_empty()
    }

    /// Looks up a key through the narrow index and separate heap.
    #[must_use]
    pub fn lookup_narrow(&self, key: u64) -> Option<Payload> {
        topic31_narrow_lookup(&self.narrow, &self.heap, key)
    }

    /// Looks up a key through the covering entries.
    #[must_use]
    pub fn lookup_covering(&self, key: u64) -> Option<Payload> {
        topic31_covering_lookup(&self.covering, key)
    }

    /// Returns modeled and Rust representation byte counts.
    #[must_use]
    pub fn layout(&self) -> LayoutBytes {
        LayoutBytes {
            rows: self.len(),
            logical_narrow_index: self.len() * 16,
            logical_heap: self.len() * 16,
            logical_covering_index: self.len() * 24,
            rust_narrow_entry: std::mem::size_of::<NarrowEntry>(),
            rust_payload: std::mem::size_of::<Payload>(),
            rust_covering_entry: std::mem::size_of::<CoveringEntry>(),
        }
    }
}

/// Logical and compiler-layout byte counts.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LayoutBytes {
    /// Number of represented rows.
    pub rows: usize,
    /// Logical bytes in `(key, row locator)` entries.
    pub logical_narrow_index: usize,
    /// Logical bytes in the separate payload array.
    pub logical_heap: usize,
    /// Logical bytes in `(key, payload)` entries.
    pub logical_covering_index: usize,
    /// Rust size of one narrow entry.
    pub rust_narrow_entry: usize,
    /// Rust size of one payload.
    pub rust_payload: usize,
    /// Rust size of one covering entry.
    pub rust_covering_entry: usize,
}

/// One benchmark treatment.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Treatment {
    /// Narrow sorted entries followed by a heap payload access.
    Narrow,
    /// Wider entries containing the returned payload.
    Covering,
}

impl Treatment {
    /// Parses the command-line spelling of a treatment.
    #[must_use]
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "narrow" => Some(Self::Narrow),
            "covering" => Some(Self::Covering),
            _ => None,
        }
    }

    /// Returns the command-line spelling.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Narrow => "narrow",
            Self::Covering => "covering",
        }
    }
}

/// Timing fields for one fresh-process treatment.
#[derive(Clone, Copy, Debug)]
pub struct RunResult {
    /// Timed treatment.
    pub treatment: Treatment,
    /// Number of represented rows.
    pub entries: usize,
    /// Queries in one pass.
    pub queries: usize,
    /// Timed passes.
    pub reps: usize,
    /// Corpus and query construction time.
    pub setup: Duration,
    /// Correctness and untimed warmup time.
    pub nonsteady: Duration,
    /// Steady-state treatment time.
    pub steady: Duration,
    /// Deterministic result accumulator.
    pub checksum: u64,
    /// Layout sizes reported with the result.
    pub layout: LayoutBytes,
}

/// Generates a deterministic query stream containing equal numbers of hits and
/// misses when `len` is even.
#[must_use]
pub fn make_queries(rows: usize, len: usize) -> Vec<u64> {
    assert!(rows.is_power_of_two() && rows > 0);
    let mut state = 0x031d_ba5e_5eed_cafe_u64;
    let mut queries = Vec::with_capacity(len);
    for position in 0..len {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        let row = (state as usize) & (rows - 1);
        let key = key_for_row(row);
        queries.push(if position & 1 == 0 { key } else { key + 1 });
    }
    queries
}

/// Returns the reference result for a key without consulting either index.
#[must_use]
pub fn oracle(rows: usize, key: u64) -> Option<Payload> {
    if key & 3 != 1 {
        return None;
    }
    let row = ((key - 1) / 4) as usize;
    (row < rows).then(|| payload_for_row(row))
}

/// Validates both representations against the reference result.
///
/// # Errors
///
/// Returns a message naming the first mismatching query.
pub fn validate(corpus: &Corpus, queries: &[u64]) -> Result<(), String> {
    for (position, &key) in queries.iter().enumerate() {
        let expected = oracle(corpus.len(), key);
        let narrow = corpus.lookup_narrow(key);
        let covering = corpus.lookup_covering(key);
        if narrow != expected || covering != expected {
            return Err(format!(
                "query {position} key {key}: expected {expected:?}, narrow {narrow:?}, covering {covering:?}"
            ));
        }
    }
    Ok(())
}

/// Runs one treatment with setup, validation, warmup, and steady time kept
/// separate.
///
/// # Errors
///
/// Returns a validation error if either representation disagrees with the
/// reference oracle.
pub fn run_treatment(
    treatment: Treatment,
    entries: usize,
    query_count: usize,
    reps: usize,
) -> Result<RunResult, String> {
    let setup_start = Instant::now();
    let corpus = Corpus::new(entries);
    let queries = make_queries(entries, query_count);
    let setup = setup_start.elapsed();

    let nonsteady_start = Instant::now();
    validate(&corpus, &queries)?;
    let warmup = run_pass(&corpus, &queries, treatment);
    black_box(warmup);
    let nonsteady = nonsteady_start.elapsed();

    let steady_start = Instant::now();
    let mut checksum = 0_u64;
    for _ in 0..reps {
        checksum = checksum.wrapping_add(run_pass(&corpus, &queries, treatment));
    }
    let steady = steady_start.elapsed();

    Ok(RunResult {
        treatment,
        entries,
        queries: query_count,
        reps,
        setup,
        nonsteady,
        steady,
        checksum,
        layout: corpus.layout(),
    })
}

/// Stable linked-image hook for narrow lookup disassembly.
#[inline(never)]
#[unsafe(export_name = "topic31_narrow_lookup")]
pub fn topic31_narrow_lookup(
    entries: &[NarrowEntry],
    heap: &[Payload],
    key: u64,
) -> Option<Payload> {
    let position = lower_bound_narrow(entries, key);
    if position < entries.len() && entries[position].key == key {
        Some(heap[entries[position].row_locator])
    } else {
        None
    }
}

/// Stable linked-image hook for covering lookup disassembly.
#[inline(never)]
#[unsafe(export_name = "topic31_covering_lookup")]
pub fn topic31_covering_lookup(entries: &[CoveringEntry], key: u64) -> Option<Payload> {
    let position = lower_bound_covering(entries, key);
    if position < entries.len() && entries[position].key == key {
        Some(entries[position].payload)
    } else {
        None
    }
}

fn lower_bound_narrow(entries: &[NarrowEntry], key: u64) -> usize {
    let mut left = 0;
    let mut right = entries.len();
    while left < right {
        let middle = left + (right - left) / 2;
        if entries[middle].key < key {
            left = middle + 1;
        } else {
            right = middle;
        }
    }
    left
}

fn lower_bound_covering(entries: &[CoveringEntry], key: u64) -> usize {
    let mut left = 0;
    let mut right = entries.len();
    while left < right {
        let middle = left + (right - left) / 2;
        if entries[middle].key < key {
            left = middle + 1;
        } else {
            right = middle;
        }
    }
    left
}

fn run_pass(corpus: &Corpus, queries: &[u64], treatment: Treatment) -> u64 {
    let mut checksum = 0_u64;
    for &key in queries {
        let value = match treatment {
            Treatment::Narrow => corpus.lookup_narrow(black_box(key)),
            Treatment::Covering => corpus.lookup_covering(black_box(key)),
        };
        checksum = checksum.wrapping_add(match value {
            Some(payload) => payload.first.rotate_left(7) ^ payload.second,
            None => 0xd1b5_4a32_d192_ed03,
        });
    }
    black_box(checksum)
}

const fn key_for_row(row: usize) -> u64 {
    (row as u64) * 4 + 1
}

const fn payload_for_row(row: usize) -> Payload {
    let value = row as u64;
    Payload {
        first: value.wrapping_mul(0xd6e8_feb8_6659_fd93),
        second: value.rotate_left(23) ^ 0xa076_1d64_78bd_642f,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layouts_match_oracle_for_hits_and_misses() {
        let corpus = Corpus::new(1 << 12);
        let queries = make_queries(corpus.len(), 1 << 13);
        validate(&corpus, &queries).unwrap();
    }

    #[test]
    fn boundary_keys_are_correct() {
        let corpus = Corpus::new(8);
        for key in [0, 1, 2, 29, 30, 33, u64::MAX] {
            assert_eq!(corpus.lookup_narrow(key), oracle(corpus.len(), key));
            assert_eq!(corpus.lookup_covering(key), oracle(corpus.len(), key));
        }
    }

    #[test]
    fn logical_and_rust_layouts_are_explicit() {
        let corpus = Corpus::new(16);
        let layout = corpus.layout();
        assert_eq!(layout.logical_narrow_index, 16 * 16);
        assert_eq!(layout.logical_heap, 16 * 16);
        assert_eq!(layout.logical_covering_index, 16 * 24);
        assert_eq!(layout.rust_narrow_entry, 16);
        assert_eq!(layout.rust_payload, 16);
        assert_eq!(layout.rust_covering_entry, 24);
    }

    #[test]
    fn treatments_have_identical_checksums() {
        let narrow = run_treatment(Treatment::Narrow, 1 << 12, 1 << 10, 2).unwrap();
        let covering = run_treatment(Treatment::Covering, 1 << 12, 1 << 10, 2).unwrap();
        assert_eq!(narrow.checksum, covering.checksum);
    }
}
