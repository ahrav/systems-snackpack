//! A bounded metadata cache for one trusted authority epoch.
//!
//! The authority assigns one dense sequence number per mutation. A complete
//! batch covers `(from, to]`. This is NOT the etcd revision protocol: filtered
//! etcd watches can skip revisions and transactions can share a revision.
//! Invalid batches leave the cache unchanged. Publication to concurrent readers,
//! authentication, transport, history retention and epoch changes are out of scope.
//!
//! ```
//! use metadata_scalability::{Cache, Change};
//! let mut cache = Cache::new(vec![Some(7), None]);
//! cache.apply(0, 1, &[Change { key: 0, value: None }]).unwrap();
//! assert_eq!(cache.slots(), &[None, None]);
//! assert_eq!(cache.cursor(), 1);
//! ```

/// One put or deletion (`None`) in authority order.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Change {
    /// Slot in a fixed-size namespace.
    pub key: usize,
    /// New route identifier, or authoritative absence.
    pub value: Option<u64>,
}

/// A cache can be used only within its authority epoch.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Cache {
    slots: Vec<Option<u64>>,
    cursor: u64,
}

/// Failed synchronization without changing the old cache.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SyncError {
    /// The batch does not describe its claimed sequence or namespace.
    Malformed,
    /// Missing history requires an earlier batch or a fresh snapshot.
    Gap,
    /// A snapshot would rewind the consumer.
    StaleSnapshot,
}

impl Cache {
    /// Install an initial snapshot at sequence zero in a single authority epoch.
    pub fn new(slots: Vec<Option<u64>>) -> Self {
        Self { slots, cursor: 0 }
    }

    /// Current complete state through [`Self::cursor`].
    pub fn slots(&self) -> &[Option<u64>] {
        &self.slots
    }

    /// Last completely applied sequence, not a wall-clock freshness bound.
    pub fn cursor(&self) -> u64 {
        self.cursor
    }

    /// Apply a complete dense batch; ignore its already-applied prefix.
    ///
    /// Validate the entire batch before any mutation. Replays require the
    /// authority to assign immutable content to each sequence number.
    pub fn apply(&mut self, from: u64, to: u64, changes: &[Change]) -> Result<(), SyncError> {
        if to.checked_sub(from) != Some(changes.len() as u64)
            || changes.iter().any(|change| change.key >= self.slots.len())
        {
            return Err(SyncError::Malformed);
        }
        if from > self.cursor {
            return Err(SyncError::Gap);
        }
        if to <= self.cursor {
            return Ok(());
        }
        // cursor is inside [from, to), so this is bounded by changes.len().
        let skip = (self.cursor - from) as usize;
        for change in &changes[skip..] {
            self.slots[change.key] = change.value;
        }
        self.cursor = to;
        Ok(())
    }

    /// Replace the entire namespace with a consistent snapshot at `to`.
    ///
    /// This removes keys absent from the snapshot. Overlaying only its live
    /// keys would retain deleted routes. Equal revisions must mean equal state.
    pub fn install(&mut self, to: u64, snapshot: &[Option<u64>]) -> Result<(), SyncError> {
        if snapshot.len() != self.slots.len() {
            return Err(SyncError::Malformed);
        }
        if to < self.cursor {
            return Err(SyncError::StaleSnapshot);
        }
        self.slots.copy_from_slice(snapshot);
        self.cursor = to;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    fn change(key: usize, value: Option<u64>) -> Change {
        Change { key, value }
    }

    #[test]
    fn all_short_histories_match_independent_map_oracle() {
        // Exhaust all 4^6 histories: put/delete on each of two keys.
        for encoding in 0..4096_u64 {
            let mut code = encoding;
            let mut oracle = BTreeMap::new();
            let mut cache = Cache::new(vec![None; 2]);
            let mut events = Vec::new();
            for seq in 1..=6 {
                let op = code % 4;
                code /= 4;
                let key = (op / 2) as usize;
                let value = (op % 2 == 1).then_some(seq);
                if let Some(value) = value {
                    oracle.insert(key, value);
                } else {
                    oracle.remove(&key);
                }
                events.push(change(key, value));
                // Replay overlapping prefixes, not only fresh batches.
                cache.apply(0, seq, &events).unwrap();
                assert_eq!(cache.cursor(), seq);
                for key in 0..2 {
                    assert_eq!(cache.slots()[key], oracle.get(&key).copied());
                }
                let snapshot: Vec<_> = (0..2).map(|k| oracle.get(&k).copied()).collect();
                let mut full = Cache::new(vec![None; 2]);
                full.install(seq, &snapshot).unwrap();
                assert_eq!(full, cache);
            }
        }
    }

    #[test]
    fn gap_and_malformed_suffix_are_atomic() {
        let mut cache = Cache::new(vec![Some(10); 2]);
        let before = cache.clone();
        assert_eq!(cache.apply(1, 2, &[change(0, None)]), Err(SyncError::Gap));
        assert_eq!(cache, before);
        assert_eq!(
            cache.apply(0, 2, &[change(0, None), change(2, None)]),
            Err(SyncError::Malformed)
        );
        assert_eq!(cache, before);
        assert_eq!(
            cache.apply(0, 2, &[change(0, None)]),
            Err(SyncError::Malformed)
        );
        assert_eq!(cache, before);
        assert_eq!(cache.apply(2, 1, &[]), Err(SyncError::Malformed));
        assert_eq!(cache, before);
    }

    #[test]
    fn deletion_replay_cannot_resurrect_route() {
        let mut cache = Cache::new(vec![None]);
        cache.apply(0, 1, &[change(0, Some(7))]).unwrap();
        cache.apply(1, 2, &[change(0, None)]).unwrap();
        cache.apply(0, 1, &[change(0, Some(7))]).unwrap();
        assert_eq!(cache.slots(), &[None]);
        assert_eq!(cache.cursor(), 2);
    }

    #[test]
    fn snapshot_recovers_compaction_and_removes_absent_keys() {
        let mut cache = Cache::new(vec![Some(7), Some(8)]);
        assert_eq!(
            cache.apply(9, 10, &[change(1, Some(9))]),
            Err(SyncError::Gap)
        );
        cache.install(10, &[None, Some(9)]).unwrap();
        cache.apply(10, 11, &[change(0, Some(1))]).unwrap();
        let before = cache.clone();
        assert_eq!(
            cache.install(10, &[Some(7), Some(9)]),
            Err(SyncError::StaleSnapshot)
        );
        assert_eq!(cache, before);
        assert_eq!(cache.install(12, &[None]), Err(SyncError::Malformed));
        assert_eq!(cache, before);
    }

    #[test]
    fn empty_batches_and_sequence_ceiling() {
        let mut cache = Cache::new(vec![]);
        cache.apply(0, 0, &[]).unwrap();
        cache.install(u64::MAX, &[]).unwrap();
        cache.apply(u64::MAX, u64::MAX, &[]).unwrap();
        assert_eq!(cache.apply(u64::MAX, 0, &[]), Err(SyncError::Malformed));
    }
}
