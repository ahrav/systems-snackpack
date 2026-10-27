//! Fixed-capacity linear probing with optional seven-bit fingerprints.
//!
//! Tombstones preserve reachability; every probe visits at most the slot count.
//! The mixer is deterministic and offers no collision-attack protection.
//! ```
//! use modern_hash_tables::Table;
//! let mut map = Table::<true>::new(8);
//! assert_eq!(map.insert(17, 170), Ok(None));
//! assert_eq!(map.remove(17), Some(170));
//! assert_eq!(map.get(17), None);
//! ```

const EMPTY: u8 = 128;
const DELETED: u8 = 129;

/// A deterministic bijective 64-bit mixer for controlled integer experiments.
pub fn mix(mut x: u64) -> u64 {
    x ^= x >> 30;
    x = x.wrapping_mul(0xbf58476d1ce4e5b9);
    x ^= x >> 27;
    x = x.wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

/// Insertion of a new key requires a reusable slot.
#[derive(Debug, PartialEq, Eq)]
pub struct Full;

/// Counts from an untimed lookup. Equality counts include true matches.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct ProbeStats {
    /// Control bytes inspected, including a terminating empty byte.
    pub probes: usize,
    /// Full key equality checks after metadata filtering.
    pub equalities: usize,
}

/// Single-threaded fixed storage. `FILTER` enables a seven-bit tag check.
///
/// Both variants share the same probe order, payload layout and hash.
/// This scalar teaching table has no SIMD groups or automatic maintenance.
pub struct Table<const FILTER: bool> {
    ctrl: Vec<u8>,
    entries: Vec<(u64, u64)>,
    len: usize,
    deleted: usize,
}

impl<const FILTER: bool> Table<FILTER> {
    /// Allocate a positive power-of-two number of physical slots.
    /// Panics if the requested slot count does not satisfy this condition.
    pub fn new(slots: usize) -> Self {
        assert!(slots.is_power_of_two());
        Self {
            ctrl: vec![EMPTY; slots],
            entries: vec![(0, 0); slots],
            len: 0,
            deleted: 0,
        }
    }

    fn tag(hash: u64) -> u8 {
        if FILTER { (hash >> 57) as u8 } else { 0 }
    }

    fn locate<const TRACK: bool>(&self, key: u64) -> (Option<usize>, ProbeStats) {
        let hash = mix(key);
        let tag = Self::tag(hash);
        let mask = self.ctrl.len() - 1;
        let mut stats = ProbeStats::default();
        for step in 0..self.ctrl.len() {
            let i = (hash as usize).wrapping_add(step) & mask;
            let c = self.ctrl[i];
            if TRACK {
                stats.probes += 1;
            }
            if c == EMPTY {
                return (None, stats);
            }
            if c < EMPTY && (!FILTER || c == tag) {
                if TRACK {
                    stats.equalities += 1;
                }
                if self.entries[i].0 == key {
                    return (Some(i), stats);
                }
            }
        }
        (None, stats)
    }

    /// Look up a copied value; termination remains bounded in a full table.
    pub fn get(&self, key: u64) -> Option<u64> {
        self.locate::<false>(key).0.map(|i| self.entries[i].1)
    }

    /// Count probe and equality work outside the timing loop.
    pub fn stats(&self, key: u64) -> ProbeStats {
        self.locate::<true>(key).1
    }

    /// Insert or replace, returning the old value. A full-table error preserves state.
    pub fn insert(&mut self, key: u64, value: u64) -> Result<Option<u64>, Full> {
        let hash = mix(key);
        let tag = Self::tag(hash);
        let mask = self.ctrl.len() - 1;
        let mut reusable = None;
        for step in 0..self.ctrl.len() {
            let i = (hash as usize).wrapping_add(step) & mask;
            let c = self.ctrl[i];
            if c == DELETED {
                reusable.get_or_insert(i);
            } else if c == EMPTY {
                reusable.get_or_insert(i);
                break;
            } else if (!FILTER || c == tag) && self.entries[i].0 == key {
                return Ok(Some(std::mem::replace(&mut self.entries[i].1, value)));
            }
        }
        let i = reusable.ok_or(Full)?;
        if self.ctrl[i] == DELETED {
            self.deleted -= 1;
        }
        self.entries[i] = (key, value);
        self.ctrl[i] = tag;
        self.len += 1;
        Ok(None)
    }

    /// Remove a key and leave a tombstone for later probe paths.
    pub fn remove(&mut self, key: u64) -> Option<u64> {
        let i = self.locate::<false>(key).0?;
        self.ctrl[i] = DELETED;
        self.len -= 1;
        self.deleted += 1;
        Some(self.entries[i].1)
    }

    /// Reinsert survivors at the same capacity; old and new arrays coexist temporarily.
    pub fn rebuild(&mut self) {
        let mut next = Self::new(self.ctrl.len());
        for (i, &c) in self.ctrl.iter().enumerate() {
            if c < EMPTY {
                let (k, v) = self.entries[i];
                next.insert(k, v).unwrap();
            }
        }
        *self = next;
    }

    /// Return live entries, deleted slots and physical slots.
    pub fn occupancy(&self) -> (usize, usize, usize) {
        (self.len, self.deleted, self.ctrl.len())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn collision_witness<const F: bool>() {
        let keys: Vec<_> = (0..10000).filter(|&k| mix(k) & 7 == 7).take(3).collect();
        let mut t = Table::<F>::new(8);
        for &k in &keys {
            t.insert(k, k + 10).unwrap();
        }
        assert_eq!(t.remove(keys[0]), Some(keys[0] + 10));
        assert_eq!(t.get(keys[2]), Some(keys[2] + 10));
        assert_eq!(t.insert(keys[2], 999), Ok(Some(keys[2] + 10)));
        assert_eq!(t.occupancy(), (2, 1, 8));
        assert_eq!(t.get(keys[2]), Some(999));
        t.rebuild();
        assert_eq!(t.occupancy(), (2, 0, 8));
        assert_eq!(t.get(keys[2]), Some(999));
    }

    #[test]
    fn collisions_wrap_and_upsert_after_tombstone() {
        collision_witness::<false>();
        collision_witness::<true>();
    }

    fn saturation<const F: bool>() {
        for slots in [1, 2, 8, 64] {
            let mut t = Table::<F>::new(slots);
            for k in 0..slots as u64 {
                t.insert(k, k).unwrap();
            }
            assert_eq!(t.insert(99999, 1), Err(Full));
            assert_eq!(t.get(99999), None);
            assert_eq!(t.stats(99999).probes, slots);
            assert_eq!(t.insert(0, 100), Ok(Some(0)));
            for k in 0..slots as u64 {
                assert!(t.remove(k).is_some());
            }
            assert_eq!(t.occupancy(), (0, slots, slots));
            assert_eq!(t.stats(99999).probes, slots);
            assert_eq!(t.insert(u64::MAX, 42), Ok(None));
            assert_eq!(t.get(u64::MAX), Some(42));
        }
    }
    #[test]
    fn full_and_all_deleted_terminate() {
        saturation::<false>();
        saturation::<true>();
    }

    fn differential<const F: bool>() {
        for seed in 1..=16_u64 {
            let mut t = Table::<F>::new(64);
            let mut oracle = BTreeMap::new();
            let mut state = seed;
            for step in 0..4000 {
                state = mix(state.wrapping_add(0x9e3779b97f4a7c15));
                let key = (state >> 8) % 96;
                match state % 5 {
                    0 | 1 => {
                        if oracle.len() == 64 && !oracle.contains_key(&key) {
                            assert_eq!(t.insert(key, state), Err(Full));
                        } else {
                            assert_eq!(t.insert(key, state), Ok(oracle.insert(key, state)));
                        }
                    }
                    2 => assert_eq!(t.remove(key), oracle.remove(&key)),
                    3 => assert_eq!(t.get(key), oracle.get(&key).copied()),
                    _ => {
                        if step % 23 == 0 {
                            t.rebuild();
                        }
                    }
                }
                assert_eq!(t.occupancy().0, oracle.len());
                for k in 0..96 {
                    assert_eq!(t.get(k), oracle.get(&k).copied());
                }
            }
        }
    }
    #[test]
    fn plain_matches_ordered_oracle() {
        differential::<false>();
    }
    #[test]
    fn filtered_matches_ordered_oracle() {
        differential::<true>();
    }

    #[test]
    fn fingerprints_reduce_comparisons_without_changing_probes() {
        let mut a = Table::<false>::new(1024);
        let mut b = Table::<true>::new(1024);
        for k in 0..896 {
            a.insert(k, k).unwrap();
            b.insert(k, k).unwrap();
        }
        let mut eq_a = 0;
        let mut eq_b = 0;
        for k in 1024..2048 {
            let x = a.stats(k);
            let y = b.stats(k);
            assert_eq!(x.probes, y.probes);
            eq_a += x.equalities;
            eq_b += y.equalities;
        }
        assert!(eq_b < eq_a);
    }
}
