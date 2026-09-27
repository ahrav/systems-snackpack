//! Executable boundaries for single-key LSM version reclamation and compaction debt.
//!
//! This is an accounting and visibility model, not a storage engine. It excludes
//! range tombstones, merge operands, transactions, persistence, and concurrent
//! compaction installation. Byte counts share one uncompressed modeling boundary.
//!
//! ```
//! use lsm_compaction_economics::{Version, compact, read};
//! let versions = vec![Version { sequence: 10, value: Some(100) },
//!                     Version { sequence: 30, value: None }];
//! let retained = compact(versions, 15, false).unwrap();
//! assert_eq!(read(&retained, 15), Some(100));
//! assert_eq!(read(&retained, 30), None);
//! ```

/// One version of the single modeled key. `None` is a point tombstone.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Version {
    /// Unique order number within this key's history.
    pub sequence: u64,
    /// Value, or a deletion marker that hides older values.
    pub value: Option<u64>,
}

/// Retain versions needed by reads at or after `oldest_snapshot`.
///
/// All inputs belong to one key and must have unique sequence numbers.
/// `older_outside` must be true if any older value can remain outside the input.
/// False therefore requires proof of complete older-version coverage. The
/// caller must synchronize snapshot capture and file publication in a real
/// engine. This function models neither obligation.
///
/// Keeps every version above the floor and the first at or below it, unless
/// that boundary entry is a tombstone with complete older-version coverage.
/// Returns an error for ambiguous duplicate sequence numbers.
#[inline(never)]
pub fn compact(
    mut versions: Vec<Version>,
    oldest_snapshot: u64,
    older_outside: bool,
) -> Result<Vec<Version>, &'static str> {
    versions.sort_by_key(|version| std::cmp::Reverse(version.sequence));
    if versions
        .windows(2)
        .any(|pair| pair[0].sequence == pair[1].sequence)
    {
        return Err("duplicate sequence number");
    }
    let mut reached_floor = false;
    versions.retain(|version| {
        if reached_floor {
            return false;
        }
        if version.sequence <= oldest_snapshot {
            reached_floor = true;
            if version.value.is_none() && !older_outside {
                return false;
            }
        }
        true
    });
    Ok(versions)
}

/// Read the modeled key at `snapshot`, with deletion and absence both returning `None`.
///
/// The supplied versions must have unique sequence numbers and belong to one key.
pub fn read(versions: &[Version], snapshot: u64) -> Option<u64> {
    versions
        .iter()
        .filter(|version| version.sequence <= snapshot)
        .max_by_key(|version| version.sequence)
        .and_then(|version| version.value)
}

/// Transfer work for one compaction job at a single byte-accounting boundary.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Job {
    /// Incoming sorted-table bytes read.
    pub incoming: u64,
    /// Existing destination bytes read, including whole-file overlap.
    pub overlap: u64,
    /// New table bytes written. This excludes WAL and device-internal writes.
    pub output: u64,
}

impl Job {
    /// Combined input-read and output-write bytes, or `None` on overflow.
    pub fn transfer_bytes(self) -> Option<u64> {
        self.incoming
            .checked_add(self.overlap)?
            .checked_add(self.output)
    }
}

/// Debt after one interval, measured in remaining compaction transfer bytes.
///
/// `updates` is accepted update bytes during the interval, `work_per_update` is
/// an assumed integer transfer-byte multiplier, and `service` is available
/// transfer-byte service during the interval. Surplus service is not banked.
/// This is a fluid approximation: arrivals are assumed available for service
/// within the interval. It does not model event ordering or engine counters.
/// Returns `None` if the final debt cannot be represented as `u64`.
#[inline(never)]
pub fn next_debt(debt: u64, updates: u64, work_per_update: u64, service: u64) -> Option<u64> {
    let work = u128::from(debt) + u128::from(updates) * u128::from(work_per_update);
    u64::try_from(work.saturating_sub(u128::from(service))).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn history() -> Vec<Version> {
        vec![
            Version {
                sequence: 10,
                value: Some(100),
            },
            Version {
                sequence: 20,
                value: Some(120),
            },
            Version {
                sequence: 30,
                value: None,
            },
        ]
    }

    #[test]
    fn pinned_snapshot_requires_older_value() {
        let result = compact(history(), 15, false).unwrap();
        assert_eq!(result.len(), 3);
        assert_eq!(read(&result, 15), Some(100));
        assert_eq!(read(&result, 30), None);
    }

    #[test]
    fn outside_version_requires_tombstone() {
        let result = compact(history(), 30, true).unwrap();
        assert_eq!(result, vec![history()[2]]);
        let outside = history()[0];
        assert_eq!(read(&[outside], 30), Some(100)); // Deliberately unsafe control.
        assert_eq!(read(&[outside, result[0]], 30), None);
        assert!(compact(history(), 30, false).unwrap().is_empty());
    }

    #[test]
    fn every_snapshot_from_floor_is_preserved() {
        // Exhaust all value/tombstone patterns, floors, reads, and outside states.
        for mask in 0..8 {
            let original: Vec<_> = (0..3)
                .map(|i| Version {
                    sequence: (i + 1) * 10,
                    value: (mask & (1 << i) != 0).then_some(i + 100),
                })
                .collect();
            for floor in 0..=40 {
                for older_outside in [false, true] {
                    let mut before = original.clone();
                    let mut after = compact(original.clone(), floor, older_outside).unwrap();
                    if older_outside {
                        let outside = Version {
                            sequence: 5,
                            value: Some(99),
                        };
                        before.push(outside);
                        after.push(outside);
                    }
                    for snapshot in floor..=40 {
                        assert_eq!(
                            read(&before, snapshot),
                            read(&after, snapshot),
                            "mask={mask} floor={floor} snapshot={snapshot} outside={older_outside}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn input_order_does_not_change_result() {
        let versions = history();
        for order in [
            [0, 1, 2],
            [0, 2, 1],
            [1, 0, 2],
            [1, 2, 0],
            [2, 0, 1],
            [2, 1, 0],
        ] {
            let input = order.map(|index| versions[index]).to_vec();
            for floor in [0, 10, 15, 20, 30, 40] {
                assert_eq!(
                    compact(input.clone(), floor, true),
                    compact(versions.clone(), floor, true)
                );
            }
        }
    }

    #[test]
    fn empty_and_ambiguous_inputs() {
        assert_eq!(compact(Vec::new(), 0, false), Ok(Vec::new()));
        assert_eq!(read(&[], 0), None);
        assert!(compact(vec![history()[0]; 2], 15, false).is_err());
    }

    #[test]
    fn job_counts_both_read_inputs_and_output() {
        const MIB: u64 = 1 << 20;
        assert_eq!(
            Job {
                incoming: 64 * MIB,
                overlap: 256 * MIB,
                output: 288 * MIB
            }
            .transfer_bytes(),
            Some(608 * MIB)
        );
        assert_eq!(
            Job {
                incoming: u64::MAX,
                overlap: 1,
                output: 0
            }
            .transfer_bytes(),
            None
        );
    }

    #[test]
    fn debt_growth_drain_and_overflow() {
        assert_eq!(next_debt(400, 10, 8, 60), Some(420));
        assert_eq!(next_debt(400, 10, 8, 100), Some(380));
        assert_eq!(next_debt(1, 0, 8, 60), Some(0));
        assert_eq!(next_debt(u64::MAX, 1, 1, 1), Some(u64::MAX));
        assert_eq!(next_debt(u64::MAX, u64::MAX, u64::MAX, 0), None);
    }
}
