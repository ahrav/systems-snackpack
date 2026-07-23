//! Validation and derived metrics for page-fault experiments.
//!
//! Linux minor and major faults are accounting classes, not fixed-cost events.
//! This crate keeps measured counters separate from derived ratios and rejects
//! cold-file observations that lack residency and process-level fault evidence.

/// One process-level touch observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Observation {
    /// Number of base pages in the mapping.
    pub pages: u64,
    /// Nanoseconds inside the sparse touch loop.
    pub touch_ns: u64,
    /// Minor-fault delta across the touch loop.
    pub minor_faults: u64,
    /// Major-fault delta across the touch loop.
    pub major_faults: u64,
    /// Pages resident immediately before the touch loop.
    pub resident_before: u64,
    /// Pages resident immediately after the touch loop.
    pub resident_after: u64,
}

/// Reasons a claimed cold-file observation is invalid.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ColdValidationError {
    /// A zero-page mapping cannot exercise page-granular access.
    EmptyMapping,
    /// At least one backing page was resident before the timed access.
    ResidentBeforeTouch,
    /// The touch loop did not leave the full mapping resident.
    IncompleteResidencyAfterTouch,
    /// The process major-fault counter did not increase during the touch phase.
    NoMajorFault,
}

/// Validates the evidence required to label a file-mapping process cold.
///
/// This check is intentionally narrower than device-cache coldness. It requires
/// caller-supplied fields that report zero pre-touch residency, full post-touch
/// residency, and a nonzero process major-fault delta. `RUSAGE_SELF` has no
/// address attribution, so the end-to-end runner uses an isolated
/// single-threaded workload to associate that delta with the touch phase.
///
/// # Errors
///
/// Returns one [`ColdValidationError`] for the first missing condition.
pub fn validate_cold_file(observation: Observation) -> Result<(), ColdValidationError> {
    if observation.pages == 0 {
        return Err(ColdValidationError::EmptyMapping);
    }
    if observation.resident_before != 0 {
        return Err(ColdValidationError::ResidentBeforeTouch);
    }
    if observation.resident_after != observation.pages {
        return Err(ColdValidationError::IncompleteResidencyAfterTouch);
    }
    if observation.major_faults == 0 {
        return Err(ColdValidationError::NoMajorFault);
    }
    Ok(())
}

/// Returns the touch-phase time divided by completed fault count.
///
/// The result is an amortized phase metric, not page-fault handler latency.
/// Readahead, fault-around, off-CPU I/O wait, and work shared across pages all
/// prevent that interpretation.
pub fn amortized_ns_per_fault(observation: Observation) -> Option<f64> {
    let faults = observation
        .minor_faults
        .checked_add(observation.major_faults)?;
    if faults == 0 {
        return None;
    }
    Some(observation.touch_ns as f64 / faults as f64)
}

/// Returns the observed completed-fault count per touched base page.
///
/// Values below one can arise when one file fault installs several ready PTEs.
/// Values above one remain possible across repeated protection or residency
/// transitions. Process-wide counters can also include unrelated faults, so
/// this ratio is descriptive rather than a VM invariant.
pub fn faults_per_page(observation: Observation) -> Option<f64> {
    if observation.pages == 0 {
        return None;
    }
    let faults = observation
        .minor_faults
        .checked_add(observation.major_faults)?;
    Some(faults as f64 / observation.pages as f64)
}

/// Returns the eight-block order-balanced process schedule.
///
/// Every mode occupies each ordinal position twice. A fresh process executes
/// each element, making the block the pairing unit and the process the
/// replication unit.
pub const fn balanced_schedule() -> [[&'static str; 4]; 8] {
    [
        ["anon-first", "anon-refault", "file-warm", "file-cold"],
        ["anon-refault", "file-warm", "file-cold", "anon-first"],
        ["file-warm", "file-cold", "anon-first", "anon-refault"],
        ["file-cold", "anon-first", "anon-refault", "file-warm"],
        ["file-cold", "file-warm", "anon-refault", "anon-first"],
        ["anon-first", "file-cold", "file-warm", "anon-refault"],
        ["anon-refault", "anon-first", "file-cold", "file-warm"],
        ["file-warm", "anon-refault", "anon-first", "file-cold"],
    ]
}

/// Reports whether a schedule satisfies the order-balance contract.
///
/// A balanced schedule places all four modes in every block and places every
/// mode in each ordinal position exactly twice. Both conditions are required:
/// position balance alone admits blocks that repeat a mode.
pub fn schedule_is_order_balanced(schedule: &[[&'static str; 4]; 8]) -> bool {
    let modes = ["anon-first", "anon-refault", "file-warm", "file-cold"];
    let blocks_complete = schedule
        .iter()
        .all(|block| modes.iter().all(|mode| block.contains(mode)));
    let positions_balanced = modes.iter().all(|mode| {
        (0..4).all(|position| {
            schedule
                .iter()
                .filter(|block| block[position] == *mode)
                .count()
                == 2
        })
    });
    blocks_complete && positions_balanced
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cold() -> Observation {
        Observation {
            pages: 8_192,
            touch_ns: 4_000_000_000,
            minor_faults: 0,
            major_faults: 8_192,
            resident_before: 0,
            resident_after: 8_192,
        }
    }

    #[test]
    fn cold_validation_requires_each_observable_condition() {
        assert_eq!(validate_cold_file(cold()), Ok(()));

        let cases = [
            (
                Observation { pages: 0, ..cold() },
                ColdValidationError::EmptyMapping,
            ),
            (
                Observation {
                    resident_before: 1,
                    ..cold()
                },
                ColdValidationError::ResidentBeforeTouch,
            ),
            (
                Observation {
                    resident_after: 8_191,
                    ..cold()
                },
                ColdValidationError::IncompleteResidencyAfterTouch,
            ),
            (
                Observation {
                    major_faults: 0,
                    ..cold()
                },
                ColdValidationError::NoMajorFault,
            ),
        ];

        for (observation, expected) in cases {
            assert_eq!(validate_cold_file(observation), Err(expected));
        }
    }

    #[test]
    fn ratios_remain_derived_metrics() {
        let observation = Observation {
            pages: 8_192,
            touch_ns: 512_000,
            minor_faults: 512,
            major_faults: 0,
            resident_before: 8_192,
            resident_after: 8_192,
        };
        assert_eq!(faults_per_page(observation), Some(0.0625));
        assert_eq!(amortized_ns_per_fault(observation), Some(1_000.0));
        assert_eq!(
            amortized_ns_per_fault(Observation {
                minor_faults: 0,
                ..observation
            }),
            None
        );
    }

    #[test]
    fn schedule_balances_modes_and_positions() {
        let schedule = balanced_schedule();
        let modes = ["anon-first", "anon-refault", "file-warm", "file-cold"];
        for mode in modes {
            for position in 0..4 {
                assert_eq!(
                    schedule
                        .iter()
                        .filter(|order| order[position] == mode)
                        .count(),
                    2
                );
            }
        }
    }

    #[test]
    fn balance_validator_accepts_the_schedule_and_rejects_violations() {
        assert!(schedule_is_order_balanced(&balanced_schedule()));

        // Repeating a mode within a block keeps position counts plausible in
        // that block yet must fail the block-completeness condition.
        let mut duplicated_mode = balanced_schedule();
        duplicated_mode[0] = ["anon-first", "anon-first", "file-warm", "file-cold"];
        assert!(!schedule_is_order_balanced(&duplicated_mode));

        // Swapping two positions in one block preserves completeness yet must
        // fail the position-balance condition.
        let mut unbalanced_positions = balanced_schedule();
        unbalanced_positions[0] = ["anon-refault", "anon-first", "file-warm", "file-cold"];
        assert!(!schedule_is_order_balanced(&unbalanced_positions));
    }
}
