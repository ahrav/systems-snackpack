//! Checked arithmetic for async-task frame, residency, and cancellation models.
//!
//! A compiler-generated future must preserve the state needed to resume at each
//! `.await`. A measured concrete layout is specific to its compiler version,
//! target, and build profile; Rust does not promise that layout as an ABI.
//! Executor metadata, allocation rounding, child allocations, and completed
//! outputs can add storage outside that future.
//!
//! # Model boundary
//!
//! [`future_frame_screen`] approximates a frame from source-level liveness,
//! [`checked_future_state_bytes`] scales a concrete frame size across a fleet,
//! and [`TaskResidency`] combines caller-supplied runtime, future, and output
//! storage. [`CancellationLatency`] sums three sequential cooperative phases;
//! it excludes asynchronous child shutdown, I/O completion, and external
//! draining.
//!
//! These screens do not measure a future, infer executor overhead, or establish
//! a shutdown upper bound. Measure a concrete future with
//! [`std::mem::size_of_val`] and obtain runtime overhead from the exact executor
//! version and configuration used by the workload.
//! Run `cargo run --package async-runtime-mechanics --example state-and-cancellation`
//! for the deterministic state-layout and cancellation-boundary probe.

use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::num::NonZeroUsize;
use std::time::Duration;

/// Signals that a byte-count cost screen exceeded `usize::MAX`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CostOverflow;

impl Display for CostOverflow {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("cost screen arithmetic overflowed")
    }
}

impl Error for CostOverflow {}

/// Returns an aligned source-level size screen for one future frame.
///
/// The calculation rounds `tag_and_fixed_bytes + widest_live_bytes` up to
/// `alignment`. Pass the aggregate bytes live at the widest single suspension
/// point; do not sum mutually exclusive suspension states. `alignment` accepts
/// any nonzero byte value, not only powers of two. The compiler can reuse
/// storage or add layout state outside this model, so compare the result with
/// [`std::mem::size_of_val`] for the concrete future.
///
/// # Examples
///
/// ```
/// use std::num::NonZeroUsize;
/// use async_runtime_mechanics::future_frame_screen;
///
/// let alignment = NonZeroUsize::new(8).unwrap();
/// assert_eq!(future_frame_screen(3, 4_096, alignment), Ok(4_104));
/// ```
///
/// # Errors
///
/// Returns [`CostOverflow`] if:
///
/// - `tag_and_fixed_bytes + widest_live_bytes` exceeds `usize::MAX`; or
/// - adding the required alignment padding exceeds `usize::MAX`.
pub fn future_frame_screen(
    tag_and_fixed_bytes: usize,
    widest_live_bytes: usize,
    alignment: NonZeroUsize,
) -> Result<usize, CostOverflow> {
    let unaligned = tag_and_fixed_bytes
        .checked_add(widest_live_bytes)
        .ok_or(CostOverflow)?;
    let alignment = alignment.get();
    let remainder = unaligned % alignment;
    if remainder == 0 {
        Ok(unaligned)
    } else {
        unaligned
            .checked_add(alignment - remainder)
            .ok_or(CostOverflow)
    }
}

/// Returns the inline future-state bytes retained by a task fleet.
///
/// The calculation is `task_count * future_bytes`. Obtain `future_bytes` from
/// the concrete future and compiler build of interest. The product excludes
/// executor metadata, allocation rounding, stacks used while polling, child
/// allocations, and output storage.
///
/// # Examples
///
/// ```
/// use async_runtime_mechanics::checked_future_state_bytes;
///
/// assert_eq!(checked_future_state_bytes(100_000, 4_099), Ok(409_900_000));
/// assert!(checked_future_state_bytes(usize::MAX, 2).is_err());
/// ```
///
/// # Errors
///
/// Returns [`CostOverflow`] when `task_count * future_bytes` exceeds
/// `usize::MAX`.
pub fn checked_future_state_bytes(
    task_count: usize,
    future_bytes: usize,
) -> Result<usize, CostOverflow> {
    task_count.checked_mul(future_bytes).ok_or(CostOverflow)
}

/// Rule for combining future and output storage at peak task residency.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FutureOutputResidency {
    /// The future and output lifetimes do not overlap, so the larger one sets
    /// their combined peak.
    NonOverlapping,
    /// The runtime retains the future and output at the same time, so both
    /// contribute to the peak.
    Overlapping,
}

/// Caller-supplied inputs to a fleet-wide peak-residency screen.
///
/// Include scheduler metadata and allocation rounding in
/// `runtime_bytes_per_task` when the model needs them. Keep every byte count
/// tied to one concrete compiler, runtime, and allocation configuration.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TaskResidency {
    /// Simultaneously resident tasks included in the modeled peak.
    pub task_count: usize,
    /// Per-task runtime and allocation bytes outside future and output storage.
    pub runtime_bytes_per_task: usize,
    /// Inline size of the concrete future.
    pub future_bytes: usize,
    /// Per-task storage retained for a completed output.
    pub output_bytes: usize,
    /// Lifetime rule used to combine `future_bytes` and `output_bytes`.
    pub future_output_residency: FutureOutputResidency,
}

impl TaskResidency {
    /// Returns peak bytes for all resident tasks.
    ///
    /// `NonOverlapping` computes
    /// `task_count * (runtime_bytes_per_task + max(future_bytes, output_bytes))`.
    /// `Overlapping` computes
    /// `task_count * (runtime_bytes_per_task + future_bytes + output_bytes)`.
    ///
    /// # Examples
    ///
    /// ```
    /// use async_runtime_mechanics::{FutureOutputResidency, TaskResidency};
    ///
    /// let non_overlapping = TaskResidency {
    ///     task_count: 100_000,
    ///     runtime_bytes_per_task: 160,
    ///     future_bytes: 4_099,
    ///     output_bytes: 16,
    ///     future_output_residency: FutureOutputResidency::NonOverlapping,
    /// };
    /// let overlapping = TaskResidency {
    ///     future_output_residency: FutureOutputResidency::Overlapping,
    ///     ..non_overlapping
    /// };
    /// assert_eq!(non_overlapping.checked_peak_bytes(), Ok(425_900_000));
    /// assert_eq!(overlapping.checked_peak_bytes(), Ok(427_500_000));
    /// ```
    ///
    /// # Errors
    ///
    /// Returns [`CostOverflow`] if:
    ///
    /// - overlapping future and output bytes exceed `usize::MAX`;
    /// - runtime bytes plus the selected state bytes exceed `usize::MAX`; or
    /// - the per-task total multiplied by `task_count` exceeds `usize::MAX`.
    pub fn checked_peak_bytes(self) -> Result<usize, CostOverflow> {
        let state_bytes = match self.future_output_residency {
            FutureOutputResidency::NonOverlapping => self.future_bytes.max(self.output_bytes),
            FutureOutputResidency::Overlapping => self
                .future_bytes
                .checked_add(self.output_bytes)
                .ok_or(CostOverflow)?,
        };
        let per_task = self
            .runtime_bytes_per_task
            .checked_add(state_bytes)
            .ok_or(CostOverflow)?;
        self.task_count.checked_mul(per_task).ok_or(CostOverflow)
    }
}

/// Returns peak residency for a caller-supplied task model.
///
/// Uses the lifetime rule and checked arithmetic defined by
/// [`TaskResidency::checked_peak_bytes`].
///
/// # Errors
///
/// Returns [`CostOverflow`] if:
///
/// - overlapping future and output bytes exceed `usize::MAX`;
/// - runtime bytes plus the selected state bytes exceed `usize::MAX`; or
/// - the per-task total multiplied by `task_count` exceeds `usize::MAX`.
pub fn task_residency_screen(screen: TaskResidency) -> Result<usize, CostOverflow> {
    screen.checked_peak_bytes()
}

/// Inputs to a sequential cooperative cancellation-latency screen.
///
/// The modeled path finishes the current poll, waits for the runtime to poll the
/// task again, then runs synchronous destructors. It excludes asynchronous
/// child shutdown, I/O completion, and external draining. The caller supplies
/// each duration; phases that overlap require a different model.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CancellationLatency {
    /// Synchronous work remaining in the poll active at cancellation time.
    pub remaining_poll: Duration,
    /// Delay until the runtime polls the task where it can observe cancellation.
    pub scheduling_delay: Duration,
    /// Synchronous destructor work after the task observes cancellation.
    pub synchronous_drop: Duration,
}

impl CancellationLatency {
    /// Returns `remaining_poll + scheduling_delay + synchronous_drop`.
    ///
    /// The sum models sequential phases and excludes asynchronous cleanup.
    ///
    /// # Examples
    ///
    /// ```
    /// use std::time::Duration;
    /// use async_runtime_mechanics::CancellationLatency;
    ///
    /// let screen = CancellationLatency {
    ///     remaining_poll: Duration::from_millis(20),
    ///     scheduling_delay: Duration::from_millis(5),
    ///     synchronous_drop: Duration::from_millis(30),
    /// };
    /// assert_eq!(screen.checked_floor(), Some(Duration::from_millis(55)));
    /// ```
    ///
    /// Returns `None` if either intermediate sum exceeds [`Duration::MAX`].
    #[must_use]
    pub fn checked_floor(self) -> Option<Duration> {
        self.remaining_poll
            .checked_add(self.scheduling_delay)?
            .checked_add(self.synchronous_drop)
    }
}

/// Returns the three-phase cooperative cancellation-latency floor.
///
/// The inputs are accounting assumptions, not measurements. The result excludes
/// asynchronous cleanup and does not establish a finite shutdown upper bound.
/// Returns `None` if either intermediate sum exceeds [`Duration::MAX`].
#[must_use]
pub fn cancellation_latency_floor(screen: CancellationLatency) -> Option<Duration> {
    screen.checked_floor()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn future_state_screen_checks_multiplication() {
        assert_eq!(checked_future_state_bytes(8, 4_099), Ok(32_792));
        assert_eq!(checked_future_state_bytes(usize::MAX, 2), Err(CostOverflow));
    }

    #[test]
    fn residency_distinguishes_output_overlap() {
        let base = TaskResidency {
            task_count: 2,
            runtime_bytes_per_task: 10,
            future_bytes: 100,
            output_bytes: 40,
            future_output_residency: FutureOutputResidency::NonOverlapping,
        };
        assert_eq!(base.checked_peak_bytes(), Ok(220));
        assert_eq!(
            TaskResidency {
                future_output_residency: FutureOutputResidency::Overlapping,
                ..base
            }
            .checked_peak_bytes(),
            Ok(300)
        );
    }

    #[test]
    fn residency_checks_each_arithmetic_step() {
        let overflowed_sum = TaskResidency {
            task_count: 1,
            runtime_bytes_per_task: 0,
            future_bytes: usize::MAX,
            output_bytes: 1,
            future_output_residency: FutureOutputResidency::Overlapping,
        };
        assert_eq!(overflowed_sum.checked_peak_bytes(), Err(CostOverflow));

        let overflowed_product = TaskResidency {
            task_count: 2,
            runtime_bytes_per_task: 1,
            future_bytes: usize::MAX / 2,
            output_bytes: 0,
            future_output_residency: FutureOutputResidency::NonOverlapping,
        };
        assert_eq!(overflowed_product.checked_peak_bytes(), Err(CostOverflow));
    }

    #[test]
    fn cancellation_screen_checks_duration_sum() {
        let one_nanosecond = Duration::from_nanos(1);
        let valid = CancellationLatency {
            remaining_poll: Duration::from_secs(1),
            scheduling_delay: Duration::from_secs(2),
            synchronous_drop: Duration::from_secs(3),
        };
        assert_eq!(valid.checked_floor(), Some(Duration::from_secs(6)));

        let overflowed = CancellationLatency {
            remaining_poll: Duration::MAX,
            scheduling_delay: one_nanosecond,
            synchronous_drop: Duration::ZERO,
        };
        assert_eq!(overflowed.checked_floor(), None);
    }
}
