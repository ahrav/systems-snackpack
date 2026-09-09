//! Deterministic models of resource fencing and joint-quorum arithmetic.
//!
//! This is not Raft, a lease clock, authentication, or persistent storage.
//! Each method call is one serialized transition. Real storage must atomically
//! enforce and persist the generation together with the protected effect.
//!
//! ```
//! use consensus_leases_fencing::FencedValue;
//! let mut invoice = FencedValue::default();
//! assert!(invoice.install(41));
//! assert!(invoice.write(41, 10));
//! assert!(invoice.install(42));
//! assert!(!invoice.write(41, 99));
//! assert!(invoice.write(42, 20));
//! assert_eq!(invoice.value(), 20);
//! ```

use std::collections::BTreeSet;

/// Whether a write names the installed, nonzero ownership generation.
///
/// Kept out of line for generated-code inspection. This predicate alone does
/// not synchronize a check with a later effect.
#[inline(never)]
pub fn accepts_generation(installed: u64, incoming: u64) -> bool {
    incoming != 0 && incoming == installed
}

/// One resource whose ownership and value change through serialized calls.
///
/// Generation zero means no owner. `install` accepts only trusted authority
/// input; it does not authenticate or independently verify a grant. Ownership
/// becomes active for this resource when installation is acknowledged.
/// Copying this value models a complete checkpoint, not a tested disk protocol.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct FencedValue {
    generation: u64,
    value: u64,
}

impl FencedValue {
    /// Install a strictly newer grant from the trusted ownership authority.
    ///
    /// Rejects repeats and regressions without changing state. A caller with
    /// an ambiguous installation outcome must reconcile it; `false` does not
    /// distinguish an already-installed generation from a superseded one.
    pub fn install(&mut self, generation: u64) -> bool {
        if generation <= self.generation {
            return false;
        }
        self.generation = generation;
        true
    }

    /// Accept a write only in the currently installed generation.
    ///
    /// Multiple writes in the same generation are allowed. This operation
    /// provides neither retry deduplication nor ordering within a generation.
    pub fn write(&mut self, generation: u64, value: u64) -> bool {
        if !accepts_generation(self.generation, generation) {
            return false;
        }
        self.value = value;
        true
    }

    /// Return the generation installed at this resource.
    pub fn generation(&self) -> u64 {
        self.generation
    }

    /// Return the most recently accepted value.
    pub fn value(&self) -> u64 {
        self.value
    }
}

/// Whether distinct acknowledgers contain a majority of the configured voters.
///
/// Inputs have set semantics. Repeated identifiers count once, outsiders count
/// zero, and an empty configuration never authorizes a decision. This checks
/// counts only, not log freshness, term, persistence, or configuration validity.
pub fn majority(config: &[u8], acknowledgers: &[u8]) -> bool {
    let voters: BTreeSet<_> = config.iter().copied().collect();
    let votes: BTreeSet<_> = acknowledgers.iter().copied().collect();
    !voters.is_empty() && voters.intersection(&votes).count() > voters.len() / 2
}

/// Whether acknowledgers contain a separate majority of both configurations.
///
/// The caller supplies the active joint configuration. This does not implement
/// the protocol that installs, commits, recovers, or leaves that configuration.
pub fn joint_majority(old: &[u8], new: &[u8], acknowledgers: &[u8]) -> bool {
    majority(old, acknowledgers) && majority(new, acknowledgers)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uninstalled_zero_and_future_writes_leave_state_unchanged() {
        let mut sink = FencedValue::default();
        let original = sink;
        for token in [0, 1, 41, u64::MAX] {
            assert!(!sink.write(token, 99));
            assert_eq!(sink, original);
        }
        assert!(sink.install(41));
        let installed = sink;
        assert!(!sink.write(42, 99));
        assert_eq!(sink, installed);
    }

    #[test]
    fn a_pause_after_a_valid_lease_check_cannot_bypass_the_sink() {
        let mut sink = FencedValue::default();
        assert!(sink.install(41));
        assert!(sink.write(41, 10));
        let check_ms = 90;
        let expiry_ms = 100;
        assert!(check_ms < expiry_ms);
        assert!(sink.install(42));
        assert!(sink.write(42, 20));
        assert!(!sink.write(41, 99));
        assert_eq!(sink.value(), 20);
    }

    #[test]
    fn installation_does_not_regress_or_wrap() {
        let mut sink = FencedValue::default();
        assert!(!sink.install(0));
        assert!(sink.install(42));
        for token in [0, 41, 42] {
            assert!(!sink.install(token));
            assert_eq!(sink.generation(), 42);
        }
        assert!(sink.install(u64::MAX));
        assert!(!sink.install(0));
        assert!(!sink.install(u64::MAX));
        assert_eq!(sink.generation(), u64::MAX);
    }

    #[test]
    fn old_writes_can_succeed_before_installation() {
        let mut sink = FencedValue::default();
        assert!(sink.install(41));
        // A grant of 42 elsewhere has not yet changed this resource.
        assert!(sink.write(41, 99));
        assert!(sink.install(42));
        assert!(sink.write(42, 20));
        assert_eq!(sink.value(), 20);
    }

    #[test]
    fn equal_generations_do_not_deduplicate_or_order_operations() {
        let mut sink = FencedValue::default();
        assert!(sink.install(42));
        assert!(sink.write(42, 20));
        assert!(sink.write(42, 99));
        assert_eq!(sink.value(), 99);
    }

    #[test]
    fn all_interleavings_with_successor_install_before_its_write() {
        // 0 = install 42, 1 = successor write, 2 = old write.
        for order in [[2, 0, 1], [0, 2, 1], [0, 1, 2]] {
            let mut sink = FencedValue::default();
            assert!(sink.install(41));
            let mut installed = false;
            for event in order {
                match event {
                    0 => {
                        assert!(sink.install(42));
                        installed = true;
                    }
                    1 => assert!(sink.write(42, 20)),
                    2 => assert_eq!(sink.write(41, 99), !installed),
                    _ => unreachable!(),
                }
            }
            assert_eq!(sink.value(), 20);
        }
    }

    #[test]
    fn checkpoint_preservation_and_reset_have_different_contracts() {
        let mut before = FencedValue::default();
        assert!(before.install(42));
        assert!(before.write(42, 20));
        let mut restored = before;
        assert!(!restored.write(41, 99));
        assert_eq!(restored, before);
        // Losing enforcement state allows a replayed old installation.
        let mut reset = FencedValue::default();
        assert!(reset.install(41));
        assert!(reset.write(41, 99));
    }

    #[test]
    fn separated_check_and_effect_is_a_counterexample() {
        let mut sink = FencedValue::default();
        assert!(sink.install(41));
        let previously_allowed = accepts_generation(sink.generation(), 41);
        assert!(sink.install(42));
        assert!(sink.write(42, 20));
        // Deliberately broken middleware writes without checking again.
        if previously_allowed {
            sink.value = 99;
        }
        assert_eq!(sink.value(), 99);
        assert_eq!(sink.generation(), 42);
    }

    #[test]
    fn duplicate_and_outside_votes_do_not_create_a_majority() {
        assert!(!majority(&[0, 1, 2], &[0, 0, 0, 9, 9]));
        assert!(majority(&[0, 1, 2], &[0, 1, 1]));
        assert!(!majority(&[], &[0, 1, 2]));
        assert!(!joint_majority(&[0], &[], &[0]));
    }

    #[test]
    fn majority_of_union_is_not_a_joint_majority() {
        assert!(majority(&[0, 1, 2, 3, 4], &[0, 1, 2]));
        assert!(!joint_majority(&[0, 1, 2], &[2, 3, 4], &[0, 1, 2]));
        assert!(joint_majority(&[0, 1, 2], &[2, 3, 4], &[1, 2, 3]));
    }

    #[test]
    fn exhaustive_five_voter_quorum_intersections() {
        let old = [0, 1, 2];
        let new = [2, 3, 4];
        let subsets: Vec<Vec<u8>> = (0_u32..32)
            .map(|mask| (0_u8..5).filter(|bit| mask & (1 << bit) != 0).collect())
            .collect();
        let mut unsafe_direct_pairs = 0;
        let mut checked_joint_pairs = 0;
        for left in &subsets {
            for right in &subsets {
                let intersects = left.iter().any(|v| right.contains(v));
                if majority(&old, left) && majority(&new, right) && !intersects {
                    unsafe_direct_pairs += 1;
                }
                if joint_majority(&old, &new, left)
                    && (majority(&old, right) || majority(&new, right))
                {
                    checked_joint_pairs += 1;
                    assert!(intersects, "left={left:?}, right={right:?}");
                }
            }
        }
        assert!(unsafe_direct_pairs > 0);
        assert!(checked_joint_pairs > 0);
    }
}
