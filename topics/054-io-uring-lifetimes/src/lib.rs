//! Models a userspace ledger that retains each `io_uring` request until every
//! applicable completion obligation is satisfied.
//!
//! # Independent completion identities
//!
//! A cancellation request and its target are separate operations with separate
//! completion queue entries (CQEs). Their arrival order does not prove whether
//! the target has retired. When a caller advances the generation before slot
//! reuse, a late CQE cannot match the newer operation in that slot.
//!
//! # Reclamation contract
//!
//! The target payload remains live until the target's terminal CQE arrives and
//! any tagged registered resource reports retirement. The cancellation CQE
//! does not gate target-payload reclamation, but it does gate removal of the
//! complete ledger entry. This distinction permits payload reclamation without
//! losing the outstanding cancellation correlation.
//!
//! This crate makes the state transitions executable without requiring Linux
//! or an `io_uring` library. It records completion results as opaque values;
//! completion identity and a terminal CQE, not the result code, discharge an
//! obligation.
//!
//! The ledger applies only when every modeled operation is configured to emit
//! its expected CQE. Do not use `IOSQE_CQE_SKIP_SUCCESS` on a target or cancel
//! SQE when a successful result would satisfy one of these obligations.
//! Operation tokens and resource-retirement tags share the CQE `user_data`
//! field. A real dispatcher must reserve disjoint namespaces for them before
//! calling the typed observation methods in this model.
//!
//! # Example
//!
//! ```
//! use std::num::NonZeroU64;
//! use io_uring_lifetimes::{OperationToken, RequestLifecycle, TargetCompletion};
//!
//! let target = OperationToken::new(7, 11);
//! let cancel = OperationToken::new(8, 3);
//! let resource_tag = NonZeroU64::new(44).unwrap();
//! let mut request = RequestLifecycle::submitted(target, Some(resource_tag));
//! request.request_cancel(cancel)?;
//!
//! // Completion order is not a correctness signal.
//! request.observe_cancel(cancel, 0)?;
//! assert!(!request.target_memory_reclaimable());
//! request.observe_target(target, -125, TargetCompletion::Terminal)?;
//! assert!(!request.target_memory_reclaimable());
//! request.observe_resource_retirement(resource_tag)?;
//! assert!(request.target_memory_reclaimable());
//! assert!(request.fully_retired());
//! # Ok::<(), io_uring_lifetimes::LifecycleError>(())
//! ```

use std::fmt;
use std::num::NonZeroU64;

/// A generation-qualified correlation key for an SQE or CQE `user_data` field.
///
/// A caller that reuses `slot` while an older token can remain in flight must
/// select another `generation` without wrapping back to that older value.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct OperationToken(u64);

impl OperationToken {
    /// Packs `generation` and `slot` into one nonzero token.
    ///
    /// # Panics
    ///
    /// Panics if both values are zero because zero is reserved for untracked
    /// completions in this model.
    #[must_use]
    pub const fn new(slot: u32, generation: u32) -> Self {
        let raw = ((generation as u64) << 32) | slot as u64;
        assert!(raw != 0, "operation token zero is reserved");
        Self(raw)
    }

    /// Returns the packed value written to `user_data`.
    #[must_use]
    pub const fn raw(self) -> u64 {
        self.0
    }

    /// Returns the reusable table slot carried by the token.
    #[must_use]
    pub const fn slot(self) -> u32 {
        self.0 as u32
    }

    /// Returns the generation that distinguishes reuse of the same slot.
    #[must_use]
    pub const fn generation(self) -> u32 {
        (self.0 >> 32) as u32
    }
}

/// A lifecycle transition that would lose completion correlation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LifecycleError {
    /// The cancel token equals the target token.
    ReusedTargetToken,
    /// A second cancel request was attached to the same target.
    CancelAlreadyRequested,
    /// A cancel CQE carried a token other than the submitted cancel token.
    WrongCancelToken,
    /// The cancel CQE was consumed more than once.
    DuplicateCancelCompletion,
    /// A target CQE carried a token other than the submitted target token.
    WrongTargetToken,
    /// The target terminal CQE was consumed more than once.
    DuplicateTargetCompletion,
    /// A resource-retirement CQE carried an unexpected tag.
    WrongResourceTag,
    /// The resource-retirement CQE was consumed more than once.
    DuplicateResourceRetirement,
}

impl fmt::Display for LifecycleError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::ReusedTargetToken => "cancel and target tokens must differ",
            Self::CancelAlreadyRequested => "cancel was already requested",
            Self::WrongCancelToken => "cancel completion token does not match",
            Self::DuplicateCancelCompletion => "cancel completion was already consumed",
            Self::WrongTargetToken => "target completion token does not match",
            Self::DuplicateTargetCompletion => "target completion was already consumed",
            Self::WrongResourceTag => "resource retirement tag does not match",
            Self::DuplicateResourceRetirement => {
                "resource retirement completion was already consumed"
            }
        };
        formatter.write_str(message)
    }
}

impl std::error::Error for LifecycleError {}

/// Completion records still required before a request leaves the driver ledger.
///
/// Each `true` field represents an outstanding record, not an observed event.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CompletionObligations {
    /// The target operation still owes its terminal CQE.
    pub target_terminal: bool,
    /// A submitted cancellation still owes its own CQE.
    pub cancel_terminal: bool,
    /// A replaced registered resource still owes its retirement CQE.
    pub resource_retirement: bool,
}

/// Whether a target CQE is terminal for its parent SQE.
///
/// Map a CQE with `IORING_CQE_F_MORE` to [`Self::More`]. Map a CQE without
/// that flag to [`Self::Terminal`]. A `More` CQE carries one result but leaves
/// the target operation armed and its terminal obligation outstanding. The
/// caller must derive this classification from CQE flags, not from `res`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TargetCompletion {
    /// `IORING_CQE_F_MORE` is set, so the parent SQE can produce another CQE.
    More,
    /// `IORING_CQE_F_MORE` is clear, so this CQE terminates the parent SQE.
    Terminal,
}

/// Tracks one target operation and its independent completion obligations.
///
/// Matching records may arrive in any order. Each obligation changes state at
/// most once; duplicate or mismatched records leave the lifecycle unchanged.
#[derive(Debug, Eq, PartialEq)]
pub struct RequestLifecycle {
    target: OperationToken,
    cancel: Option<OperationToken>,
    cancel_result: Option<i32>,
    target_result: Option<i32>,
    resource_tag: Option<NonZeroU64>,
    resource_retired: bool,
}

impl RequestLifecycle {
    /// Starts a request with one target obligation and an optional resource-retirement
    /// obligation.
    ///
    /// No cancellation obligation exists until [`Self::request_cancel`] succeeds.
    #[must_use]
    pub const fn submitted(target: OperationToken, resource_tag: Option<NonZeroU64>) -> Self {
        Self {
            target,
            cancel: None,
            cancel_result: None,
            target_result: None,
            resource_tag,
            resource_retired: false,
        }
    }

    /// Adds the independent completion obligation for an async-cancel SQE.
    ///
    /// This transition does not change the target or resource-retirement
    /// obligations.
    ///
    /// # Errors
    ///
    /// - [`LifecycleError::CancelAlreadyRequested`] if any cancel request is already
    ///   attached to the target. This check takes precedence over token reuse.
    /// - [`LifecycleError::ReusedTargetToken`] if `cancel` equals the target token.
    pub fn request_cancel(&mut self, cancel: OperationToken) -> Result<(), LifecycleError> {
        if self.cancel.is_some() {
            return Err(LifecycleError::CancelAlreadyRequested);
        }
        if cancel == self.target {
            return Err(LifecycleError::ReusedTargetToken);
        }
        self.cancel = Some(cancel);
        Ok(())
    }

    /// Consumes the cancel request's CQE without retiring the target.
    ///
    /// Any result code discharges the cancel obligation. The target CQE remains
    /// authoritative for target retirement.
    ///
    /// # Errors
    ///
    /// - [`LifecycleError::WrongCancelToken`] if `cancel` is not the token attached
    ///   by [`Self::request_cancel`].
    /// - [`LifecycleError::DuplicateCancelCompletion`] if the matching cancel CQE
    ///   was already consumed.
    pub fn observe_cancel(
        &mut self,
        cancel: OperationToken,
        result: i32,
    ) -> Result<(), LifecycleError> {
        if self.cancel != Some(cancel) {
            return Err(LifecycleError::WrongCancelToken);
        }
        if self.cancel_result.is_some() {
            return Err(LifecycleError::DuplicateCancelCompletion);
        }
        self.cancel_result = Some(result);
        Ok(())
    }

    /// Consumes one target CQE and retires the target only when it is terminal.
    ///
    /// [`TargetCompletion::More`] records no transition because the parent SQE
    /// remains armed. [`TargetCompletion::Terminal`] discharges the target
    /// obligation for any result code, including a cancellation result.
    ///
    /// # Errors
    ///
    /// - [`LifecycleError::WrongTargetToken`] if `target` differs from the submitted
    ///   target token.
    /// - [`LifecycleError::DuplicateTargetCompletion`] if the matching target CQE
    ///   was already consumed.
    pub fn observe_target(
        &mut self,
        target: OperationToken,
        result: i32,
        completion: TargetCompletion,
    ) -> Result<(), LifecycleError> {
        if target != self.target {
            return Err(LifecycleError::WrongTargetToken);
        }
        if self.target_result.is_some() {
            return Err(LifecycleError::DuplicateTargetCompletion);
        }
        if completion == TargetCompletion::Terminal {
            self.target_result = Some(result);
        }
        Ok(())
    }

    /// Consumes the registered resource's retirement CQE.
    ///
    /// # Errors
    ///
    /// - [`LifecycleError::WrongResourceTag`] if the request has no resource tag or
    ///   `tag` differs from it.
    /// - [`LifecycleError::DuplicateResourceRetirement`] if the matching retirement
    ///   CQE was already consumed.
    pub fn observe_resource_retirement(&mut self, tag: NonZeroU64) -> Result<(), LifecycleError> {
        if self.resource_tag != Some(tag) {
            return Err(LifecycleError::WrongResourceTag);
        }
        if self.resource_retired {
            return Err(LifecycleError::DuplicateResourceRetirement);
        }
        self.resource_retired = true;
        Ok(())
    }

    /// Returns the CQEs still required before the driver can erase this entry.
    ///
    /// A cancellation contributes an obligation only after
    /// [`Self::request_cancel`] succeeds.
    #[must_use]
    pub const fn obligations(&self) -> CompletionObligations {
        CompletionObligations {
            target_terminal: self.target_result.is_none(),
            cancel_terminal: self.cancel.is_some() && self.cancel_result.is_none(),
            resource_retirement: self.resource_tag.is_some() && !self.resource_retired,
        }
    }

    /// Returns whether the target payload and operation state can be reclaimed.
    ///
    /// A cancel CQE does not satisfy the target obligation. A tagged registered
    /// resource also requires its retirement CQE. An outstanding cancel CQE does
    /// not prevent target-payload reclamation after those two conditions hold.
    #[must_use]
    pub const fn target_memory_reclaimable(&self) -> bool {
        self.target_result.is_some() && (self.resource_tag.is_none() || self.resource_retired)
    }

    /// Returns whether target, cancel, and resource completions are all consumed.
    ///
    /// Unlike [`Self::target_memory_reclaimable`], this remains `false` while a
    /// submitted cancellation still owes its CQE.
    #[must_use]
    pub const fn fully_retired(&self) -> bool {
        let obligations = self.obligations();
        !obligations.target_terminal
            && !obligations.cancel_terminal
            && !obligations.resource_retirement
    }
}

/// Returns a checked completion-visibility bound in microseconds.
///
/// The model adds operation service, the longest gap between owner `GETEVENTS`
/// entries, and CQE drain time. Callers supply bounds for all three components;
/// this function does not measure them.
///
/// # Errors
///
/// Returns `None` if either checked addition exceeds [`u64::MAX`].
#[must_use]
pub const fn visible_completion_bound_us(
    operation_us: u64,
    owner_getevents_gap_us: u64,
    drain_us: u64,
) -> Option<u64> {
    match operation_us.checked_add(owner_getevents_gap_us) {
        Some(partial) => partial.checked_add(drain_us),
        None => None,
    }
}

/// Returns a checked power-of-two CQ size for an SQ and one completion burst.
///
/// The unrounded requirement is
/// `ceil(burst_cqes_per_second * drain_interval_us / 1_000_000) + extra_cqes + safety_margin`.
/// `extra_cqes` accounts for completion fan-out such as cancellation, links,
/// notifications, and multishot operations. The result is at least
/// `sq_entries` rounded up to a power of two, because an explicit Linux CQ
/// cannot be smaller than the final rounded SQ.
///
/// # Errors
///
/// Returns `None` if `sq_entries` is zero, the multiplication, ceiling
/// adjustment, or either addition exceeds [`u64::MAX`], or either next power
/// of two is not representable as a `u64`.
#[must_use]
pub const fn required_cq_entries(
    sq_entries: u64,
    burst_cqes_per_second: u64,
    drain_interval_us: u64,
    extra_cqes: u64,
    safety_margin: u64,
) -> Option<u64> {
    if sq_entries == 0 {
        return None;
    }
    let rounded_sq = match sq_entries.checked_next_power_of_two() {
        Some(value) => value,
        None => return None,
    };
    let product = match burst_cqes_per_second.checked_mul(drain_interval_us) {
        Some(value) => value,
        None => return None,
    };
    let base = match product.checked_add(999_999) {
        Some(value) => value / 1_000_000,
        None => return None,
    };
    let required = match base.checked_add(extra_cqes) {
        Some(value) => value,
        None => return None,
    };
    let required = match required.checked_add(safety_margin) {
        Some(value) => value,
        None => return None,
    };
    let rounded_burst = match required.checked_next_power_of_two() {
        Some(value) => value,
        None => return None,
    };
    Some(if rounded_sq > rounded_burst {
        rounded_sq
    } else {
        rounded_burst
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn token(slot: u32, generation: u32) -> OperationToken {
        OperationToken::new(slot, generation)
    }

    fn resource_tag(value: u64) -> NonZeroU64 {
        NonZeroU64::new(value).unwrap()
    }

    #[test]
    fn cancel_completion_never_retires_target() {
        let target = token(1, 9);
        let cancel = token(2, 4);
        let mut request = RequestLifecycle::submitted(target, None);
        request.request_cancel(cancel).unwrap();
        request.observe_cancel(cancel, 0).unwrap();

        assert!(!request.target_memory_reclaimable());
        assert_eq!(
            request.obligations(),
            CompletionObligations {
                target_terminal: true,
                cancel_terminal: false,
                resource_retirement: false,
            }
        );

        request
            .observe_target(target, -125, TargetCompletion::Terminal)
            .unwrap();
        assert!(request.target_memory_reclaimable());
        assert!(request.fully_retired());
    }

    #[test]
    fn target_can_complete_before_cancel_request() {
        let target = token(7, 3);
        let cancel = token(8, 3);
        let mut request = RequestLifecycle::submitted(target, None);
        request.request_cancel(cancel).unwrap();
        request
            .observe_target(target, 4096, TargetCompletion::Terminal)
            .unwrap();

        assert!(request.target_memory_reclaimable());
        assert!(!request.fully_retired());

        request.observe_cancel(cancel, -2).unwrap();
        assert!(request.fully_retired());
    }

    #[test]
    fn registered_resource_requires_retirement() {
        let target = token(10, 1);
        let tag = resource_tag(44);
        let mut request = RequestLifecycle::submitted(target, Some(tag));
        request
            .observe_target(target, 0, TargetCompletion::Terminal)
            .unwrap();
        assert!(!request.target_memory_reclaimable());

        request.observe_resource_retirement(tag).unwrap();
        assert!(request.target_memory_reclaimable());
        assert!(request.fully_retired());
    }

    #[test]
    fn multishot_more_cqe_never_retires_target() {
        let target = token(11, 1);
        let mut request = RequestLifecycle::submitted(target, None);

        request
            .observe_target(target, 128, TargetCompletion::More)
            .unwrap();
        request
            .observe_target(target, 256, TargetCompletion::More)
            .unwrap();
        assert!(request.obligations().target_terminal);
        assert!(!request.target_memory_reclaimable());

        request
            .observe_target(target, 0, TargetCompletion::Terminal)
            .unwrap();
        assert!(request.target_memory_reclaimable());
    }

    #[test]
    fn generation_changes_raw_identity() {
        let old = token(12, 4);
        let new = token(12, 5);
        assert_eq!(old.slot(), new.slot());
        assert_ne!(old, new);
        assert_ne!(old.raw(), new.raw());
    }

    #[test]
    fn rejects_duplicate_or_mismatched_records() {
        let target = token(1, 1);
        let cancel = token(2, 1);
        let tag = resource_tag(9);
        let mut request = RequestLifecycle::submitted(target, Some(tag));
        request.request_cancel(cancel).unwrap();
        assert_eq!(
            request.request_cancel(token(3, 1)),
            Err(LifecycleError::CancelAlreadyRequested)
        );
        assert_eq!(
            request.request_cancel(target),
            Err(LifecycleError::CancelAlreadyRequested)
        );
        assert_eq!(
            request.observe_target(token(9, 9), 0, TargetCompletion::Terminal),
            Err(LifecycleError::WrongTargetToken)
        );
        request
            .observe_target(target, 0, TargetCompletion::Terminal)
            .unwrap();
        assert_eq!(
            request.observe_target(target, 0, TargetCompletion::Terminal),
            Err(LifecycleError::DuplicateTargetCompletion)
        );
        assert_eq!(
            request.observe_resource_retirement(resource_tag(8)),
            Err(LifecycleError::WrongResourceTag)
        );
    }

    #[test]
    fn cost_models_match_running_example() {
        assert_eq!(visible_completion_bound_us(200, 500, 50), Some(750));
        assert_eq!(required_cq_entries(128, 50_000, 2_000, 24, 32), Some(256));
    }

    #[test]
    fn cq_size_never_undersizes_rounded_sq() {
        assert_eq!(required_cq_entries(300, 0, 0, 0, 0), Some(512));
        assert_eq!(required_cq_entries(0, 50_000, 2_000, 24, 32), None);
    }

    #[test]
    fn cost_models_fail_closed_on_overflow() {
        assert_eq!(visible_completion_bound_us(u64::MAX, 1, 0), None);
        assert_eq!(required_cq_entries(8, u64::MAX, 2, 0, 0), None);
        assert_eq!(required_cq_entries(u64::MAX, 1, 1, 0, 0), None);
    }
}
