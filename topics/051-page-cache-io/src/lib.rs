//! Arithmetic models for Linux page-cache reuse, buffered-write headroom,
//! read-ahead, and direct-I/O concurrency.
//!
//! Each calculation accepts already-estimated rates, sizes, or latencies. The
//! results do not predict filesystem, block-device, or kernel policy.

use std::error::Error;
use std::fmt;

/// Invalid input to a page-cache cost calculation.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CostError {
    /// A floating-point input was NaN or infinite.
    NonFinite,
    /// A finite duration, byte count, or rate was below zero.
    Negative,
    /// A finite probability was outside the inclusive range from zero to one.
    InvalidProbability,
    /// A required positive rate, request size, or pass count was zero.
    ZeroDenominator,
    /// A computed direct-I/O queue depth reached the conversion bound.
    Overflow,
    /// A lower bound exceeded the corresponding upper bound.
    InvalidBounds,
}

impl fmt::Display for CostError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::NonFinite => "input must be finite",
            Self::Negative => "input must be non-negative",
            Self::InvalidProbability => "probability must be between zero and one",
            Self::ZeroDenominator => "denominator must be positive",
            Self::Overflow => "result does not fit in the target integer type",
            Self::InvalidBounds => "lower bound exceeds upper bound",
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

/// Computes the average service time for a mix of cache hits and misses.
///
/// A hit fraction of `1.0` selects `hit_seconds`; `0.0` selects
/// `miss_seconds`. The result is a weighted mean, not a tail-latency estimate.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if any argument is NaN or infinite.
/// - [`CostError::Negative`] if `hit_seconds` or `miss_seconds` is negative.
/// - [`CostError::InvalidProbability`] if a finite `hit_fraction` is outside
///   `[0, 1]`.
///
/// # Examples
///
/// ```
/// use page_cache_io::expected_read_seconds;
///
/// let seconds = expected_read_seconds(0.95, 4e-6, 1e-3)?;
/// assert!((seconds - 53.8e-6).abs() < 1e-12);
/// # Ok::<(), page_cache_io::CostError>(())
/// ```
pub fn expected_read_seconds(
    hit_fraction: f64,
    hit_seconds: f64,
    miss_seconds: f64,
) -> Result<f64, CostError> {
    finite_non_negative(&[hit_seconds, miss_seconds])?;
    if !hit_fraction.is_finite() {
        return Err(CostError::NonFinite);
    }
    if !(0.0..=1.0).contains(&hit_fraction) {
        return Err(CostError::InvalidProbability);
    }
    Ok(hit_fraction.mul_add(hit_seconds, (1.0 - hit_fraction) * miss_seconds))
}

/// Returns the byte window that covers the supplied latency and jitter at the
/// supplied throughput.
///
/// The calculation holds throughput constant and assumes sequential
/// consumption.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if any argument is NaN or infinite.
/// - [`CostError::Negative`] if any argument is negative.
/// - [`CostError::ZeroDenominator`] if `bytes_per_second` is zero.
///
/// # Examples
///
/// ```
/// use page_cache_io::required_readahead_bytes;
///
/// let bytes = required_readahead_bytes(1_073_741_824.0, 80e-6, 42e-6)?;
/// assert!((bytes - 130_996.5).abs() < 0.01);
/// # Ok::<(), page_cache_io::CostError>(())
/// ```
pub fn required_readahead_bytes(
    bytes_per_second: f64,
    device_latency_seconds: f64,
    scheduling_jitter_seconds: f64,
) -> Result<f64, CostError> {
    positive(bytes_per_second)?;
    finite_non_negative(&[device_latency_seconds, scheduling_jitter_seconds])?;
    Ok(bytes_per_second * (device_latency_seconds + scheduling_jitter_seconds))
}

/// Computes bytes fetched per byte requested.
///
/// A result of `32.0` means the storage path fetched 32 bytes for every byte
/// the application requested.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if either argument is NaN or infinite.
/// - [`CostError::Negative`] if either argument is negative.
/// - [`CostError::ZeroDenominator`] if `requested_bytes` is zero.
///
/// # Examples
///
/// ```
/// use page_cache_io::read_amplification;
///
/// let amplification = read_amplification(128.0 * 1024.0, 4.0 * 1024.0)?;
/// assert_eq!(amplification, 32.0);
/// # Ok::<(), page_cache_io::CostError>(())
/// ```
pub fn read_amplification(fetched_bytes: f64, requested_bytes: f64) -> Result<f64, CostError> {
    finite_non_negative(&[fetched_bytes])?;
    positive(requested_bytes)?;
    Ok(fetched_bytes / requested_bytes)
}

/// Time before a producer exhausts the dirty-page headroom.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum DirtyHeadroom {
    /// Writeback matches or exceeds production, so dirty bytes do not increase.
    Unbounded,
    /// Seconds to close the threshold gap at the positive net production rate.
    Seconds(f64),
}

/// Computes the time to grow dirty bytes from `background_bytes` to
/// `limit_bytes`.
///
/// The calculation holds both thresholds and both rates constant.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if any argument is NaN or infinite.
/// - [`CostError::Negative`] if any argument is negative.
/// - [`CostError::InvalidBounds`] if `background_bytes` exceeds `limit_bytes`.
///
/// # Examples
///
/// ```
/// use page_cache_io::{DirtyHeadroom, dirty_headroom};
///
/// let result = dirty_headroom(4.8e9, 2.4e9, 4e9, 1e9)?;
/// assert_eq!(result, DirtyHeadroom::Seconds(0.8));
/// # Ok::<(), page_cache_io::CostError>(())
/// ```
pub fn dirty_headroom(
    limit_bytes: f64,
    background_bytes: f64,
    producer_bytes_per_second: f64,
    writeback_bytes_per_second: f64,
) -> Result<DirtyHeadroom, CostError> {
    finite_non_negative(&[
        limit_bytes,
        background_bytes,
        producer_bytes_per_second,
        writeback_bytes_per_second,
    ])?;
    if background_bytes > limit_bytes {
        return Err(CostError::InvalidBounds);
    }
    if background_bytes == limit_bytes {
        return Ok(DirtyHeadroom::Seconds(0.0));
    }
    if producer_bytes_per_second <= writeback_bytes_per_second {
        return Ok(DirtyHeadroom::Unbounded);
    }
    Ok(DirtyHeadroom::Seconds(
        (limit_bytes - background_bytes) / (producer_bytes_per_second - writeback_bytes_per_second),
    ))
}

/// Computes the queue depth needed to cover direct-I/O latency at a target rate.
///
/// The result rounds up because a fractional request cannot be in flight. This
/// lower bound ignores software overhead, device limits, and latency variation.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if any argument is NaN or infinite.
/// - [`CostError::Negative`] if any argument is negative.
/// - [`CostError::ZeroDenominator`] if `request_bytes` is zero.
/// - [`CostError::Overflow`] if the rounded floating-point depth is greater
///   than or equal to `u64::MAX as f64`, which rounds to `2^64`.
///
/// # Examples
///
/// ```
/// use page_cache_io::required_direct_queue_depth;
///
/// let depth = required_direct_queue_depth(3.0 * 1024.0_f64.powi(3), 100e-6, 4096.0)?;
/// assert_eq!(depth, 79);
/// # Ok::<(), page_cache_io::CostError>(())
/// ```
pub fn required_direct_queue_depth(
    target_bytes_per_second: f64,
    latency_seconds: f64,
    request_bytes: f64,
) -> Result<u64, CostError> {
    finite_non_negative(&[target_bytes_per_second, latency_seconds])?;
    positive(request_bytes)?;
    let depth = (target_bytes_per_second * latency_seconds / request_bytes).ceil();
    if depth >= u64::MAX as f64 {
        return Err(CostError::Overflow);
    }
    Ok(depth as u64)
}

/// One workload's estimated buffered and direct-I/O service times.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ReuseLedger {
    /// Setup, eviction, one device pass, and the remaining cache passes, in seconds.
    pub buffered_seconds: f64,
    /// Setup plus one device pass per requested pass, in seconds.
    pub direct_seconds: f64,
}

/// Compares buffered reuse with repeated direct-I/O passes.
///
/// The buffered path pays for one device pass, one cache pass for every reuse,
/// and the supplied eviction pressure. The direct path pays the device cost on
/// every pass. Both paths pay `setup_seconds` once.
///
/// # Errors
///
/// - [`CostError::NonFinite`] if any floating-point argument is NaN or infinite.
/// - [`CostError::Negative`] if `file_bytes`, either rate, `eviction_seconds`,
///   or `setup_seconds` is negative.
/// - [`CostError::ZeroDenominator`] if either rate or `passes` is zero.
///
/// # Examples
///
/// ```
/// use page_cache_io::reuse_ledger;
///
/// let gib = 1024.0_f64.powi(3);
/// let ledger = reuse_ledger(8.0 * gib, 3.0 * gib, 30.0 * gib, 2, 0.4, 0.02)?;
/// assert!(ledger.buffered_seconds < ledger.direct_seconds);
/// # Ok::<(), page_cache_io::CostError>(())
/// ```
pub fn reuse_ledger(
    file_bytes: f64,
    device_bytes_per_second: f64,
    cache_bytes_per_second: f64,
    passes: u64,
    eviction_seconds: f64,
    setup_seconds: f64,
) -> Result<ReuseLedger, CostError> {
    finite_non_negative(&[file_bytes, eviction_seconds, setup_seconds])?;
    positive(device_bytes_per_second)?;
    positive(cache_bytes_per_second)?;
    if passes == 0 {
        return Err(CostError::ZeroDenominator);
    }
    let device_pass = file_bytes / device_bytes_per_second;
    let cache_reuses = passes.saturating_sub(1) as f64 * file_bytes / cache_bytes_per_second;
    Ok(ReuseLedger {
        buffered_seconds: setup_seconds + eviction_seconds + device_pass + cache_reuses,
        direct_seconds: setup_seconds + passes as f64 * device_pass,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expected_read_checks_probability() {
        assert_eq!(
            expected_read_seconds(1.1, 1.0, 2.0),
            Err(CostError::InvalidProbability)
        );
    }

    #[test]
    fn headroom_is_unbounded_when_writeback_keeps_up() {
        assert_eq!(
            dirty_headroom(100.0, 20.0, 10.0, 10.0),
            Ok(DirtyHeadroom::Unbounded)
        );
    }

    #[test]
    fn exhausted_headroom_is_zero_even_when_writeback_keeps_up() {
        assert_eq!(
            dirty_headroom(20.0, 20.0, 10.0, 10.0),
            Ok(DirtyHeadroom::Seconds(0.0))
        );
    }

    #[test]
    fn headroom_rejects_reversed_bounds() {
        assert_eq!(
            dirty_headroom(10.0, 20.0, 3.0, 1.0),
            Err(CostError::InvalidBounds)
        );
    }

    #[test]
    fn queue_depth_rounds_up() {
        assert_eq!(required_direct_queue_depth(10_000.0, 0.1, 512.0), Ok(2));
    }

    #[test]
    fn queue_depth_rejects_the_saturating_cast_boundary() {
        assert_eq!(
            required_direct_queue_depth(u64::MAX as f64, 1.0, 1.0),
            Err(CostError::Overflow)
        );
    }

    #[test]
    fn reuse_switches_with_pass_count() {
        let one = reuse_ledger(8.0, 3.0, 30.0, 1, 0.4, 0.02).unwrap();
        let two = reuse_ledger(8.0, 3.0, 30.0, 2, 0.4, 0.02).unwrap();
        assert!(one.buffered_seconds > one.direct_seconds);
        assert!(two.buffered_seconds < two.direct_seconds);
    }
}
