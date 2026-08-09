//! In-memory model of an idempotency receipt state machine.
//!
//! One caller key identifies one logical intent. [`IdempotencyStore::begin`]
//! conditionally claims an absent key, rejects a changed fingerprint, reports a
//! retained in-progress generation, or replays a completed resource.
//! [`IdempotencyStore::complete`]
//! changes the modeled business effect and replay receipt under one lock.
//!
//! # Model boundary
//!
//! The lock models one serializable local transaction. The crate does not
//! implement persistence, a database, networking, deadlines, authorization,
//! expiry clocks, or an external side effect. Deterministic split-write helpers
//! expose the two crash windows that a real atomic commit must close.

use std::collections::HashMap;
use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::sync::Mutex;

/// Validation value compared for exact equality under one caller key.
///
/// A differing value rejects reuse of a retained key. Equal values do not prove
/// that two request payloads are equal or share one intent.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RequestFingerprint(pub u64);

/// Identifier retained in a completed receipt and replayed for matching retries.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResourceId(pub u64);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum RecordStatus {
    InProgress,
    Complete(ResourceId),
}

#[derive(Debug)]
struct Record {
    fingerprint: RequestFingerprint,
    generation: u64,
    status: RecordStatus,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct Effect {
    key: String,
    resource: ResourceId,
}

#[derive(Debug, Default)]
struct Inner {
    records: HashMap<String, Record>,
    effects: Vec<Effect>,
    next_generation: u64,
    next_resource: u64,
}

/// Proof that one claim owns a specific generation of a key.
///
/// Cloning a ticket does not create another generation. A takeover changes the
/// retained generation and fences every ticket from the previous generation.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompletionTicket {
    key: String,
    generation: u64,
}

/// Result of looking up or conditionally claiming one caller key.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum BeginResult {
    /// The caller owns the in-progress generation and may perform the effect.
    Owner(CompletionTicket),
    /// The matching request has a retained in-progress generation.
    InProgress,
    /// The matching request completed and retained this resource identifier.
    Replay(ResourceId),
    /// The retained key belongs to different request parameters.
    ParameterMismatch,
    /// The model cannot allocate another ownership generation.
    CounterOverflow,
}

/// Error returned when a ticket cannot complete its request.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CompleteError {
    /// A takeover replaced the ticket's generation.
    StaleOwner,
    /// The key already reached `COMPLETE`.
    AlreadyComplete,
    /// This store has no retained record for the ticket's key.
    MissingKey,
    /// The resource identifier counter reached [`u64::MAX`].
    CounterOverflow,
}

impl Display for CompleteError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::StaleOwner => "stale owner generation",
            Self::AlreadyComplete => "request already complete",
            Self::MissingKey => "request key is absent",
            Self::CounterOverflow => "model counter overflow",
        })
    }
}

impl Error for CompleteError {}

/// Error returned when the deterministic expiry model cannot transfer ownership.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TakeoverError {
    /// The retained key belongs to different request parameters.
    ParameterMismatch,
    /// The request already reached `COMPLETE`.
    AlreadyComplete,
    /// The key is absent.
    MissingKey,
    /// The generation counter reached [`u64::MAX`].
    CounterOverflow,
}

impl Display for TakeoverError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::ParameterMismatch => "request fingerprint changed",
            Self::AlreadyComplete => "request already complete",
            Self::MissingKey => "request key is absent",
            Self::CounterOverflow => "model generation overflow",
        })
    }
}

impl Error for TakeoverError {}

/// Thread-safe receipt and effect model for one process.
///
/// The model scopes keys only by their supplied string. It does not represent a
/// tenant or principal, operation, or service scope. Records and effects remain
/// retained for the store's lifetime; takeover changes ownership without
/// deleting the record.
#[derive(Debug, Default)]
pub struct IdempotencyStore {
    inner: Mutex<Inner>,
}

impl IdempotencyStore {
    /// Creates an empty model.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Claims an absent key or reports the matching retained state.
    ///
    /// An absent key receives [`BeginResult::Owner`] when another generation
    /// can be allocated. Matching calls receive [`BeginResult::InProgress`]
    /// until the retained generation completes. A completed retry receives the
    /// original [`ResourceId`]. Only an absent key consumes a generation.
    #[must_use]
    pub fn begin(&self, key: impl Into<String>, fingerprint: RequestFingerprint) -> BeginResult {
        let key = key.into();
        let mut inner = self
            .inner
            .lock()
            .unwrap_or_else(|poison| poison.into_inner());
        if let Some(record) = inner.records.get(&key) {
            if record.fingerprint != fingerprint {
                return BeginResult::ParameterMismatch;
            }
            return match record.status {
                RecordStatus::InProgress => BeginResult::InProgress,
                RecordStatus::Complete(resource) => BeginResult::Replay(resource),
            };
        }

        let Some(generation) = inner.next_generation.checked_add(1) else {
            return BeginResult::CounterOverflow;
        };
        inner.next_generation = generation;
        inner.records.insert(
            key.clone(),
            Record {
                fingerprint,
                generation,
                status: RecordStatus::InProgress,
            },
        );
        BeginResult::Owner(CompletionTicket { key, generation })
    }

    /// Transfers an in-progress key to a newer modeled generation.
    ///
    /// This method injects expiry deterministically; it does not read a clock.
    /// The returned ticket fences every older ticket for the key.
    ///
    /// # Errors
    ///
    /// - [`TakeoverError::MissingKey`] if this store has no record for `key`.
    /// - [`TakeoverError::ParameterMismatch`] if the retained fingerprint differs.
    /// - [`TakeoverError::AlreadyComplete`] if the matching request completed.
    /// - [`TakeoverError::CounterOverflow`] if another generation cannot be allocated.
    ///
    /// Every error leaves the retained record unchanged.
    pub fn take_over(
        &self,
        key: &str,
        fingerprint: RequestFingerprint,
    ) -> Result<CompletionTicket, TakeoverError> {
        let mut inner = self
            .inner
            .lock()
            .unwrap_or_else(|poison| poison.into_inner());
        let record = inner.records.get(key).ok_or(TakeoverError::MissingKey)?;
        if record.fingerprint != fingerprint {
            return Err(TakeoverError::ParameterMismatch);
        }
        if matches!(record.status, RecordStatus::Complete(_)) {
            return Err(TakeoverError::AlreadyComplete);
        }
        let generation = inner
            .next_generation
            .checked_add(1)
            .ok_or(TakeoverError::CounterOverflow)?;
        inner.next_generation = generation;
        inner
            .records
            .get_mut(key)
            .expect("record was checked")
            .generation = generation;
        Ok(CompletionTicket {
            key: key.to_owned(),
            generation,
        })
    }

    /// Commits one modeled effect and its replay receipt under one lock.
    ///
    /// # Errors
    ///
    /// - [`CompleteError::MissingKey`] if this store has no record for the ticket's key.
    /// - [`CompleteError::StaleOwner`] if the retained generation differs from the ticket.
    /// - [`CompleteError::AlreadyComplete`] if that generation already completed.
    /// - [`CompleteError::CounterOverflow`] if another resource identifier cannot be allocated.
    ///
    /// Every error leaves both the effect list and retained record unchanged.
    pub fn complete(&self, ticket: CompletionTicket) -> Result<ResourceId, CompleteError> {
        let mut inner = self
            .inner
            .lock()
            .unwrap_or_else(|poison| poison.into_inner());
        let record = inner
            .records
            .get(&ticket.key)
            .ok_or(CompleteError::MissingKey)?;
        if record.generation != ticket.generation {
            return Err(CompleteError::StaleOwner);
        }
        if matches!(record.status, RecordStatus::Complete(_)) {
            return Err(CompleteError::AlreadyComplete);
        }

        let next = inner
            .next_resource
            .checked_add(1)
            .ok_or(CompleteError::CounterOverflow)?;
        let resource = ResourceId(next);
        inner.next_resource = next;
        inner.effects.push(Effect {
            key: ticket.key.clone(),
            resource,
        });
        inner
            .records
            .get_mut(&ticket.key)
            .expect("record was checked")
            .status = RecordStatus::Complete(resource);
        Ok(resource)
    }

    /// Counts appended business effects; claims, replays, and rejected completions add none.
    #[must_use]
    pub fn effect_count(&self) -> usize {
        self.inner
            .lock()
            .unwrap_or_else(|poison| poison.into_inner())
            .effects
            .len()
    }

    /// Checks the receipt-to-effect bijection for every completed key.
    ///
    /// In-progress records need no effect. Every completed record must name one
    /// matching effect, and every effect must have one matching completed
    /// record.
    #[must_use]
    pub fn invariants_hold(&self) -> bool {
        let inner = self
            .inner
            .lock()
            .unwrap_or_else(|poison| poison.into_inner());
        let records_valid = inner
            .records
            .iter()
            .all(|(key, record)| match record.status {
                RecordStatus::InProgress => !inner.effects.iter().any(|effect| effect.key == *key),
                RecordStatus::Complete(resource) => {
                    inner
                        .effects
                        .iter()
                        .filter(|effect| effect.key == *key && effect.resource == resource)
                        .count()
                        == 1
                }
            });
        let effects_valid = inner.effects.iter().all(|effect| {
            inner.records.get(&effect.key).map(|record| record.status)
                == Some(RecordStatus::Complete(effect.resource))
        });
        records_valid && effects_valid
    }
}

/// Result of a deterministic non-atomic split-write failure.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SplitWriteOutcome {
    /// Number of committed business effects after one retry.
    pub effects: u64,
    /// Whether the retry finds a receipt and reports a replay.
    pub replayed: bool,
}

/// Models effect-first execution with a crash before the receipt write.
///
/// The first effect survives without a receipt, so one retry commits a second
/// effect instead of replaying the first result.
#[must_use]
pub const fn effect_before_receipt() -> SplitWriteOutcome {
    SplitWriteOutcome {
        effects: 2,
        replayed: false,
    }
}

/// Models receipt-first execution with a crash before the effect write.
///
/// The receipt survives without an effect, so one retry replays success while
/// the effect count remains zero.
#[must_use]
pub const fn receipt_before_effect() -> SplitWriteOutcome {
    SplitWriteOutcome {
        effects: 0,
        replayed: true,
    }
}

/// Returns the encoded begin action for a retained state and two fingerprints.
///
/// Input states `0`, `1`, and `2` mean absent, in progress, and complete.
/// Every state above `2` also follows the complete branch. Return values `0`,
/// `1`, `2`, and `3` mean owner, in progress, replay, and mismatch. An absent
/// state ignores the fingerprints; every nonzero state checks them before its
/// status. The exported, non-inlined symbol supports generated-code inspection.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic30_begin_decision(state: u8, stored: u64, incoming: u64) -> u8 {
    if state == 0 {
        0
    } else if stored != incoming {
        3
    } else if state == 1 {
        1
    } else {
        2
    }
}

/// Returns `1` only for an in-progress state with a matching ticket generation.
///
/// Every other input returns `0`. The exported, non-inlined symbol supports
/// generated-code inspection.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic30_finish_allowed(
    state: u8,
    current_generation: u64,
    ticket_generation: u64,
) -> u8 {
    u8::from(state == 1 && current_generation == ticket_generation)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn owner(result: BeginResult) -> CompletionTicket {
        match result {
            BeginResult::Owner(ticket) => ticket,
            other => panic!("expected owner, got {other:?}"),
        }
    }

    #[test]
    fn replay_and_distinct_intent_preserve_effect_count() {
        let store = IdempotencyStore::new();
        let ticket = owner(store.begin("order-42", RequestFingerprint(2_000)));
        assert_eq!(
            store.begin("order-42", RequestFingerprint(2_000)),
            BeginResult::InProgress
        );
        let resource = store.complete(ticket).unwrap();
        assert_eq!(
            store.begin("order-42", RequestFingerprint(2_000)),
            BeginResult::Replay(resource)
        );
        assert_eq!(
            store.begin("order-42", RequestFingerprint(2_001)),
            BeginResult::ParameterMismatch
        );
        let second = owner(store.begin("order-43", RequestFingerprint(2_000)));
        store.complete(second).unwrap();
        assert_eq!(store.effect_count(), 2);
        assert!(store.invariants_hold());
    }

    #[test]
    fn scoped_keys_do_not_share_state() {
        let store = IdempotencyStore::new();
        let tenant_a = "billing:tenant-a:create-charge:order-42";
        let tenant_b = "billing:tenant-b:create-charge:order-42";

        let first = owner(store.begin(tenant_a, RequestFingerprint(2_000)));
        let second = owner(store.begin(tenant_b, RequestFingerprint(2_001)));
        let first_resource = store.complete(first).unwrap();
        let second_resource = store.complete(second).unwrap();

        assert_ne!(first_resource, second_resource);
        assert_eq!(
            store.begin(tenant_a, RequestFingerprint(2_000)),
            BeginResult::Replay(first_resource)
        );
        assert_eq!(
            store.begin(tenant_b, RequestFingerprint(2_001)),
            BeginResult::Replay(second_resource)
        );
        assert_eq!(store.effect_count(), 2);
    }

    #[test]
    fn takeover_fences_stale_owner() {
        let store = IdempotencyStore::new();
        let stale = owner(store.begin("order-44", RequestFingerprint(3_000)));
        let current = store
            .take_over("order-44", RequestFingerprint(3_000))
            .unwrap();
        assert_eq!(store.complete(stale), Err(CompleteError::StaleOwner));
        assert_eq!(store.complete(current), Ok(ResourceId(1)));
        assert!(store.invariants_hold());
    }

    #[test]
    fn split_writes_expose_both_crash_windows() {
        assert_eq!(
            effect_before_receipt(),
            SplitWriteOutcome {
                effects: 2,
                replayed: false
            }
        );
        assert_eq!(
            receipt_before_effect(),
            SplitWriteOutcome {
                effects: 0,
                replayed: true
            }
        );
    }

    #[test]
    fn codegen_hooks_cover_all_decisions() {
        assert_eq!(topic30_begin_decision(0, 7, 9), 0);
        assert_eq!(topic30_begin_decision(1, 7, 7), 1);
        assert_eq!(topic30_begin_decision(2, 7, 7), 2);
        assert_eq!(topic30_begin_decision(2, 7, 9), 3);
        assert_eq!(topic30_finish_allowed(1, 8, 8), 1);
        assert_eq!(topic30_finish_allowed(1, 8, 7), 0);
    }
}
