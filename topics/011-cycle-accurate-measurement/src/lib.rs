//! Arithmetic and workload contracts for the reference-counter experiment.
//!
//! Reference-counter ticks, elapsed nanoseconds, and PMU cycles are different
//! quantities. This crate keeps counter access in the Linux benchmark and keeps
//! conversion and workload logic testable on every workspace host.

/// Errors from fixed-point timestamp conversion.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ConversionError {
    /// The end counter value precedes the start value.
    EndBeforeStart,
    /// The scaled endpoint does not fit in `u64` nanoseconds.
    Overflow,
    /// The requested relative-error budget is zero.
    ZeroErrorBudget,
}

/// Scales an absolute counter endpoint with perf's multiplier and shift.
///
/// The result is `floor(ticks * mult / 2^shift)`. Returns `None` when the result
/// does not fit in `u64`. Use [`endpoint_delta_ns`] for an interval so
/// subtraction happens after each endpoint is rounded.
pub fn scale_absolute_ticks(ticks: u64, mult: u32, shift: u16) -> Option<u64> {
    let product = u128::from(ticks) * u128::from(mult);
    let scaled = product.checked_shr(u32::from(shift)).unwrap_or(0);
    u64::try_from(scaled).ok()
}

/// Converts two absolute counter values and subtracts their converted times.
///
/// `offset` applies to each converted endpoint and therefore cancels. Converting
/// the endpoints before subtraction accounts for their distinct fixed-point
/// rounding phases.
///
/// # Errors
///
/// Returns [`ConversionError::EndBeforeStart`] when `end < start`. Returns
/// [`ConversionError::Overflow`] when a scaled endpoint or its sum with `offset`
/// does not fit in `u64`.
pub fn endpoint_delta_ns(
    start: u64,
    end: u64,
    mult: u32,
    shift: u16,
    offset: u64,
) -> Result<u64, ConversionError> {
    if end < start {
        return Err(ConversionError::EndBeforeStart);
    }
    let start_ns = scale_absolute_ticks(start, mult, shift)
        .and_then(|value| value.checked_add(offset))
        .ok_or(ConversionError::Overflow)?;
    let end_ns = scale_absolute_ticks(end, mult, shift)
        .and_then(|value| value.checked_add(offset))
        .ok_or(ConversionError::Overflow)?;
    end_ns
        .checked_sub(start_ns)
        .ok_or(ConversionError::EndBeforeStart)
}

/// Returns the minimum batch duration for a two-endpoint quantization budget.
///
/// `update_period` must bound each endpoint's quantization error; it and the
/// return value use the same unit. A minimum observed read delta alone does not
/// establish this bound. `error_ppm` expresses the maximum relative
/// quantization contribution in parts per million. The calculation is
/// `ceil(2 * update_period * 1_000_000 / error_ppm)`.
///
/// # Errors
///
/// Returns [`ConversionError::ZeroErrorBudget`] when `error_ppm` is zero.
/// Returns [`ConversionError::Overflow`] when the rounded duration does not fit
/// in `u64`.
pub fn minimum_batch_duration(update_period: u64, error_ppm: u32) -> Result<u64, ConversionError> {
    if error_ppm == 0 {
        return Err(ConversionError::ZeroErrorBudget);
    }
    let numerator = u128::from(update_period)
        .checked_mul(2_000_000)
        .ok_or(ConversionError::Overflow)?;
    let denominator = u128::from(error_ppm);
    let rounded = numerator.div_ceil(denominator);
    u64::try_from(rounded).map_err(|_| ConversionError::Overflow)
}

/// Advances one SplitMix-style dependent recurrence step.
///
/// The recurrence supplies deterministic integer work. It is not a random
/// number generator contract for applications.
#[inline]
pub fn recurrence_step(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

/// Runs `count` recurrence steps through one loop-carried dependency chain.
///
/// This shape estimates latency plus loop effects. Independent chains would
/// estimate throughput and answer a different question.
#[inline(never)]
pub fn dependent_chain(mut value: u64, count: usize) -> u64 {
    for _ in 0..count {
        value = recurrence_step(value);
    }
    std::hint::black_box(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_point_vectors_preserve_endpoint_rounding() {
        assert_eq!(endpoint_delta_ns(100, 223, 1, 0, 50), Ok(123));
        assert_eq!(endpoint_delta_ns(1024, 2048, 1000, 10, 7), Ok(1000));
        assert_eq!(endpoint_delta_ns(5, 9, 3, 1, 0), Ok(6));

        assert_eq!(endpoint_delta_ns(1, 2, 3, 1, 50), Ok(2));
        assert_eq!(scale_absolute_ticks(1, 3, 1), Some(1));
        assert_eq!(scale_absolute_ticks(u64::MAX, u32::MAX, 127), Some(0));
        assert_eq!(scale_absolute_ticks(u64::MAX, u32::MAX, 128), Some(0));
        assert_eq!(scale_absolute_ticks(u64::MAX, u32::MAX, u16::MAX), Some(0));
    }

    #[test]
    fn conversion_rejects_invalid_intervals_and_overflow() {
        assert_eq!(
            endpoint_delta_ns(2, 1, 1, 0, 0),
            Err(ConversionError::EndBeforeStart)
        );
        assert_eq!(
            endpoint_delta_ns(0, u64::MAX, u32::MAX, 0, 0),
            Err(ConversionError::Overflow)
        );
    }

    #[test]
    fn quantization_guard_rounds_up() {
        assert_eq!(minimum_batch_duration(40, 10_000), Ok(8_000));
        assert_eq!(minimum_batch_duration(7, 3_000), Ok(4_667));
        assert_eq!(
            minimum_batch_duration(1, 0),
            Err(ConversionError::ZeroErrorBudget)
        );
    }

    #[test]
    fn dependent_chain_matches_repeated_steps() {
        let seed = 0x243f_6a88_85a3_08d3;
        let mut expected = seed;
        for _ in 0..37 {
            expected = recurrence_step(expected);
        }
        assert_eq!(dependent_chain(seed, 37), expected);
        assert_eq!(dependent_chain(seed, 0), seed);
    }
}
