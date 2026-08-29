//! Checked accounting identities for CPU service chains.
//!
//! A request can wait on a dependency, wait in its own runnable queue, and
//! execute on a CPU. A lock waiter can also inherit the lock owner's remaining
//! critical-section work, runnable delay, blocking chain, and handoff cost.
//! This crate keeps those terms separate so a measured delay is not silently
//! attributed to execution alone.
//!
//! The helpers also calculate scheduler weight share, simultaneous
//! multithreading (SMT) throughput ratios, deadline utilization, and a simple
//! wake-to-service decomposition. SMT means one physical core exposes multiple
//! hardware threads. These functions are accounting identities, not scheduler,
//! power-state, or microarchitecture simulators.
//!
//! Except for [`WakeService`], time values are unit-neutral: every argument to
//! one formula must use the same unit. [`WakeService`] uses seconds, hertz, and
//! instructions per cycle. The `f64` type does not enforce those units.
//!
//! # Example
//!
//! ```
//! use cpu_service_chain::{
//!     WakeService, deadline_utilization_sum, fair_share, lock_blocking,
//!     response_time, smt_aggregate_gain, smt_symmetric_per_thread_slowdown,
//! };
//!
//! assert_eq!(response_time(2.0, 0.4, 0.06)?, 2.46);
//! assert_eq!(lock_blocking(60.0, 2_000.0, 0.0, 15.0)?, 2_075.0);
//! assert_eq!(fair_share(1_024.0, 2_048.0)?, 0.5);
//! assert_eq!(smt_aggregate_gain(100.0, 150.0)?, 1.5);
//! assert_eq!(smt_symmetric_per_thread_slowdown(100.0, 150.0)?, 0.25);
//! assert_eq!(deadline_utilization_sum(&[(2.0, 10.0), (3.0, 20.0)])?, 0.35);
//!
//! let wake = WakeService::new(20e-6, 80e-6, 1_500_000.0, 1.5, 2e9)?;
//! assert!((wake.execution_seconds() - 500e-6).abs() < 1e-15);
//! assert!((wake.total_seconds() - 600e-6).abs() < 1e-15);
//! # Ok::<(), cpu_service_chain::ModelError>(())
//! ```

#![forbid(unsafe_code)]

use std::error::Error;
use std::fmt::{self, Display, Formatter};

/// Adds dependency blocking, runnable-queue delay, and own execution time.
///
/// The accounting identity is `B_dep + Q_self + X_self`. All three arguments
/// must use the same time unit. The result uses that unit.
///
/// # Errors
///
/// Returns [`ModelError`] when an input is negative or non-finite, or when the
/// sum cannot be represented as a finite `f64`.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::response_time;
///
/// let milliseconds = response_time(2.0, 0.4, 0.06)?;
/// assert_eq!(milliseconds, 2.46);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn response_time(
    dependency_blocking: f64,
    self_queue_delay: f64,
    self_execution_time: f64,
) -> Result<f64, ModelError> {
    validate_non_negative_finite(dependency_blocking, "dependency blocking")?;
    validate_non_negative_finite(self_queue_delay, "self runnable-queue delay")?;
    validate_non_negative_finite(self_execution_time, "self execution time")?;
    finite_sum(
        &[dependency_blocking, self_queue_delay, self_execution_time],
        "response time",
    )
}

/// Adds the service-chain terms that can delay a lock waiter.
///
/// The accounting identity is
/// `C_owner_remaining + Q_owner + B_owner_chain + handoff`. The result is an
/// upper-level decomposition, not a bound unless each supplied component is
/// itself a valid bound. Every argument and the result use the same time unit.
///
/// # Errors
///
/// Returns [`ModelError`] when an input is negative or non-finite, or when the
/// sum cannot be represented as a finite `f64`.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::lock_blocking;
///
/// let microseconds = lock_blocking(60.0, 2_000.0, 0.0, 15.0)?;
/// assert_eq!(microseconds, 2_075.0);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn lock_blocking(
    owner_critical_section_remaining: f64,
    owner_queue_delay: f64,
    owner_blocking_chain: f64,
    handoff_delay: f64,
) -> Result<f64, ModelError> {
    validate_non_negative_finite(
        owner_critical_section_remaining,
        "owner critical-section work remaining",
    )?;
    validate_non_negative_finite(owner_queue_delay, "owner runnable-queue delay")?;
    validate_non_negative_finite(owner_blocking_chain, "owner blocking chain")?;
    validate_non_negative_finite(handoff_delay, "lock handoff delay")?;
    finite_sum(
        &[
            owner_critical_section_remaining,
            owner_queue_delay,
            owner_blocking_chain,
            handoff_delay,
        ],
        "lock blocking",
    )
}

/// Calculates one runnable entity's weight fraction.
///
/// The result is `task_weight / runnable_weight_sum`. The supplied sum must
/// include the task's weight. A zero task weight is accepted and returns zero;
/// the total weight must be positive.
///
/// This fraction describes the configured weight ratio. It does not promise a
/// wall-clock CPU share over a short interval or account for sleeping tasks,
/// affinity, throttling, or capacity differences.
///
/// # Errors
///
/// Returns [`ModelError`] when an input is non-finite, the task weight is
/// negative, the total is not positive, or the task weight exceeds the total.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::fair_share;
///
/// assert_eq!(fair_share(1_024.0, 2_048.0)?, 0.5);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn fair_share(task_weight: f64, runnable_weight_sum: f64) -> Result<f64, ModelError> {
    validate_non_negative_finite(task_weight, "task weight")?;
    validate_positive_finite(runnable_weight_sum, "runnable weight sum")?;
    if task_weight > runnable_weight_sum {
        return Err(ModelError::PartExceedsTotal {
            part: "task weight",
            total: "runnable weight sum",
        });
    }
    finite_result(task_weight / runnable_weight_sum, "fair-share fraction")
}

/// Calculates the two-thread SMT aggregate-throughput factor.
///
/// The result is `two_thread_aggregate / single_thread_throughput`. A result of
/// `1.5` means the two hardware threads completed 1.5 times as much aggregate
/// work as the one-thread baseline. It is a ratio, not a 150% improvement.
/// Both measurements must use the same work and time units.
///
/// # Errors
///
/// Returns [`ModelError`] when the single-thread throughput is not finite and
/// positive, the aggregate throughput is negative or non-finite, or the ratio
/// cannot be represented as a finite `f64`.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::smt_aggregate_gain;
///
/// assert_eq!(smt_aggregate_gain(100.0, 150.0)?, 1.5);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn smt_aggregate_gain(
    single_thread_throughput: f64,
    two_thread_aggregate_throughput: f64,
) -> Result<f64, ModelError> {
    validate_positive_finite(single_thread_throughput, "single-thread throughput")?;
    validate_non_negative_finite(
        two_thread_aggregate_throughput,
        "two-thread aggregate throughput",
    )?;
    finite_result(
        two_thread_aggregate_throughput / single_thread_throughput,
        "SMT aggregate gain",
    )
}

/// Calculates per-thread slowdown under a symmetric SMT split.
///
/// The model assumes each of two hardware threads receives half of the measured
/// aggregate throughput. It returns
/// `1 - two_thread_aggregate / (2 * single_thread_throughput)`. A result of
/// `0.25` means each thread is modeled as 25% slower than the solo baseline.
/// A negative result represents a per-thread speedup rather than an invalid
/// measurement.
///
/// The symmetry assumption is an inference. Aggregate throughput alone cannot
/// prove that both threads made equal progress.
///
/// # Errors
///
/// Returns [`ModelError`] under the same input conditions as
/// [`smt_aggregate_gain`], or when the derived slowdown is not finite.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::smt_symmetric_per_thread_slowdown;
///
/// assert_eq!(smt_symmetric_per_thread_slowdown(100.0, 150.0)?, 0.25);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn smt_symmetric_per_thread_slowdown(
    single_thread_throughput: f64,
    two_thread_aggregate_throughput: f64,
) -> Result<f64, ModelError> {
    let aggregate_gain =
        smt_aggregate_gain(single_thread_throughput, two_thread_aggregate_throughput)?;
    finite_result(1.0 - aggregate_gain / 2.0, "symmetric per-thread slowdown")
}

/// Calculates one deadline task's runtime-to-period utilization.
///
/// Runtime and period must use the same unit. The result is dimensionless.
/// Runtime may exceed the period: a result above one is useful overload
/// evidence and is not rejected.
///
/// # Errors
///
/// Returns [`ModelError`] when runtime is negative or non-finite, period is not
/// finite and positive, or the ratio cannot be represented as a finite `f64`.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::deadline_utilization;
///
/// assert_eq!(deadline_utilization(2.0, 10.0)?, 0.2);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn deadline_utilization(runtime: f64, period: f64) -> Result<f64, ModelError> {
    validate_non_negative_finite(runtime, "deadline runtime")?;
    validate_positive_finite(period, "deadline period")?;
    finite_result(runtime / period, "deadline utilization")
}

/// Sums runtime-to-period utilization for multiple deadline tasks.
///
/// Each tuple is `(runtime, period)` in any consistent time unit. An empty
/// slice has zero utilization. The sum is an accounting demand ratio, not by
/// itself a schedulability proof: deadlines, release patterns, CPU placement,
/// runtime enforcement, and scheduler policy still matter.
///
/// # Errors
///
/// Returns [`ModelError`] when any tuple is invalid according to
/// [`deadline_utilization`] or when the total is not finite.
///
/// # Examples
///
/// ```
/// use cpu_service_chain::deadline_utilization_sum;
///
/// let utilization = deadline_utilization_sum(&[(2.0, 10.0), (3.0, 20.0)])?;
/// assert_eq!(utilization, 0.35);
/// # Ok::<(), cpu_service_chain::ModelError>(())
/// ```
pub fn deadline_utilization_sum(tasks: &[(f64, f64)]) -> Result<f64, ModelError> {
    let mut total = 0.0;
    for &(runtime, period) in tasks {
        let utilization = deadline_utilization(runtime, period)?;
        total = finite_result(total + utilization, "deadline utilization sum")?;
    }
    Ok(total)
}

/// A checked wake-to-service decomposition in seconds.
///
/// The total is the idle-state exit delay plus runnable-queue delay plus a
/// simplified execution component:
///
/// `instructions / (instructions_per_cycle * frequency_hz)`.
///
/// The execution term assumes the supplied instructions-per-cycle value applies
/// throughout the work. It excludes stalls and work not counted in the supplied
/// instruction total, so it is an accounting term rather than a runtime
/// prediction.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct WakeService {
    idle_exit_seconds: f64,
    runnable_queue_seconds: f64,
    execution_seconds: f64,
    total_seconds: f64,
}

impl WakeService {
    /// Creates a checked wake-to-service decomposition.
    ///
    /// `instructions_per_cycle` is the effective parallel instruction rate used
    /// by this simple model. `frequency_hz` is cycles per second.
    ///
    /// # Errors
    ///
    /// Returns [`ModelError`] when a delay or instruction count is negative or
    /// non-finite, when instructions per cycle or frequency is not finite and
    /// positive, or when execution or total time is not finite.
    ///
    /// # Examples
    ///
    /// ```
    /// use cpu_service_chain::WakeService;
    ///
    /// let wake = WakeService::new(20e-6, 80e-6, 1_500_000.0, 1.5, 2e9)?;
    /// assert!((wake.execution_seconds() - 500e-6).abs() < 1e-15);
    /// assert!((wake.total_seconds() - 600e-6).abs() < 1e-15);
    /// # Ok::<(), cpu_service_chain::ModelError>(())
    /// ```
    pub fn new(
        idle_exit_seconds: f64,
        runnable_queue_seconds: f64,
        instructions: f64,
        instructions_per_cycle: f64,
        frequency_hz: f64,
    ) -> Result<Self, ModelError> {
        validate_non_negative_finite(idle_exit_seconds, "idle-exit delay seconds")?;
        validate_non_negative_finite(runnable_queue_seconds, "runnable-queue delay seconds")?;
        validate_non_negative_finite(instructions, "instruction count")?;
        validate_positive_finite(instructions_per_cycle, "instructions per cycle")?;
        validate_positive_finite(frequency_hz, "frequency hertz")?;

        let execution_seconds = finite_result(
            instructions / instructions_per_cycle / frequency_hz,
            "wake execution seconds",
        )?;
        let total_seconds = finite_sum(
            &[idle_exit_seconds, runnable_queue_seconds, execution_seconds],
            "wake-service total seconds",
        )?;

        Ok(Self {
            idle_exit_seconds,
            runnable_queue_seconds,
            execution_seconds,
            total_seconds,
        })
    }

    /// Returns the modeled idle-state exit delay in seconds.
    #[must_use]
    pub const fn idle_exit_seconds(self) -> f64 {
        self.idle_exit_seconds
    }

    /// Returns the modeled runnable-queue delay in seconds.
    #[must_use]
    pub const fn runnable_queue_seconds(self) -> f64 {
        self.runnable_queue_seconds
    }

    /// Returns the instruction-service component in seconds.
    #[must_use]
    pub const fn execution_seconds(self) -> f64 {
        self.execution_seconds
    }

    /// Returns idle exit, runnable queue, and instruction service in seconds.
    #[must_use]
    pub const fn total_seconds(self) -> f64 {
        self.total_seconds
    }
}

/// Invalid input or non-finite output from an accounting helper.
///
/// Invalid caller-controlled numeric inputs are recoverable errors. The helpers
/// do not panic for those inputs.
#[non_exhaustive]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ModelError {
    /// A named input was not a finite number.
    NotFinite(&'static str),
    /// A named input was negative but its domain includes only zero and above.
    Negative(&'static str),
    /// A named denominator or rate was zero or negative.
    NotPositive(&'static str),
    /// A part was larger than a total that is documented to contain it.
    PartExceedsTotal {
        /// Name of the part.
        part: &'static str,
        /// Name of the containing total.
        total: &'static str,
    },
    /// A named derived value could not be represented as a finite `f64`.
    DerivedValueNotFinite(&'static str),
}

impl Display for ModelError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFinite(name) => write!(formatter, "{name} must be finite"),
            Self::Negative(name) => write!(formatter, "{name} must be non-negative"),
            Self::NotPositive(name) => write!(formatter, "{name} must be positive"),
            Self::PartExceedsTotal { part, total } => {
                write!(formatter, "{part} must not exceed {total}")
            }
            Self::DerivedValueNotFinite(name) => {
                write!(formatter, "derived {name} is not finite")
            }
        }
    }
}

impl Error for ModelError {}

fn validate_non_negative_finite(value: f64, name: &'static str) -> Result<(), ModelError> {
    if !value.is_finite() {
        return Err(ModelError::NotFinite(name));
    }
    if value < 0.0 {
        return Err(ModelError::Negative(name));
    }
    Ok(())
}

fn validate_positive_finite(value: f64, name: &'static str) -> Result<(), ModelError> {
    if !value.is_finite() {
        return Err(ModelError::NotFinite(name));
    }
    if value <= 0.0 {
        return Err(ModelError::NotPositive(name));
    }
    Ok(())
}

fn finite_result(value: f64, name: &'static str) -> Result<f64, ModelError> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(ModelError::DerivedValueNotFinite(name))
    }
}

fn finite_sum(values: &[f64], name: &'static str) -> Result<f64, ModelError> {
    values
        .iter()
        .try_fold(0.0, |total, value| finite_result(total + value, name))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_close(actual: f64, expected: f64) {
        let scale = expected.abs().max(1.0);
        assert!(
            (actual - expected).abs() <= scale * 1e-12,
            "actual={actual}, expected={expected}"
        );
    }

    fn assert_error_bounds<T: Error + Send + Sync + 'static>() {}

    #[test]
    fn response_time_matches_lesson_and_accepts_zero_terms() {
        assert_close(response_time(2.0, 0.4, 0.06).expect("valid"), 2.46);
        assert_eq!(response_time(0.0, 0.0, 0.0), Ok(0.0));
    }

    #[test]
    fn response_time_rejects_invalid_inputs_and_overflow() {
        assert_eq!(
            response_time(f64::NAN, 0.0, 0.0),
            Err(ModelError::NotFinite("dependency blocking"))
        );
        assert_eq!(
            response_time(0.0, -1.0, 0.0),
            Err(ModelError::Negative("self runnable-queue delay"))
        );
        assert_eq!(
            response_time(0.0, 0.0, f64::INFINITY),
            Err(ModelError::NotFinite("self execution time"))
        );
        assert_eq!(
            response_time(f64::MAX, f64::MAX, 0.0),
            Err(ModelError::DerivedValueNotFinite("response time"))
        );
    }

    #[test]
    fn lock_blocking_matches_lesson_and_accepts_no_chain() {
        assert_eq!(lock_blocking(60.0, 2_000.0, 0.0, 15.0), Ok(2_075.0));
        assert_eq!(lock_blocking(0.0, 0.0, 0.0, 0.0), Ok(0.0));
    }

    #[test]
    fn lock_blocking_rejects_invalid_inputs_and_overflow() {
        assert_eq!(
            lock_blocking(-1.0, 0.0, 0.0, 0.0),
            Err(ModelError::Negative(
                "owner critical-section work remaining"
            ))
        );
        assert_eq!(
            lock_blocking(0.0, f64::NAN, 0.0, 0.0),
            Err(ModelError::NotFinite("owner runnable-queue delay"))
        );
        assert_eq!(
            lock_blocking(0.0, 0.0, -1.0, 0.0),
            Err(ModelError::Negative("owner blocking chain"))
        );
        assert_eq!(
            lock_blocking(0.0, 0.0, 0.0, f64::INFINITY),
            Err(ModelError::NotFinite("lock handoff delay"))
        );
        assert_eq!(
            lock_blocking(f64::MAX, f64::MAX, 0.0, 0.0),
            Err(ModelError::DerivedValueNotFinite("lock blocking"))
        );
    }

    #[test]
    fn fair_share_matches_equal_and_skewed_weights() {
        assert_eq!(fair_share(1_024.0, 2_048.0), Ok(0.5));
        assert_close(
            fair_share(1_024.0, 1_134.0).expect("valid"),
            0.902_998_236_331_569_7,
        );
        assert_close(
            fair_share(110.0, 1_134.0).expect("valid"),
            0.097_001_763_668_430_34,
        );
        assert_eq!(fair_share(0.0, 1.0), Ok(0.0));
    }

    #[test]
    fn fair_share_rejects_invalid_domains() {
        assert_eq!(
            fair_share(f64::NAN, 1.0),
            Err(ModelError::NotFinite("task weight"))
        );
        assert_eq!(
            fair_share(-1.0, 1.0),
            Err(ModelError::Negative("task weight"))
        );
        assert_eq!(
            fair_share(1.0, 0.0),
            Err(ModelError::NotPositive("runnable weight sum"))
        );
        assert_eq!(
            fair_share(1.0, f64::INFINITY),
            Err(ModelError::NotFinite("runnable weight sum"))
        );
        assert_eq!(
            fair_share(2.0, 1.0),
            Err(ModelError::PartExceedsTotal {
                part: "task weight",
                total: "runnable weight sum",
            })
        );
    }

    #[test]
    fn smt_helpers_match_lesson_and_zero_aggregate() {
        assert_eq!(smt_aggregate_gain(100.0, 150.0), Ok(1.5));
        assert_eq!(smt_symmetric_per_thread_slowdown(100.0, 150.0), Ok(0.25));
        assert_eq!(smt_aggregate_gain(100.0, 0.0), Ok(0.0));
        assert_eq!(smt_symmetric_per_thread_slowdown(100.0, 0.0), Ok(1.0));
    }

    #[test]
    fn smt_helpers_reject_invalid_inputs_and_non_finite_ratio() {
        assert_eq!(
            smt_aggregate_gain(0.0, 1.0),
            Err(ModelError::NotPositive("single-thread throughput"))
        );
        assert_eq!(
            smt_aggregate_gain(f64::NAN, 1.0),
            Err(ModelError::NotFinite("single-thread throughput"))
        );
        assert_eq!(
            smt_aggregate_gain(1.0, -1.0),
            Err(ModelError::Negative("two-thread aggregate throughput"))
        );
        assert_eq!(
            smt_aggregate_gain(1.0, f64::INFINITY),
            Err(ModelError::NotFinite("two-thread aggregate throughput"))
        );
        assert_eq!(
            smt_aggregate_gain(f64::MIN_POSITIVE, f64::MAX),
            Err(ModelError::DerivedValueNotFinite("SMT aggregate gain"))
        );
    }

    #[test]
    fn symmetric_slowdown_reports_negative_values_as_speedup() {
        assert_close(
            smt_symmetric_per_thread_slowdown(100.0, 220.0).expect("valid"),
            -0.1,
        );
    }

    #[test]
    fn deadline_utilization_matches_lesson_and_empty_sum() {
        assert_eq!(deadline_utilization(2.0, 10.0), Ok(0.2));
        assert_close(
            deadline_utilization_sum(&[(2.0, 10.0), (3.0, 20.0)]).expect("valid"),
            0.35,
        );
        assert_eq!(deadline_utilization_sum(&[]), Ok(0.0));
        assert_eq!(deadline_utilization(12.0, 10.0), Ok(1.2));
    }

    #[test]
    fn deadline_utilization_rejects_invalid_inputs_and_overflow() {
        assert_eq!(
            deadline_utilization(-1.0, 10.0),
            Err(ModelError::Negative("deadline runtime"))
        );
        assert_eq!(
            deadline_utilization(f64::NAN, 10.0),
            Err(ModelError::NotFinite("deadline runtime"))
        );
        assert_eq!(
            deadline_utilization(1.0, 0.0),
            Err(ModelError::NotPositive("deadline period"))
        );
        assert_eq!(
            deadline_utilization(1.0, f64::INFINITY),
            Err(ModelError::NotFinite("deadline period"))
        );
        assert_eq!(
            deadline_utilization(f64::MAX, f64::MIN_POSITIVE),
            Err(ModelError::DerivedValueNotFinite("deadline utilization"))
        );
        assert_eq!(
            deadline_utilization_sum(&[(f64::MAX, 1.0), (f64::MAX, 1.0)]),
            Err(ModelError::DerivedValueNotFinite(
                "deadline utilization sum"
            ))
        );
    }

    #[test]
    fn wake_service_matches_lesson_decomposition() {
        let wake = WakeService::new(20e-6, 80e-6, 1_500_000.0, 1.5, 2e9).expect("valid");
        assert_close(wake.idle_exit_seconds(), 20e-6);
        assert_close(wake.runnable_queue_seconds(), 80e-6);
        assert_close(wake.execution_seconds(), 500e-6);
        assert_close(wake.total_seconds(), 600e-6);
    }

    #[test]
    fn wake_service_accepts_zero_work_and_delay() {
        let wake = WakeService::new(0.0, 0.0, 0.0, 1.0, 1.0).expect("valid");
        assert_eq!(wake.execution_seconds(), 0.0);
        assert_eq!(wake.total_seconds(), 0.0);
    }

    #[test]
    fn wake_service_rejects_invalid_input_domains() {
        assert_eq!(
            WakeService::new(-1.0, 0.0, 0.0, 1.0, 1.0),
            Err(ModelError::Negative("idle-exit delay seconds"))
        );
        assert_eq!(
            WakeService::new(0.0, f64::NAN, 0.0, 1.0, 1.0),
            Err(ModelError::NotFinite("runnable-queue delay seconds"))
        );
        assert_eq!(
            WakeService::new(0.0, 0.0, -1.0, 1.0, 1.0),
            Err(ModelError::Negative("instruction count"))
        );
        assert_eq!(
            WakeService::new(0.0, 0.0, 1.0, 0.0, 1.0),
            Err(ModelError::NotPositive("instructions per cycle"))
        );
        assert_eq!(
            WakeService::new(0.0, 0.0, 1.0, 1.0, f64::INFINITY),
            Err(ModelError::NotFinite("frequency hertz"))
        );
    }

    #[test]
    fn wake_service_rejects_non_finite_derived_values() {
        assert_eq!(
            WakeService::new(0.0, 0.0, f64::MAX, f64::MIN_POSITIVE, f64::MIN_POSITIVE,),
            Err(ModelError::DerivedValueNotFinite("wake execution seconds"))
        );
        assert_eq!(
            WakeService::new(f64::MAX, f64::MAX, 0.0, 1.0, 1.0),
            Err(ModelError::DerivedValueNotFinite(
                "wake-service total seconds"
            ))
        );
    }

    #[test]
    fn model_error_is_composable_and_descriptive() {
        assert_error_bounds::<ModelError>();
        assert_eq!(
            ModelError::NotFinite("runtime").to_string(),
            "runtime must be finite"
        );
        assert_eq!(
            ModelError::PartExceedsTotal {
                part: "weight",
                total: "sum",
            }
            .to_string(),
            "weight must not exceed sum"
        );
        assert!(ModelError::NotPositive("period").source().is_none());
    }
}
