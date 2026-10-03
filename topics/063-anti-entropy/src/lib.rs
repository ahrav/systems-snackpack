//! Finite reference model for causal reconciliation of three catalog replicas.
//!
//! Merge retains concurrent versions and explicit deletion records. Delivery is
//! modeled separately. Writer identities never change; counters are supplied by
//! the fixture. This is not a database or a safe tombstone collection protocol.
//!
//! ```
//! use topic063_anti_entropy::{Version, merge};
//! let old = Version { clock: [1, 0, 0], value: Some(10) };
//! let deleted = Version { clock: [2, 0, 0], value: None };
//! assert_eq!(merge(&[old], &[deleted]), vec![deleted]);
//! ```

use std::collections::BTreeMap;

/// One version of a catalog record, including a retained deletion marker.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version {
    /// History counters in stable writer order A, B, C.
    pub clock: [u64; 3],
    /// Encoded product value; `None` is a tombstone, not missing history.
    pub value: Option<u64>,
}

/// A key's canonical, causally maximal versions. Empty means no retained history.
pub type State = Vec<Version>;

/// Catalog records, including any retained tombstones and concurrent siblings.
pub type Catalog = BTreeMap<u32, State>;

/// Whether `x` is strictly causally before `y` in this fixed-identity model.
#[inline(never)]
pub fn before(x: &[u64; 3], y: &[u64; 3]) -> bool {
    x.iter().zip(y).all(|(a, b)| a <= b) && x != y
}

/// Union histories, deduplicate them, and discard strictly superseded versions.
///
/// This quadratic reference algorithm favors a clear contract over throughput.
/// Inputs must use the same writer identities and preserve complete counters.
///
/// # Panics
///
/// Panics if an identical history labels two different payloads. The model
/// requires one immutable payload per history and rejects that invalid input.
pub fn merge(a: &[Version], b: &[Version]) -> State {
    let mut all = a.to_vec();
    all.extend_from_slice(b);
    all.sort();
    all.dedup();
    for pair in all.windows(2) {
        assert_ne!(
            pair[0].clock, pair[1].clock,
            "history reused for a different payload"
        );
    }
    all.iter()
        .filter(|v| !all.iter().any(|w| before(&v.clock, &w.clock)))
        .copied()
        .collect()
}

/// Absence is the only encoding of unknown history, so two catalogs holding
/// the same knowledge compare equal.
fn store(catalog: &mut Catalog, key: u32, state: State) {
    if state.is_empty() {
        catalog.remove(&key);
    } else {
        catalog.insert(key, state);
    }
}

/// Merge all records from one delivered snapshot into a local catalog.
///
/// Missing keys are absence of knowledge, not evidence of deletion.
/// Panics on invalid histories as described by [`merge`].
pub fn receive(local: &mut Catalog, incoming: &Catalog) {
    for (&key, versions) in incoming {
        let merged = merge(local.get(&key).map_or(&[], Vec::as_slice), versions);
        store(local, key, merged);
    }
}

/// Repair exactly the selected key in two replicas, ignoring all other keys.
/// A key unknown to both replicas stays absent from both.
///
/// This idealized two-replica operation models coverage, not a product's quorum
/// protocol, failure behavior, latency, or partition-level atomicity.
/// Panics on invalid histories as described by [`merge`].
pub fn repair_read(a: &mut Catalog, b: &mut Catalog, key: u32) {
    let state = merge(
        a.get(&key).map_or(&[], Vec::as_slice),
        b.get(&key).map_or(&[], Vec::as_slice),
    );
    store(a, key, state.clone());
    store(b, key, state);
}

/// Bidirectionally exchange full catalog state between distinct replicas.
///
/// # Panics
///
/// Panics on invalid indices, equal indices, or conflicting history identities.
pub fn exchange(replicas: &mut [Catalog; 3], a: usize, b: usize) {
    assert_ne!(a, b);
    let mut combined = replicas[a].clone();
    receive(&mut combined, &replicas[b]);
    replicas[a] = combined.clone();
    replicas[b] = combined;
}

/// Exact reference comparator for equal-size fixed record ranges.
///
/// Returns differing leaf-range indices. It compares complete canonical states,
/// including history and deletion metadata. It does not hash or implement a
/// Merkle tree; it is an oracle for a future summary-based implementation.
///
/// # Panics
///
/// Panics on unequal record counts or a zero leaf size.
pub fn differing_ranges(a: &[State], b: &[State], leaf_size: usize) -> Vec<usize> {
    assert_eq!(a.len(), b.len());
    assert!(leaf_size > 0);
    a.chunks(leaf_size)
        .zip(b.chunks(leaf_size))
        .enumerate()
        .filter_map(|(i, (x, y))| (x != y).then_some(i))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const OLD: Version = Version {
        clock: [1, 0, 0],
        value: Some(10),
    };
    const DELETED: Version = Version {
        clock: [2, 0, 0],
        value: None,
    };
    const EDITED: Version = Version {
        clock: [1, 1, 0],
        value: Some(20),
    };
    const RESOLVED: Version = Version {
        clock: [3, 1, 0],
        value: Some(30),
    };
    const THIRD: Version = Version {
        clock: [1, 0, 1],
        value: Some(40),
    };

    fn catalog(v: Version) -> Catalog {
        BTreeMap::from([(42, vec![v])])
    }

    #[test]
    fn causality_is_not_lexicographic_order() {
        assert!(before(&OLD.clock, &DELETED.clock));
        assert!(!before(&DELETED.clock, &EDITED.clock));
        assert!(!before(&EDITED.clock, &DELETED.clock));
        assert!(!before(&OLD.clock, &OLD.clock));
    }

    #[test]
    fn concurrent_delete_and_edit_remain_siblings() {
        let state = merge(&[OLD, DELETED], &[EDITED]);
        assert_eq!(state, vec![EDITED, DELETED]);
    }

    #[test]
    fn resolving_write_must_cover_all_siblings() {
        let state = merge(&[DELETED, EDITED], &[RESOLVED]);
        assert_eq!(state, vec![RESOLVED]);
        let stale_context_write = Version {
            clock: [3, 0, 0],
            value: Some(30),
        };
        assert_eq!(merge(&[DELETED, EDITED], &[stale_context_write]).len(), 2);
    }

    #[test]
    fn merge_laws_hold_for_all_32_fixture_subsets() {
        let versions = [OLD, DELETED, EDITED, RESOLVED, THIRD];
        let states: Vec<_> = (0..32)
            .map(|mask| {
                let raw: Vec<_> = versions
                    .iter()
                    .enumerate()
                    .filter_map(|(i, &v)| ((mask & (1 << i)) != 0).then_some(v))
                    .collect();
                merge(&raw, &[])
            })
            .collect();
        for a in &states {
            assert_eq!(merge(a, a), *a);
            for b in &states {
                assert_eq!(merge(a, b), merge(b, a));
                for c in &states {
                    assert_eq!(merge(&merge(a, b), c), merge(a, &merge(b, c)));
                }
            }
        }
    }

    #[test]
    fn retained_delete_beats_obsolete_value() {
        assert_eq!(merge(&[DELETED], &[OLD]), vec![DELETED]);
    }

    #[test]
    fn forgotten_delete_resurrects_obsolete_value() {
        assert_eq!(merge(&[], &[OLD]), vec![OLD]);
    }

    #[test]
    fn read_repair_leaves_cold_key_stale() {
        let mut a = BTreeMap::from([(42, vec![DELETED]), (43, vec![DELETED])]);
        let mut c = BTreeMap::from([(42, vec![OLD]), (43, vec![OLD])]);
        repair_read(&mut a, &mut c, 42);
        assert_eq!(a[&42], c[&42]);
        assert_ne!(a[&43], c[&43]);
        receive(&mut c, &a);
        assert_eq!(a, c);
    }

    #[test]
    fn unknown_key_stays_absent_after_repair_and_delivery() {
        let mut a = Catalog::new();
        let mut c = Catalog::new();
        repair_read(&mut a, &mut c, 7);
        assert!(a.is_empty());
        assert!(c.is_empty());
        receive(&mut a, &BTreeMap::from([(7, Vec::new())]));
        assert!(a.is_empty());
    }

    #[test]
    fn finite_schedule_converges_despite_duplicate_delivery() {
        let mut replicas = [catalog(DELETED), catalog(EDITED), catalog(OLD)];
        for (a, b) in [(0, 1), (0, 1), (1, 2), (2, 0)] {
            exchange(&mut replicas, a, b);
        }
        assert_eq!(replicas[0], replicas[1]);
        assert_eq!(replicas[1], replicas[2]);
        assert_eq!(replicas[0][&42].len(), 2);
    }

    #[test]
    fn isolation_prevents_convergence_even_with_valid_merge() {
        let mut replicas = [catalog(DELETED), catalog(EDITED), catalog(OLD)];
        for _ in 0..10 {
            exchange(&mut replicas, 0, 1);
        }
        assert_eq!(replicas[0], replicas[1]);
        assert_eq!(replicas[0][&42], vec![EDITED, DELETED]);
        assert_eq!(replicas[2], catalog(OLD));
        assert_ne!(replicas[0], replicas[2]);
    }

    #[test]
    fn range_oracle_includes_history_and_tombstones() {
        let a = vec![vec![OLD]; 16];
        let mut b = a.clone();
        b[6] = vec![Version {
            clock: [2, 0, 0],
            value: OLD.value,
        }];
        assert_eq!(differing_ranges(&a, &b, 4), vec![1]);
        b[12] = vec![DELETED];
        assert_eq!(differing_ranges(&a, &b, 4), vec![1, 3]);
        assert!(differing_ranges(&a, &a, 4).is_empty());
    }

    #[test]
    #[should_panic(expected = "history reused")]
    fn history_identity_reuse_is_rejected() {
        merge(&[OLD], &[Version { value: None, ..OLD }]);
    }
}
