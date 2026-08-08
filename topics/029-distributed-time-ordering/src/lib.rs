//! Deterministic models of several ways to order distributed events.
//!
//! The models use caller-supplied clock readings, so tests can force clock
//! skew and rollback without consulting the host clock. They cover wall-clock
//! last-write-wins selection, Lamport clocks, a fixed two-replica vector clock,
//! a hybrid logical clock, and closed uncertainty intervals.
//!
//! # Ordering guarantees
//!
//! [`LwwStamp`] gives equal physical readings a deterministic winner, but clock
//! skew can select a causal predecessor. A successful receive transition from
//! [`LamportClock`] or [`HybridLogicalClock`] produces a timestamp greater than
//! both the prior local timestamp and the received timestamp; neither timestamp
//! comparison identifies concurrency. [`VectorClock`] distinguishes causal
//! dominance from concurrency within its fixed two-replica membership.
//! [`UncertaintyInterval`] establishes physical order only when two closed
//! intervals are strictly disjoint.
//!
//! # Model boundary
//!
//! This crate is a teaching and code-generation probe. It models two replicas
//! named [`Replica::A`] and [`Replica::B`], deterministic local transitions,
//! and checked counter overflow. It does not implement persistence, networking,
//! membership changes, clock synchronization, crash recovery, authentication,
//! or a production replication protocol.

#![deny(unsafe_op_in_unsafe_fn)]

use std::error::Error;
use std::fmt::{self, Display, Formatter};

/// One of the two replicas represented by [`VectorClock`].
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum Replica {
    /// The first replica and first vector-clock component.
    A,
    /// The second replica and second vector-clock component.
    B,
}

impl Replica {
    const fn index(self) -> usize {
        match self {
            Self::A => 0,
            Self::B => 1,
        }
    }

    /// Returns `A` for [`Replica::A`] and `B` for [`Replica::B`].
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::A => "A",
            Self::B => "B",
        }
    }
}

/// A wall-clock timestamp plus a deterministic replica tie-breaker.
///
/// Ordering compares `physical_ms` first and [`Replica`] second. The replica
/// component makes equal physical readings deterministic; it does not make a
/// skewed wall clock preserve causal order.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct LwwStamp {
    physical_ms: u64,
    replica: Replica,
}

impl LwwStamp {
    /// Creates a last-write-wins stamp from an injected wall-clock reading.
    #[must_use]
    pub const fn new(physical_ms: u64, replica: Replica) -> Self {
        Self {
            physical_ms,
            replica,
        }
    }

    /// Returns the injected physical time in milliseconds.
    #[must_use]
    pub const fn physical_ms(self) -> u64 {
        self.physical_ms
    }

    /// Returns the replica used to break equal-time ties.
    #[must_use]
    pub const fn replica(self) -> Replica {
        self.replica
    }
}

/// Selects the greater wall-clock last-write-wins stamp.
///
/// A causally later write can lose when its replica clock is behind:
///
/// ```
/// use distributed_time_ordering::{LwwStamp, Replica, wall_clock_lww};
///
/// let first = LwwStamp::new(200, Replica::A);
/// let causally_later = LwwStamp::new(150, Replica::B);
/// assert_eq!(wall_clock_lww(first, causally_later), first);
/// ```
#[must_use]
pub fn wall_clock_lww(left: LwwStamp, right: LwwStamp) -> LwwStamp {
    left.max(right)
}

/// Error returned when a logical counter cannot be incremented.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ClockOverflow;

impl Display for ClockOverflow {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("logical clock counter overflowed")
    }
}

impl Error for ClockOverflow {}

/// A scalar Lamport logical clock.
///
/// A local event increments the counter. Receiving a timestamp takes the
/// greater counter and then increments it. Therefore causal order implies
/// increasing timestamps, but increasing timestamps alone do not prove that
/// two events communicated.
///
/// ```
/// use distributed_time_ordering::LamportClock;
///
/// let mut sender = LamportClock::new(0);
/// let sent = sender.tick()?;
/// let mut receiver = LamportClock::new(0);
/// assert_eq!(receiver.receive(sent)?, 2);
/// # Ok::<(), distributed_time_ordering::ClockOverflow>(())
/// ```
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct LamportClock {
    counter: u64,
}

impl LamportClock {
    /// Creates a clock with the supplied counter value.
    #[must_use]
    pub const fn new(counter: u64) -> Self {
        Self { counter }
    }

    /// Returns the current counter without changing it.
    #[must_use]
    pub const fn value(self) -> u64 {
        self.counter
    }

    /// Records one local event and returns its timestamp.
    ///
    /// # Errors
    ///
    /// Returns [`ClockOverflow`] when the current counter is [`u64::MAX`]. The
    /// clock remains unchanged on error.
    pub fn tick(&mut self) -> Result<u64, ClockOverflow> {
        let next = self.counter.checked_add(1).ok_or(ClockOverflow)?;
        self.counter = next;
        Ok(next)
    }

    /// Records receipt of `remote` and returns the receive-event timestamp.
    ///
    /// # Errors
    ///
    /// Returns [`ClockOverflow`] when the greater of the local and remote
    /// counters is [`u64::MAX`]. The clock remains unchanged on error.
    pub fn receive(&mut self, remote: u64) -> Result<u64, ClockOverflow> {
        let next = self
            .counter
            .max(remote)
            .checked_add(1)
            .ok_or(ClockOverflow)?;
        self.counter = next;
        Ok(next)
    }
}

/// The causal relation between two [`VectorClock`] values.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum VectorRelation {
    /// Both clocks contain the same two counters.
    Equal,
    /// The left clock is componentwise no greater and is smaller in at least one component.
    Before,
    /// The left clock is componentwise no smaller and is greater in at least one component.
    After,
    /// Each clock is greater in a different component, so neither caused the other.
    Concurrent,
}

impl VectorRelation {
    /// Returns `equal`, `before`, `after`, or `concurrent`.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Equal => "equal",
            Self::Before => "before",
            Self::After => "after",
            Self::Concurrent => "concurrent",
        }
    }

    const fn code(self) -> u8 {
        match self {
            Self::Equal => 0,
            Self::Before => 1,
            Self::After => 2,
            Self::Concurrent => 3,
        }
    }
}

/// A fixed two-replica vector clock stored as `[A, B]` counters.
///
/// Unlike a scalar Lamport clock, componentwise comparison can distinguish a
/// causal predecessor from events that were produced independently.
///
/// ```
/// use distributed_time_ordering::{Replica, VectorClock, VectorRelation};
///
/// let mut a = VectorClock::new();
/// a.tick(Replica::A)?;
/// let mut b = VectorClock::new();
/// b.tick(Replica::B)?;
/// assert_eq!(a.relation(b), VectorRelation::Concurrent);
///
/// b.receive(Replica::B, a)?;
/// assert_eq!(a.relation(b), VectorRelation::Before);
/// # Ok::<(), distributed_time_ordering::ClockOverflow>(())
/// ```
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct VectorClock {
    counters: [u64; 2],
}

impl VectorClock {
    /// Creates the zero clock `[0, 0]`.
    #[must_use]
    pub const fn new() -> Self {
        Self { counters: [0, 0] }
    }

    /// Creates a clock from `[A, B]` counters.
    #[must_use]
    pub const fn from_counters(counters: [u64; 2]) -> Self {
        Self { counters }
    }

    /// Returns both counters in `[A, B]` order.
    #[must_use]
    pub const fn counters(self) -> [u64; 2] {
        self.counters
    }

    /// Returns one replica's counter.
    #[must_use]
    pub const fn counter(self, replica: Replica) -> u64 {
        self.counters[replica.index()]
    }

    /// Records one event at `replica`.
    ///
    /// # Errors
    ///
    /// Returns [`ClockOverflow`] if that replica's counter is [`u64::MAX`].
    /// The clock remains unchanged on error.
    pub fn tick(&mut self, replica: Replica) -> Result<Self, ClockOverflow> {
        let index = replica.index();
        let next = self.counters[index].checked_add(1).ok_or(ClockOverflow)?;
        self.counters[index] = next;
        Ok(*self)
    }

    /// Merges `remote` and records a receive event at `replica`.
    ///
    /// The componentwise maximum imports the remote history. Incrementing the
    /// receiver component makes the receive event later than that merged history.
    ///
    /// # Errors
    ///
    /// Returns [`ClockOverflow`] if the merged receiver component is
    /// [`u64::MAX`]. The clock remains unchanged on error.
    pub fn receive(&mut self, replica: Replica, remote: Self) -> Result<Self, ClockOverflow> {
        let mut merged = [
            self.counters[0].max(remote.counters[0]),
            self.counters[1].max(remote.counters[1]),
        ];
        let index = replica.index();
        merged[index] = merged[index].checked_add(1).ok_or(ClockOverflow)?;
        self.counters = merged;
        Ok(*self)
    }

    /// Compares two clocks using componentwise partial order.
    #[must_use]
    pub const fn relation(self, other: Self) -> VectorRelation {
        let self_le =
            self.counters[0] <= other.counters[0] && self.counters[1] <= other.counters[1];
        let other_le =
            other.counters[0] <= self.counters[0] && other.counters[1] <= self.counters[1];

        match (self_le, other_le) {
            (true, true) => VectorRelation::Equal,
            (true, false) => VectorRelation::Before,
            (false, true) => VectorRelation::After,
            (false, false) => VectorRelation::Concurrent,
        }
    }
}

/// One hybrid logical clock timestamp `(physical_ms, logical)`.
///
/// Lexicographic ordering compares the physical component first. The logical
/// component preserves order when the injected physical reading stalls or moves
/// backward. Different replicas can still produce equal timestamps unless a
/// separate replica tie-breaker is added by a protocol.
///
/// The exported inspection hook uses this type's C field layout. No persistence
/// or network format is defined by that layout.
#[repr(C)]
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub struct HybridTimestamp {
    physical_ms: u64,
    logical: u32,
}

impl HybridTimestamp {
    /// Creates a timestamp from physical and logical components.
    #[must_use]
    pub const fn new(physical_ms: u64, logical: u32) -> Self {
        Self {
            physical_ms,
            logical,
        }
    }

    /// Returns the physical component in milliseconds.
    #[must_use]
    pub const fn physical_ms(self) -> u64 {
        self.physical_ms
    }

    /// Returns the logical component.
    #[must_use]
    pub const fn logical(self) -> u32 {
        self.logical
    }
}

/// A hybrid logical clock driven by injected physical readings.
///
/// ```
/// use distributed_time_ordering::{HybridLogicalClock, HybridTimestamp};
///
/// let mut sender = HybridLogicalClock::new();
/// let sent = sender.local(100)?;
/// assert_eq!(sent, HybridTimestamp::new(100, 0));
///
/// let mut receiver = HybridLogicalClock::from_timestamp(HybridTimestamp::new(90, 0));
/// let received = receiver.receive(95, sent)?;
/// assert_eq!(received, HybridTimestamp::new(100, 1));
/// assert_eq!(receiver.local(80)?, HybridTimestamp::new(100, 2));
/// # Ok::<(), distributed_time_ordering::ClockOverflow>(())
/// ```
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct HybridLogicalClock {
    last: HybridTimestamp,
}

impl Default for HybridTimestamp {
    fn default() -> Self {
        Self::new(0, 0)
    }
}

impl HybridLogicalClock {
    /// Creates a clock at `(0, 0)`.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            last: HybridTimestamp::new(0, 0),
        }
    }

    /// Creates a clock whose last timestamp is `last`.
    #[must_use]
    pub const fn from_timestamp(last: HybridTimestamp) -> Self {
        Self { last }
    }

    /// Returns the last timestamp without changing the clock.
    #[must_use]
    pub const fn last(self) -> HybridTimestamp {
        self.last
    }

    /// Records a local event using the injected physical reading `now_ms`.
    ///
    /// A reading later than the stored physical component resets the logical
    /// component to zero. A stalled or backward reading increments the logical
    /// component instead.
    ///
    /// # Errors
    ///
    /// Returns [`ClockOverflow`] if the logical component must increment past
    /// [`u32::MAX`]. The clock remains unchanged on error.
    pub fn local(&mut self, now_ms: u64) -> Result<HybridTimestamp, ClockOverflow> {
        let next = if now_ms > self.last.physical_ms {
            HybridTimestamp::new(now_ms, 0)
        } else {
            HybridTimestamp::new(
                self.last.physical_ms,
                self.last.logical.checked_add(1).ok_or(ClockOverflow)?,
            )
        };
        self.last = next;
        Ok(next)
    }

    /// Records receipt of `remote` using the injected physical reading `now_ms`.
    ///
    /// The next physical component is the maximum of the local physical state,
    /// the remote physical component, and `now_ms`. The logical component then
    /// advances the clock or resets when physical time is strictly newer.
    ///
    /// # Errors
    ///
    /// Returns [`ClockOverflow`] if the selected logical component must
    /// increment past [`u32::MAX`]. The clock remains unchanged on error.
    pub fn receive(
        &mut self,
        now_ms: u64,
        remote: HybridTimestamp,
    ) -> Result<HybridTimestamp, ClockOverflow> {
        let physical_ms = now_ms.max(self.last.physical_ms).max(remote.physical_ms);

        let base_logical =
            if physical_ms == self.last.physical_ms && physical_ms == remote.physical_ms {
                Some(self.last.logical.max(remote.logical))
            } else if physical_ms == self.last.physical_ms {
                Some(self.last.logical)
            } else if physical_ms == remote.physical_ms {
                Some(remote.logical)
            } else {
                None
            };

        let logical = match base_logical {
            Some(base) => base.checked_add(1).ok_or(ClockOverflow)?,
            None => 0,
        };
        let next = HybridTimestamp::new(physical_ms, logical);
        self.last = next;
        Ok(next)
    }
}

/// Error returned when an uncertainty interval has reversed endpoints.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidInterval {
    earliest_ms: u64,
    latest_ms: u64,
}

impl InvalidInterval {
    /// Returns the rejected earliest endpoint.
    #[must_use]
    pub const fn earliest_ms(self) -> u64 {
        self.earliest_ms
    }

    /// Returns the rejected latest endpoint.
    #[must_use]
    pub const fn latest_ms(self) -> u64 {
        self.latest_ms
    }
}

impl Display for InvalidInterval {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "uncertainty interval starts at {} but ends at {}",
            self.earliest_ms, self.latest_ms
        )
    }
}

impl Error for InvalidInterval {}

/// The definite ordering result for two uncertainty intervals.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum IntervalRelation {
    /// Every possible instant in the left interval precedes the right interval.
    DefinitelyBefore,
    /// Every possible instant in the left interval follows the right interval.
    DefinitelyAfter,
    /// The intervals touch or overlap, so their order is not established.
    Indeterminate,
}

impl IntervalRelation {
    /// Returns `definitely-before`, `definitely-after`, or `indeterminate`.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::DefinitelyBefore => "definitely-before",
            Self::DefinitelyAfter => "definitely-after",
            Self::Indeterminate => "indeterminate",
        }
    }
}

/// A validated closed interval of possible wall-clock instants.
///
/// ```
/// use distributed_time_ordering::{IntervalRelation, UncertaintyInterval};
///
/// let first = UncertaintyInterval::new(90, 110)?;
/// let second = UncertaintyInterval::new(120, 140)?;
/// assert!(first.definitely_before(second));
/// assert_eq!(first.relation(second), IntervalRelation::DefinitelyBefore);
/// # Ok::<(), distributed_time_ordering::InvalidInterval>(())
/// ```
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct UncertaintyInterval {
    earliest_ms: u64,
    latest_ms: u64,
}

impl UncertaintyInterval {
    /// Validates and creates the closed interval `[earliest_ms, latest_ms]`.
    ///
    /// # Errors
    ///
    /// Returns [`InvalidInterval`] when `earliest_ms > latest_ms`.
    pub const fn new(earliest_ms: u64, latest_ms: u64) -> Result<Self, InvalidInterval> {
        if earliest_ms > latest_ms {
            Err(InvalidInterval {
                earliest_ms,
                latest_ms,
            })
        } else {
            Ok(Self {
                earliest_ms,
                latest_ms,
            })
        }
    }

    /// Returns the earliest possible instant.
    #[must_use]
    pub const fn earliest_ms(self) -> u64 {
        self.earliest_ms
    }

    /// Returns the latest possible instant.
    #[must_use]
    pub const fn latest_ms(self) -> u64 {
        self.latest_ms
    }

    /// Returns whether every possible instant in `self` precedes `other`.
    ///
    /// The comparison is strict because these are closed intervals. Intervals
    /// that share one endpoint are not definitely ordered.
    #[must_use]
    pub const fn definitely_before(self, other: Self) -> bool {
        self.latest_ms < other.earliest_ms
    }

    /// Returns the definite ordering supported by the two intervals.
    #[must_use]
    pub const fn relation(self, other: Self) -> IntervalRelation {
        if self.latest_ms < other.earliest_ms {
            IntervalRelation::DefinitelyBefore
        } else if other.latest_ms < self.earliest_ms {
            IntervalRelation::DefinitelyAfter
        } else {
            IntervalRelation::Indeterminate
        }
    }
}

/// Selects the greater injected wall reading for final-image inspection.
///
/// Returns `1` when `right_ms` is greater and `0` otherwise. Replica
/// tie-breaking remains outside this scalar hook.
#[must_use]
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic29_lww_choice(left_ms: u64, right_ms: u64) -> u8 {
    u8::from(right_ms > left_ms)
}

/// Computes a Lamport receive timestamp for final-image inspection.
///
/// Returns zero on overflow; every successful Lamport receive timestamp is
/// nonzero.
#[must_use]
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic29_lamport_receive(local: u64, remote: u64) -> u64 {
    LamportClock::new(local).receive(remote).unwrap_or(0)
}

/// Classifies two vector clocks for final-image inspection.
///
/// Returns `0` for equal, `1` for before, `2` for after, and `3` for
/// concurrent.
#[must_use]
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic29_vector_relation(a0: u64, a1: u64, b0: u64, b1: u64) -> u8 {
    VectorClock::from_counters([a0, a1])
        .relation(VectorClock::from_counters([b0, b1]))
        .code()
}

/// Computes one HLC receive transition for final-image inspection.
///
/// Returns `(0, 0)` if the transition would overflow the logical component.
/// Normal inputs use the same checked transition as [`HybridLogicalClock`].
#[must_use]
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic29_hlc_receive(
    last_physical_ms: u64,
    last_logical: u32,
    remote_physical_ms: u64,
    remote_logical: u32,
    now_ms: u64,
) -> HybridTimestamp {
    let mut clock =
        HybridLogicalClock::from_timestamp(HybridTimestamp::new(last_physical_ms, last_logical));
    clock
        .receive(
            now_ms,
            HybridTimestamp::new(remote_physical_ms, remote_logical),
        )
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lww_uses_physical_time_then_replica_tie_break() {
        let first = LwwStamp::new(200, Replica::A);
        let causally_later = LwwStamp::new(150, Replica::B);
        assert_eq!(wall_clock_lww(first, causally_later), first);

        let tied_a = LwwStamp::new(200, Replica::A);
        let tied_b = LwwStamp::new(200, Replica::B);
        assert_eq!(wall_clock_lww(tied_a, tied_b), tied_b);
        assert_eq!(tied_a.physical_ms(), 200);
        assert_eq!(Replica::A.as_str(), "A");
        assert_eq!(Replica::B.as_str(), "B");
    }

    #[test]
    fn lamport_tick_and_receive_are_checked_and_transactional() {
        let mut clock = LamportClock::new(4);
        assert_eq!(clock.tick(), Ok(5));
        assert_eq!(clock.receive(9), Ok(10));
        assert_eq!(clock.value(), 10);

        let mut exhausted = LamportClock::new(u64::MAX);
        assert_eq!(exhausted.tick(), Err(ClockOverflow));
        assert_eq!(exhausted.value(), u64::MAX);

        let mut receiver = LamportClock::new(7);
        assert_eq!(receiver.receive(u64::MAX), Err(ClockOverflow));
        assert_eq!(receiver.value(), 7);
    }

    #[test]
    fn vector_relation_distinguishes_causal_and_concurrent() -> Result<(), ClockOverflow> {
        let mut a = VectorClock::new();
        a.tick(Replica::A)?;
        let mut b = VectorClock::new();
        b.tick(Replica::B)?;

        assert_eq!(a.relation(a), VectorRelation::Equal);
        assert_eq!(a.relation(b), VectorRelation::Concurrent);
        assert_eq!(b.relation(a), VectorRelation::Concurrent);
        assert_eq!(VectorRelation::Equal.as_str(), "equal");
        assert_eq!(VectorRelation::Concurrent.as_str(), "concurrent");

        b.receive(Replica::B, a)?;
        assert_eq!(a.relation(b), VectorRelation::Before);
        assert_eq!(b.relation(a), VectorRelation::After);
        assert_eq!(VectorRelation::Before.as_str(), "before");
        assert_eq!(VectorRelation::After.as_str(), "after");
        assert_eq!(b.counters(), [1, 2]);
        assert_eq!(b.counter(Replica::A), 1);
        assert_eq!(b.counter(Replica::B), 2);
        Ok(())
    }

    #[test]
    fn vector_overflow_does_not_partially_merge() {
        let original = VectorClock::from_counters([4, 5]);
        let mut receiver = original;
        let remote = VectorClock::from_counters([u64::MAX, 99]);
        assert_eq!(receiver.receive(Replica::A, remote), Err(ClockOverflow));
        assert_eq!(receiver, original);

        let mut exhausted = VectorClock::from_counters([0, u64::MAX]);
        assert_eq!(exhausted.tick(Replica::B), Err(ClockOverflow));
        assert_eq!(exhausted.counters(), [0, u64::MAX]);
    }

    #[test]
    fn hlc_handles_physical_advance_stall_rollback_and_receive() -> Result<(), ClockOverflow> {
        let mut sender = HybridLogicalClock::new();
        let sent = sender.local(100)?;
        assert_eq!(sent, HybridTimestamp::new(100, 0));
        assert_eq!(sent.physical_ms(), 100);
        assert_eq!(sent.logical(), 0);
        assert_eq!(sender.local(100)?, HybridTimestamp::new(100, 1));
        assert_eq!(sender.local(80)?, HybridTimestamp::new(100, 2));
        assert_eq!(sender.local(101)?, HybridTimestamp::new(101, 0));

        let mut receiver = HybridLogicalClock::from_timestamp(HybridTimestamp::new(90, 7));
        assert_eq!(
            receiver.receive(95, HybridTimestamp::new(100, 3))?,
            HybridTimestamp::new(100, 4)
        );
        assert_eq!(
            receiver.receive(110, HybridTimestamp::new(100, 99))?,
            HybridTimestamp::new(110, 0)
        );
        Ok(())
    }

    #[test]
    fn hlc_equal_physical_components_advance_greater_logical() {
        let mut clock = HybridLogicalClock::from_timestamp(HybridTimestamp::new(100, 4));
        assert_eq!(
            clock.receive(90, HybridTimestamp::new(100, 9)),
            Ok(HybridTimestamp::new(100, 10))
        );
    }

    #[test]
    fn hlc_overflow_preserves_state() {
        let last = HybridTimestamp::new(100, u32::MAX);
        let mut local = HybridLogicalClock::from_timestamp(last);
        assert_eq!(local.local(99), Err(ClockOverflow));
        assert_eq!(local.last(), last);

        let mut receive = HybridLogicalClock::from_timestamp(HybridTimestamp::new(100, 7));
        let original = receive;
        assert_eq!(
            receive.receive(90, HybridTimestamp::new(100, u32::MAX)),
            Err(ClockOverflow)
        );
        assert_eq!(receive, original);

        assert_eq!(
            receive.receive(101, HybridTimestamp::new(100, u32::MAX)),
            Ok(HybridTimestamp::new(101, 0))
        );
    }

    #[test]
    fn interval_validation_and_strict_boundaries() {
        let invalid = UncertaintyInterval::new(11, 10).unwrap_err();
        assert_eq!(invalid.earliest_ms(), 11);
        assert_eq!(invalid.latest_ms(), 10);

        let first = UncertaintyInterval::new(10, 20).unwrap();
        let touching = UncertaintyInterval::new(20, 30).unwrap();
        let later = UncertaintyInterval::new(21, 30).unwrap();
        assert_eq!(first.earliest_ms(), 10);
        assert_eq!(first.latest_ms(), 20);
        assert!(!first.definitely_before(touching));
        assert_eq!(first.relation(touching), IntervalRelation::Indeterminate);
        assert_eq!(IntervalRelation::Indeterminate.as_str(), "indeterminate");
        assert!(first.definitely_before(later));
        assert_eq!(first.relation(later), IntervalRelation::DefinitelyBefore);
        assert_eq!(
            IntervalRelation::DefinitelyBefore.as_str(),
            "definitely-before"
        );
        assert_eq!(later.relation(first), IntervalRelation::DefinitelyAfter);
        assert_eq!(
            IntervalRelation::DefinitelyAfter.as_str(),
            "definitely-after"
        );
    }

    #[test]
    fn inspection_hooks_use_documented_sentinels() {
        assert_eq!(topic29_lww_choice(1_000, 900), 0);
        assert_eq!(topic29_lww_choice(1_000, 1_001), 1);
        assert_eq!(topic29_lamport_receive(0, 1), 2);
        assert_eq!(topic29_lamport_receive(5, 1), 6);
        assert_eq!(topic29_lamport_receive(0, u64::MAX), 0);
        assert_eq!(topic29_vector_relation(1, 0, 0, 1), 3);
        assert_eq!(
            topic29_hlc_receive(0, 0, 1_000, 0, 900),
            HybridTimestamp::new(1_000, 1)
        );
        assert_eq!(
            topic29_hlc_receive(100, u32::MAX, 100, u32::MAX, 99),
            HybridTimestamp::default()
        );
    }

    const _: () = {
        fn assert_send_sync<T: Send + Sync>() {}
        let _ = assert_send_sync::<LamportClock>;
        let _ = assert_send_sync::<VectorClock>;
        let _ = assert_send_sync::<HybridLogicalClock>;
        let _ = assert_send_sync::<UncertaintyInterval>;
    };
}
