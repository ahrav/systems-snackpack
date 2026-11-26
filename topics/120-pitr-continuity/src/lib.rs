//! Check recovery coverage on one timeline at whole-segment boundaries.
//! The caller supplies verified base backups and readable WAL from the same cluster.
//!
//! ```
//! use std::collections::BTreeSet;
//! use topic120_pitr_continuity::Base;
//! let archive = BTreeSet::from([10, 11, 13]);
//! let backup = Base { first: 10, consistent: 11 };
//! assert!(backup.reaches(11, &archive));
//! assert!(!backup.reaches(13, &archive));
//! ```
use std::collections::BTreeSet;

/// The segment range needed to make a physical base backup consistent.
#[derive(Clone, Copy)]
pub struct Base {
    /// Segment containing the first required WAL record.
    pub first: u32,
    /// Segment ending at the earliest selectable target in this model.
    pub consistent: u32,
}

impl Base {
    /// Checks whether replay can reach the end of `target`.
    pub fn reaches(self, target: u32, wal: &BTreeSet<u32>) -> bool {
        self.first <= self.consistent
            && self.consistent <= target
            && (self.first..=target).all(|segment| wal.contains(&segment))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compare_with_forward_replay() {
        // Replay one record per segment until a read fails. Record every
        // observable consistent state, then compare the planner at every target.
        for mask in 0..256u32 {
            let wal = (10..18).filter(|s| mask & (1 << (s - 10)) != 0).collect();
            for first in 10..18 {
                for consistent in first..18 {
                    let base = Base { first, consistent };
                    let mut reached = BTreeSet::new();
                    let mut next = first;
                    while next < 18 && mask & (1 << (next - 10)) != 0 {
                        if next >= consistent {
                            reached.insert(next);
                        }
                        next += 1;
                    }
                    for target in 9..=18 {
                        assert_eq!(base.reaches(target, &wal), reached.contains(&target));
                    }
                }
            }
        }
    }

    #[test]
    fn rejects_reversed_base() {
        let base = Base {
            first: 11,
            consistent: 10,
        };
        assert!(!base.reaches(11, &BTreeSet::from([10, 11])));
    }
}
