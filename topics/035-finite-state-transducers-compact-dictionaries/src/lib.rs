//! Topology-controlled byte dictionaries for comparing a trie with an exact
//! minimal deterministic acyclic finite-state acceptor (DAFSA).
//!
//! Both representations use the same flat state and arc records and the same
//! lookup function. Their only experimental difference is graph topology: the
//! trie shares prefixes, while the DAFSA also merges states with identical
//! accepted suffix languages.
//!
//! A state's accepted suffix language is the set of remaining byte strings
//! that lead from that state to an accepted key. States with the same set can
//! share one record without changing membership results.
//!
//! # Contract
//!
//! Builders require bytewise strictly increasing keys and reject duplicates.
//! Keys may be empty and may contain any byte; the builders perform no text
//! decoding or Unicode normalization. The structures are immutable after
//! construction. [`FlatDictionary::topology_bytes`] counts occupied state and
//! arc records. It is not a portable serialization size, an allocation size,
//! or process resident memory.
//!
//! # Example
//!
//! ```
//! use finite_state_transducers_compact_dictionaries::{
//!     build_flat_trie, build_minimal_dafsa,
//! };
//!
//! let keys = [b"bar".to_vec(), b"bat".to_vec(), b"car".to_vec(), b"cat".to_vec()];
//! let trie = build_flat_trie(&keys)?;
//! let dafsa = build_minimal_dafsa(&keys)?;
//!
//! assert!(trie.contains(b"cat"));
//! assert!(!dafsa.contains(b"cab"));
//! assert_eq!((trie.state_count(), trie.arc_count()), (9, 8));
//! assert_eq!((dafsa.state_count(), dafsa.arc_count()), (4, 5));
//! # Ok::<(), finite_state_transducers_compact_dictionaries::BuildError>(())
//! ```

use std::collections::{HashMap, HashSet};
use std::fmt;
use std::hint::black_box;
use std::mem::size_of;

const KEY_COUNT: usize = 65_536;
const QUERY_COUNT: usize = 16_384;

#[derive(Default)]
struct BuildState {
    final_state: bool,
    arcs: Vec<(u8, u32)>,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct State {
    first_arc: u32,
    arc_count: u16,
    final_state: u8,
    padding: u8,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Arc {
    label: u8,
    padding: [u8; 3],
    target: u32,
}

const _: [(); 8] = [(); size_of::<State>()];
const _: [(); 8] = [(); size_of::<Arc>()];

#[derive(Clone, Hash, PartialEq, Eq)]
struct Signature {
    final_state: bool,
    arcs: Vec<(u8, u32)>,
}

/// An input or fixed-width layout condition that prevents construction.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BuildError {
    /// Two adjacent keys are equal at the reported input index.
    DuplicateKey {
        /// Zero-based index of the second equal key.
        index: usize,
    },
    /// A key is bytewise smaller than its predecessor.
    KeysNotStrictlyIncreasing {
        /// Zero-based index of the descending key.
        index: usize,
    },
    /// A state identifier cannot fit in the format's 32-bit target field.
    TooManyStates,
    /// The total arc count cannot fit in a 32-bit state offset.
    TooManyArcs,
    /// One state's fanout cannot fit in its 16-bit count field.
    TooManyOutgoingArcs,
}

impl fmt::Display for BuildError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::DuplicateKey { index } => write!(formatter, "duplicate key at index {index}"),
            Self::KeysNotStrictlyIncreasing { index } => {
                write!(formatter, "keys descend at index {index}")
            }
            Self::TooManyStates => formatter.write_str("state count exceeds the 32-bit format"),
            Self::TooManyArcs => formatter.write_str("arc count exceeds the 32-bit format"),
            Self::TooManyOutgoingArcs => {
                formatter.write_str("state fanout exceeds the 16-bit format")
            }
        }
    }
}

impl std::error::Error for BuildError {}

/// Immutable byte dictionary backed by flat eight-byte state and arc records.
///
/// A `FlatDictionary` may contain trie topology or an exactly minimized DAFSA.
/// Lookup cannot distinguish the source topology and always uses the same
/// binary-search transition function.
#[derive(Clone)]
pub struct FlatDictionary {
    states: Vec<State>,
    arcs: Vec<Arc>,
    root: u32,
}

impl FlatDictionary {
    /// Tests exact membership without decoding or normalizing `key`.
    ///
    /// # Performance
    ///
    /// The function visits one state per examined key byte, stopping at the
    /// first absent transition, and binary-searches that state's sorted
    /// outgoing labels. It allocates no memory.
    #[inline]
    pub fn contains(&self, key: &[u8]) -> bool {
        topic035_flat_contains(self, key)
    }

    /// Returns the number of occupied state records.
    pub fn state_count(&self) -> usize {
        self.states.len()
    }

    /// Returns the number of occupied arc records.
    pub fn arc_count(&self) -> usize {
        self.arcs.len()
    }

    /// Returns logical bytes occupied by state and arc records.
    ///
    /// The count excludes vector headers, spare capacity, allocator metadata,
    /// source keys, queries, temporary builder storage, and memory residency.
    /// `#[repr(C)]` fixes record layout for this binary; it does not define a
    /// portable file format.
    pub fn topology_bytes(&self) -> usize {
        self.states.len() * size_of::<State>() + self.arcs.len() * size_of::<Arc>()
    }

    /// Reports whether every occupied state has a distinct structural signature.
    ///
    /// A true result proves that no two states in this acyclic acceptor have the
    /// same final flag and sorted `(label, target)` list. The builder emits only
    /// reachable states, so this is the exact-minimality check used by the probe.
    ///
    /// # Performance
    ///
    /// The no-duplicate case copies every arc pair into temporary signatures
    /// and retains one signature per state until the check completes.
    pub fn has_unique_state_signatures(&self) -> bool {
        let mut seen = HashSet::with_capacity(self.states.len());
        self.states.iter().all(|state| {
            let start = state.first_arc as usize;
            let end = start + state.arc_count as usize;
            let signature = Signature {
                final_state: state.final_state != 0,
                arcs: self.arcs[start..end]
                    .iter()
                    .map(|arc| (arc.label, arc.target))
                    .collect(),
            };
            seen.insert(signature)
        })
    }
}

/// Runs the shared linked lookup kernel used by both experimental methods.
///
/// The exported, non-inlined symbol keeps the exact search loop available for
/// generated-code inspection. Call [`FlatDictionary::contains`] in normal code.
///
/// # Performance
///
/// The function allocates no memory. It performs one binary search per consumed
/// key byte and returns at the first absent transition.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic035_flat_contains(dictionary: &FlatDictionary, key: &[u8]) -> bool {
    let mut state_id = dictionary.root as usize;
    for &wanted in key {
        let state = dictionary.states[state_id];
        let mut low = state.first_arc as usize;
        let mut high = low + state.arc_count as usize;
        let mut next = None;
        while low < high {
            let middle = low + (high - low) / 2;
            let arc = dictionary.arcs[middle];
            if arc.label < wanted {
                low = middle + 1;
            } else if arc.label > wanted {
                high = middle;
            } else {
                next = Some(arc.target as usize);
                break;
            }
        }
        match next {
            Some(target) => state_id = target,
            None => return false,
        }
    }
    dictionary.states[state_id].final_state != 0
}

fn validate_keys(keys: &[Vec<u8>]) -> Result<(), BuildError> {
    for (offset, pair) in keys.windows(2).enumerate() {
        if pair[0] == pair[1] {
            return Err(BuildError::DuplicateKey { index: offset + 1 });
        }
        if pair[0] > pair[1] {
            return Err(BuildError::KeysNotStrictlyIncreasing { index: offset + 1 });
        }
    }
    Ok(())
}

fn checked_state_id(value: usize) -> Result<u32, BuildError> {
    u32::try_from(value).map_err(|_| BuildError::TooManyStates)
}

fn insert_sorted(states: &mut Vec<BuildState>, key: &[u8]) -> Result<(), BuildError> {
    let mut state_id = 0_usize;
    for &label in key {
        let existing = states[state_id]
            .arcs
            .last()
            .filter(|(last_label, _)| *last_label == label)
            .map(|(_, target)| *target as usize);
        state_id = match existing {
            Some(target) => target,
            None => {
                let target = checked_state_id(states.len())?;
                states.push(BuildState::default());
                states[state_id].arcs.push((label, target));
                target as usize
            }
        };
    }
    states[state_id].final_state = true;
    Ok(())
}

fn build_trie_states(keys: &[Vec<u8>]) -> Result<Vec<BuildState>, BuildError> {
    validate_keys(keys)?;
    let mut states = vec![BuildState::default()];
    for key in keys {
        insert_sorted(&mut states, key)?;
    }
    Ok(states)
}

fn flatten_trie(source: &[BuildState]) -> Result<FlatDictionary, BuildError> {
    let edge_count = source.iter().try_fold(0_usize, |total, state| {
        total
            .checked_add(state.arcs.len())
            .ok_or(BuildError::TooManyArcs)
    })?;
    u32::try_from(edge_count).map_err(|_| BuildError::TooManyArcs)?;
    let mut states = Vec::with_capacity(source.len());
    let mut arcs = Vec::with_capacity(edge_count);
    for state in source {
        let first_arc = u32::try_from(arcs.len()).map_err(|_| BuildError::TooManyArcs)?;
        let arc_count =
            u16::try_from(state.arcs.len()).map_err(|_| BuildError::TooManyOutgoingArcs)?;
        arcs.extend(state.arcs.iter().map(|&(label, target)| Arc {
            label,
            padding: [0; 3],
            target,
        }));
        states.push(State {
            first_arc,
            arc_count,
            final_state: u8::from(state.final_state),
            padding: 0,
        });
    }
    Ok(FlatDictionary {
        states,
        arcs,
        root: 0,
    })
}

fn minimize(source: &[BuildState]) -> Result<FlatDictionary, BuildError> {
    let mut old_to_new = vec![u32::MAX; source.len()];
    let mut register: HashMap<Signature, u32> = HashMap::new();
    let mut unique: Vec<Signature> = Vec::new();

    for old_id in (0..source.len()).rev() {
        let signature = Signature {
            final_state: source[old_id].final_state,
            arcs: source[old_id]
                .arcs
                .iter()
                .map(|&(label, target)| (label, old_to_new[target as usize]))
                .collect(),
        };
        let canonical = match register.get(&signature) {
            Some(&id) => id,
            None => {
                let id = checked_state_id(unique.len())?;
                register.insert(signature.clone(), id);
                unique.push(signature);
                id
            }
        };
        old_to_new[old_id] = canonical;
    }

    let edge_count = unique.iter().try_fold(0_usize, |total, state| {
        total
            .checked_add(state.arcs.len())
            .ok_or(BuildError::TooManyArcs)
    })?;
    u32::try_from(edge_count).map_err(|_| BuildError::TooManyArcs)?;
    let mut states = Vec::with_capacity(unique.len());
    let mut arcs = Vec::with_capacity(edge_count);
    for state in unique {
        let first_arc = u32::try_from(arcs.len()).map_err(|_| BuildError::TooManyArcs)?;
        let arc_count =
            u16::try_from(state.arcs.len()).map_err(|_| BuildError::TooManyOutgoingArcs)?;
        arcs.extend(state.arcs.into_iter().map(|(label, target)| Arc {
            label,
            padding: [0; 3],
            target,
        }));
        states.push(State {
            first_arc,
            arc_count,
            final_state: u8::from(state.final_state),
            padding: 0,
        });
    }
    Ok(FlatDictionary {
        states,
        arcs,
        root: old_to_new[0],
    })
}

/// Builds a flat trie from strictly increasing byte keys.
///
/// # Errors
///
/// - [`BuildError::DuplicateKey`] if two adjacent keys are equal.
/// - [`BuildError::KeysNotStrictlyIncreasing`] if a key is bytewise smaller
///   than its predecessor.
/// - [`BuildError::TooManyStates`] if a state identifier does not fit in `u32`.
/// - [`BuildError::TooManyArcs`] if the total arc count does not fit in `u32`.
/// - [`BuildError::TooManyOutgoingArcs`] if one state's arc count does not fit
///   in `u16`.
///
/// # Performance
///
/// Construction uses time and temporary storage proportional to the total key
/// bytes. The resulting graph contains one state per distinct key prefix.
pub fn build_flat_trie(keys: &[Vec<u8>]) -> Result<FlatDictionary, BuildError> {
    flatten_trie(&build_trie_states(keys)?)
}

/// Builds an exact minimal DAFSA from strictly increasing byte keys.
///
/// The builder first creates a trie, then registers bottom-up state signatures.
/// It retains the complete signature registry, so equivalent states cannot be
/// missed because of cache eviction.
///
/// # Errors
///
/// - [`BuildError::DuplicateKey`] if two adjacent keys are equal.
/// - [`BuildError::KeysNotStrictlyIncreasing`] if a key is bytewise smaller
///   than its predecessor.
/// - [`BuildError::TooManyStates`] if a state identifier does not fit in `u32`.
/// - [`BuildError::TooManyArcs`] if the total arc count does not fit in `u32`.
/// - [`BuildError::TooManyOutgoingArcs`] if one state's arc count does not fit
///   in `u16`.
///
/// # Performance
///
/// The temporary trie uses storage proportional to total distinct prefixes.
/// Hash-registry lookup has expected constant cost per completed state; full
/// signature comparison resolves collisions.
pub fn build_minimal_dafsa(keys: &[Vec<u8>]) -> Result<FlatDictionary, BuildError> {
    minimize(&build_trie_states(keys)?)
}

fn hex_digit(value: usize) -> u8 {
    match value {
        0..=9 => b'0' + value as u8,
        10..=15 => b'a' + (value - 10) as u8,
        _ => unreachable!(),
    }
}

/// Generates all four-hex-digit prefixes followed by `:metrics:v1`.
///
/// The result contains 65,536 sorted, unique, 15-byte keys.
pub fn shared_keys() -> Vec<Vec<u8>> {
    let mut keys = Vec::with_capacity(KEY_COUNT);
    for value in 0..KEY_COUNT {
        let mut key = Vec::with_capacity(15);
        key.push(hex_digit((value >> 12) & 0xf));
        key.push(hex_digit((value >> 8) & 0xf));
        key.push(hex_digit((value >> 4) & 0xf));
        key.push(hex_digit(value & 0xf));
        key.extend_from_slice(b":metrics:v1");
        keys.push(key);
    }
    keys
}

fn splitmix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

/// Generates deterministic opaque 16-byte keys from SplitMix64 output.
///
/// The result contains 65,536 sorted, unique keys. “Opaque” describes the
/// generator; it does not claim that the minimal graph has no shared states.
///
/// # Panics
///
/// Panics if the fixed generator produces fewer than 65,536 unique keys.
pub fn opaque_keys() -> Vec<Vec<u8>> {
    let mut keys = Vec::with_capacity(KEY_COUNT);
    for value in 0..KEY_COUNT as u64 {
        let first = splitmix64(value);
        let second = splitmix64(value ^ 0xd1b5_4a32_d192_ed03);
        let mut key = Vec::with_capacity(16);
        key.extend_from_slice(&first.to_be_bytes());
        key.extend_from_slice(&second.to_be_bytes());
        keys.push(key);
    }
    keys.sort_unstable();
    keys.dedup();
    assert_eq!(keys.len(), KEY_COUNT, "fixed generator must remain unique");
    keys
}

/// Builds the fixed 50% hit and 50% append-byte-miss query sequence.
///
/// The input must contain at least one key. Each even query is a selected key;
/// the following odd query appends zero to that key and therefore misses when
/// the source is a fixed-length corpus.
///
/// # Panics
///
/// Panics if `keys` is empty.
pub fn benchmark_queries(keys: &[Vec<u8>]) -> Vec<Vec<u8>> {
    assert!(!keys.is_empty(), "benchmark corpus must not be empty");
    let mut queries = Vec::with_capacity(QUERY_COUNT);
    for index in 0..(QUERY_COUNT / 2) {
        let selected = splitmix64(index as u64) as usize % keys.len();
        queries.push(keys[selected].clone());
        let mut miss = keys[selected].clone();
        miss.push(0);
        queries.push(miss);
    }
    queries
}

/// Computes the 64-bit FNV-1a checksum used by measurement receipts.
///
/// FNV-1a is non-cryptographic and provides no collision-resistance guarantee.
pub fn checksum(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf2_9ce4_8422_2325, |hash, &byte| {
        (hash ^ u64::from(byte)).wrapping_mul(0x0000_0100_0000_01b3)
    })
}

/// Folds an ordered byte-string sequence into the stable receipt checksum.
///
/// The fold incorporates input order and each value's length. It remains
/// non-cryptographic and may collide.
pub fn sequence_checksum(values: &[Vec<u8>]) -> u64 {
    values.iter().fold(0x517c_c1b7_2722_0a95, |state, value| {
        state.rotate_left(11) ^ checksum(value).wrapping_add(value.len() as u64)
    })
}

/// Prevents link-time removal of the shared inspection hook.
pub fn retain_inspection_hook(dictionary: &FlatDictionary) {
    let hook: fn(&FlatDictionary, &[u8]) -> bool = black_box(topic035_flat_contains);
    black_box(hook(black_box(dictionary), black_box(b"linked-code")));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn keys(values: &[&[u8]]) -> Vec<Vec<u8>> {
        values.iter().map(|value| value.to_vec()).collect()
    }

    fn assert_matches_oracle(source: &[Vec<u8>], queries: &[Vec<u8>]) {
        let trie = build_flat_trie(source).unwrap();
        let dafsa = build_minimal_dafsa(source).unwrap();
        for query in queries {
            let expected = source.binary_search(query).is_ok();
            assert_eq!(trie.contains(query), expected, "trie query {query:?}");
            assert_eq!(dafsa.contains(query), expected, "DAFSA query {query:?}");
        }
        assert!(dafsa.has_unique_state_signatures());
    }

    #[test]
    fn running_example_has_expected_topology() {
        let source = keys(&[b"bar", b"bat", b"car", b"cat"]);
        let trie = build_flat_trie(&source).unwrap();
        let dafsa = build_minimal_dafsa(&source).unwrap();
        assert_eq!((trie.state_count(), trie.arc_count()), (9, 8));
        assert_eq!((dafsa.state_count(), dafsa.arc_count()), (4, 5));
        assert_matches_oracle(&source, &keys(&[b"bar", b"bat", b"cab", b"cat"]));
    }

    #[test]
    fn rejects_duplicate_and_descending_keys() {
        assert_eq!(
            build_flat_trie(&keys(&[b"a", b"a"])).err(),
            Some(BuildError::DuplicateKey { index: 1 })
        );
        assert_eq!(
            build_minimal_dafsa(&keys(&[b"b", b"a"])).err(),
            Some(BuildError::KeysNotStrictlyIncreasing { index: 1 })
        );
    }

    #[test]
    fn handles_empty_prefix_and_arbitrary_bytes() {
        let source = keys(&[b"", b"\0", b"\0\xff", b"a", b"a\0", b"\xff"]);
        let queries = keys(&[
            b"", b"\0", b"\0\0", b"\0\xff", b"a", b"a\0", b"a\0\0", b"\xfe", b"\xff",
        ]);
        assert_matches_oracle(&source, &queries);
    }

    #[test]
    fn exhaustive_binary_dictionaries_match_oracle() {
        let universe = keys(&[b"", b"a", b"aa", b"ab", b"b", b"ba", b"bb"]);
        for mask in 0_u16..(1_u16 << universe.len()) {
            let source: Vec<Vec<u8>> = universe
                .iter()
                .enumerate()
                .filter(|(index, _)| mask & (1 << index) != 0)
                .map(|(_, key)| key.clone())
                .collect();
            assert_matches_oracle(&source, &universe);
        }
    }

    #[test]
    fn benchmark_corpora_have_stable_topology() {
        let shared = shared_keys();
        assert_eq!(shared.iter().map(Vec::len).sum::<usize>(), 983_040);
        let shared_trie = build_flat_trie(&shared).unwrap();
        let shared_dafsa = build_minimal_dafsa(&shared).unwrap();
        assert_eq!(
            (
                shared_trie.state_count(),
                shared_trie.arc_count(),
                shared_trie.topology_bytes()
            ),
            (790_801, 790_800, 12_652_808)
        );
        assert_eq!(
            (
                shared_dafsa.state_count(),
                shared_dafsa.arc_count(),
                shared_dafsa.topology_bytes()
            ),
            (16, 75, 728)
        );
        assert!(shared_dafsa.has_unique_state_signatures());

        let opaque = opaque_keys();
        assert_eq!(opaque.iter().map(Vec::len).sum::<usize>(), 1_048_576);
        let opaque_trie = build_flat_trie(&opaque).unwrap();
        let opaque_dafsa = build_minimal_dafsa(&opaque).unwrap();
        assert_eq!(
            (
                opaque_trie.state_count(),
                opaque_trie.arc_count(),
                opaque_trie.topology_bytes()
            ),
            (959_061, 959_060, 15_344_968)
        );
        assert_eq!(
            (
                opaque_dafsa.state_count(),
                opaque_dafsa.arc_count(),
                opaque_dafsa.topology_bytes()
            ),
            (804_065, 869_599, 13_389_312)
        );
        assert!(opaque_dafsa.has_unique_state_signatures());
    }

    #[test]
    fn fixed_queries_have_half_hits() {
        for source in [shared_keys(), opaque_keys()] {
            let queries = benchmark_queries(&source);
            assert_eq!(queries.len(), QUERY_COUNT);
            let hits = queries
                .iter()
                .filter(|query| source.binary_search(query).is_ok())
                .count();
            assert_eq!(hits, QUERY_COUNT / 2);
            assert_matches_oracle(&source, &queries);
        }
    }
}
