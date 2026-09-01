//! Bounded planning models for a Non-Volatile Memory Express (NVMe) path
//! through Linux's multiqueue block layer (`blk-mq`).
//!
//! Callers supply every limit and cost. The models combine those inputs; they
//! do not inspect Linux, reconstruct queue internals, or predict a device.
//!
//! # Model chain
//!
//! 1. [`effective_queue_depth`] selects the tightest concurrency bound.
//! 2. [`concurrency_limited_iops`] converts that depth and a mean service time
//!    into an input/output operations per second (IOPS) ceiling.
//! 3. [`bandwidth_bytes_per_second`] converts IOPS into byte throughput.
//! 4. [`cpu_batch_cost`] amortizes fixed submission and completion work over a
//!    caller-selected batch size.
//!
//! # Example
//!
//! ```
//! use nvme_blk_mq::{
//!     bandwidth_bytes_per_second, concurrency_limited_iops, cpu_batch_cost,
//!     effective_queue_depth,
//! };
//!
//! let depth = effective_queue_depth(512, 8, 64, 128)?;
//! let iops = concurrency_limited_iops(depth, 500e-6, 200_000.0)?;
//! let bandwidth = bandwidth_bytes_per_second(iops, 4096)?;
//! let cpu = cpu_batch_cost(
//!     iops,
//!     32,
//!     500.0,
//!     800.0,
//!     480.0,
//!     2_500_000_000.0,
//! )?;
//!
//! assert_eq!(depth, 128);
//! assert_eq!(iops, 200_000.0);
//! assert_eq!(bandwidth, 819_200_000.0);
//! assert!((cpu.cycles_per_io - 540.0).abs() < f64::EPSILON);
//! assert!((cpu.required_cores - 0.0432).abs() < 1e-12);
//! # Ok::<(), nvme_blk_mq::CostError>(())
//! ```

use std::error::Error;
use std::fmt;

/// Invalid input or unrepresentable result from a planning model.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CostError {
    /// A floating-point input was NaN or infinite.
    NonFinite,
    /// A finite floating-point input was below zero.
    Negative,
    /// A batch size, latency, or usable cycle rate was zero.
    ZeroDenominator,
    /// Integer or floating-point arithmetic exceeded its result type.
    Overflow,
}

impl fmt::Display for CostError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::NonFinite => "input must be finite",
            Self::Negative => "input must be non-negative",
            Self::ZeroDenominator => "denominator must be positive",
            Self::Overflow => "calculation overflowed",
        };
        formatter.write_str(message)
    }
}

impl Error for CostError {}

fn finite_non_negative(values: &[f64]) -> Result<(), CostError> {
    if values.iter().any(|value| !value.is_finite()) {
        return Err(CostError::NonFinite);
    }
    if values.iter().any(|value| *value < 0.0) {
        return Err(CostError::Negative);
    }
    Ok(())
}

fn positive(value: f64) -> Result<(), CostError> {
    finite_non_negative(&[value])?;
    if value == 0.0 {
        return Err(CostError::ZeroDenominator);
    }
    Ok(())
}

fn finite_result(value: f64) -> Result<f64, CostError> {
    if value.is_finite() {
        Ok(value)
    } else {
        Err(CostError::Overflow)
    }
}

/// Returns the smallest supplied concurrency limit.
///
/// `active_queues * slots_per_queue` is the modeled `blk-mq` slot limit.
/// `application_in_flight` and `device_slots` bound that product from outside
/// the block layer. These inputs are planning bounds, not kernel observations.
///
/// # Errors
///
/// Returns [`CostError::Overflow`] if `active_queues * slots_per_queue`
/// exceeds `u64`.
///
/// # Examples
///
/// ```
/// use nvme_blk_mq::effective_queue_depth;
///
/// assert_eq!(effective_queue_depth(512, 8, 64, 128)?, 128);
/// # Ok::<(), nvme_blk_mq::CostError>(())
/// ```
pub fn effective_queue_depth(
    application_in_flight: u64,
    active_queues: u64,
    slots_per_queue: u64,
    device_slots: u64,
) -> Result<u64, CostError> {
    let block_slots = active_queues
        .checked_mul(slots_per_queue)
        .ok_or(CostError::Overflow)?;
    Ok(application_in_flight.min(block_slots).min(device_slots))
}

/// Returns the lower of the concurrency and device IOPS ceilings.
///
/// The concurrency ceiling is `effective_depth / mean_service_seconds`.
/// This mean-based identity omits service-time variation, queueing delay,
/// scheduling, and workload-dependent device behavior.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if `mean_service_seconds` or `device_iops_cap`
///   is NaN or infinite.
/// - [`CostError::Negative`] if `mean_service_seconds` or `device_iops_cap`
///   is negative.
/// - [`CostError::ZeroDenominator`] if `mean_service_seconds` is zero.
/// - [`CostError::Overflow`] if `effective_depth / mean_service_seconds` is
///   not finite.
///
/// # Examples
///
/// ```
/// use nvme_blk_mq::concurrency_limited_iops;
///
/// let iops = concurrency_limited_iops(128, 500e-6, 200_000.0)?;
/// assert_eq!(iops, 200_000.0);
/// # Ok::<(), nvme_blk_mq::CostError>(())
/// ```
pub fn concurrency_limited_iops(
    effective_depth: u64,
    mean_service_seconds: f64,
    device_iops_cap: f64,
) -> Result<f64, CostError> {
    positive(mean_service_seconds)?;
    finite_non_negative(&[device_iops_cap])?;
    let concurrency_cap = finite_result(effective_depth as f64 / mean_service_seconds)?;
    Ok(concurrency_cap.min(device_iops_cap))
}

/// Converts IOPS and bytes per operation into bytes per second.
///
/// This dimensional conversion does not apply a link, controller, memory, or
/// device bandwidth cap.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if `iops` is NaN or infinite.
/// - [`CostError::Negative`] if `iops` is negative.
/// - [`CostError::Overflow`] if the product is not finite.
///
/// # Examples
///
/// ```
/// use nvme_blk_mq::bandwidth_bytes_per_second;
///
/// let bytes_per_second = bandwidth_bytes_per_second(200_000.0, 4096)?;
/// assert_eq!(bytes_per_second, 819_200_000.0);
/// # Ok::<(), nvme_blk_mq::CostError>(())
/// ```
pub fn bandwidth_bytes_per_second(iops: f64, bytes_per_io: u64) -> Result<f64, CostError> {
    finite_non_negative(&[iops])?;
    finite_result(iops * bytes_per_io as f64)
}

/// CPU cost produced by [`cpu_batch_cost`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CpuBatchCost {
    /// Per-operation cycles after fixed batch work is amortized.
    pub cycles_per_io: f64,
    /// CPU cores consumed at the supplied IOPS and usable cycle rate.
    pub required_cores: f64,
}

/// Computes per-operation cycles and required cores for batched I/O work.
///
/// The model adds `per_io_cycles` to
/// `(fixed_submission_cycles + fixed_completion_cycles) / batch_size`. It then
/// multiplies that cost by `iops` and divides by
/// `usable_cycles_per_core_second`. The caller must supply measured or assumed
/// cycle costs; this function does not measure CPU work.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if a floating-point input is NaN or infinite.
/// - [`CostError::Negative`] if a floating-point input is negative.
/// - [`CostError::ZeroDenominator`] if `batch_size` or
///   `usable_cycles_per_core_second` is zero.
/// - [`CostError::Overflow`] if an intermediate or result is not finite.
///
/// # Examples
///
/// ```
/// use nvme_blk_mq::cpu_batch_cost;
///
/// let cost = cpu_batch_cost(
///     1_000_000.0,
///     32,
///     500.0,
///     800.0,
///     480.0,
///     2_500_000_000.0,
/// )?;
/// assert!((cost.cycles_per_io - 540.0).abs() < f64::EPSILON);
/// assert!((cost.required_cores - 0.216).abs() < 1e-12);
/// # Ok::<(), nvme_blk_mq::CostError>(())
/// ```
pub fn cpu_batch_cost(
    iops: f64,
    batch_size: u64,
    per_io_cycles: f64,
    fixed_submission_cycles: f64,
    fixed_completion_cycles: f64,
    usable_cycles_per_core_second: f64,
) -> Result<CpuBatchCost, CostError> {
    finite_non_negative(&[
        iops,
        per_io_cycles,
        fixed_submission_cycles,
        fixed_completion_cycles,
    ])?;
    positive(usable_cycles_per_core_second)?;
    if batch_size == 0 {
        return Err(CostError::ZeroDenominator);
    }

    let fixed_cycles = finite_result(fixed_submission_cycles + fixed_completion_cycles)?;
    let cycles_per_io = finite_result(per_io_cycles + fixed_cycles / batch_size as f64)?;
    let required_cores = finite_result(iops * cycles_per_io / usable_cycles_per_core_second)?;
    Ok(CpuBatchCost {
        cycles_per_io,
        required_cores,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn effective_depth_uses_each_possible_bottleneck() {
        assert_eq!(effective_queue_depth(64, 8, 32, 512), Ok(64));
        assert_eq!(effective_queue_depth(512, 4, 32, 512), Ok(128));
        assert_eq!(effective_queue_depth(512, 8, 32, 96), Ok(96));
    }

    #[test]
    fn effective_depth_reports_slot_product_overflow() {
        assert_eq!(
            effective_queue_depth(1, u64::MAX, 2, 1),
            Err(CostError::Overflow)
        );
    }

    #[test]
    fn iops_applies_concurrency_and_device_caps() {
        assert_eq!(concurrency_limited_iops(16, 1e-3, 20_000.0), Ok(16_000.0));
        assert_eq!(concurrency_limited_iops(32, 1e-3, 20_000.0), Ok(20_000.0));
    }

    #[test]
    fn iops_rejects_invalid_inputs_and_result_overflow() {
        assert_eq!(
            concurrency_limited_iops(1, f64::NAN, 1.0),
            Err(CostError::NonFinite)
        );
        assert_eq!(
            concurrency_limited_iops(1, -1.0, 1.0),
            Err(CostError::Negative)
        );
        assert_eq!(
            concurrency_limited_iops(1, 0.0, 1.0),
            Err(CostError::ZeroDenominator)
        );
        assert_eq!(
            concurrency_limited_iops(u64::MAX, f64::MIN_POSITIVE, f64::MAX),
            Err(CostError::Overflow)
        );
    }

    #[test]
    fn bandwidth_converts_operation_rate_to_byte_rate() {
        assert_eq!(
            bandwidth_bytes_per_second(200_000.0, 4096),
            Ok(819_200_000.0)
        );
        assert_eq!(
            bandwidth_bytes_per_second(-1.0, 4096),
            Err(CostError::Negative)
        );
        assert_eq!(
            bandwidth_bytes_per_second(f64::MAX, 2),
            Err(CostError::Overflow)
        );
    }

    #[test]
    fn batching_amortizes_fixed_cycles() {
        let cost = cpu_batch_cost(1_000_000.0, 32, 500.0, 800.0, 480.0, 2_500_000_000.0)
            .expect("finite positive model inputs");
        assert!((cost.cycles_per_io - 540.0).abs() < f64::EPSILON);
        assert!((cost.required_cores - 0.216).abs() < 1e-12);
    }

    #[test]
    fn batching_rejects_invalid_denominators_and_overflow() {
        assert_eq!(
            cpu_batch_cost(1.0, 0, 1.0, 1.0, 1.0, 1.0),
            Err(CostError::ZeroDenominator)
        );
        assert_eq!(
            cpu_batch_cost(1.0, 1, 1.0, 1.0, 1.0, 0.0),
            Err(CostError::ZeroDenominator)
        );
        assert_eq!(
            cpu_batch_cost(1.0, 1, 0.0, f64::MAX, f64::MAX, 1.0),
            Err(CostError::Overflow)
        );
    }
}
