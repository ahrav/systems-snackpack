//! Provides an A/A checksum workload and order-cancelled analysis for an
//! order-balanced benchmark negative control.
//!
//! Labels `A` and `B` call the same checksum. A fixed-order label effect cannot
//! represent an implementation difference; it combines position, harness, and
//! transient measurement effects.

use std::hint::black_box;
use std::time::Instant;

/// Records both timed positions and their asserted-equal checksum from one
/// [`measure_pair`] call.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PairMeasurement {
    /// First interval, including the `black_box(words)` call.
    pub first_ns: u128,
    /// Second interval, including the `black_box(words)` call.
    pub second_ns: u128,
    /// Value returned by both calls after their equality is asserted.
    pub checksum: u64,
}

/// Adds every word with wrapping arithmetic.
///
/// `#[inline(never)]` requests a distinct function boundary. Linked-image
/// inspection, rather than the attribute alone, establishes whether the final
/// binary retains this symbol and its call sites.
#[inline(never)]
pub fn checksum(words: &[u64]) -> u64 {
    let mut sum = 0u64;
    for &word in words {
        sum = sum.wrapping_add(word);
    }
    sum
}

/// Measures two consecutive calls to [`checksum`].
///
/// Each interval brackets `black_box(words)` and one checksum call with
/// `Instant::now` and `Instant::elapsed`. The equality assertion and
/// [`PairMeasurement`] construction occur after both intervals.
///
/// # Panics
///
/// Panics if the identical calls return different checksums.
pub fn measure_pair(words: &[u64]) -> PairMeasurement {
    let start = Instant::now();
    let first_checksum = checksum(black_box(words));
    let first_ns = start.elapsed().as_nanos();

    let start = Instant::now();
    let second_checksum = checksum(black_box(words));
    let second_ns = start.elapsed().as_nanos();

    assert_eq!(first_checksum, second_checksum);
    PairMeasurement {
        first_ns,
        second_ns,
        checksum: black_box(first_checksum),
    }
}

/// Returns the geometric mean of `A/B` ratios from one `AB` and one `BA` run,
/// cancelling a reciprocal multiplicative position effect.
///
/// Returns `None` when either ratio is non-finite or not strictly positive.
/// Log-space averaging avoids overflow or underflow from multiplying the
/// inputs.
pub fn order_cancelled_ratio(ab_a_over_b: f64, ba_a_over_b: f64) -> Option<f64> {
    if !ab_a_over_b.is_finite()
        || !ba_a_over_b.is_finite()
        || ab_a_over_b <= 0.0
        || ba_a_over_b <= 0.0
    {
        return None;
    }

    Some(((ab_a_over_b.ln() + ba_a_over_b.ln()) / 2.0).exp())
}

#[cfg(test)]
mod tests {
    use super::{checksum, measure_pair, order_cancelled_ratio};

    #[test]
    fn checksum_wraps_without_panicking() {
        assert_eq!(checksum(&[u64::MAX, 2]), 1);
    }

    #[test]
    fn pair_uses_identical_work() {
        let pair = measure_pair(&[1, 2, 3, 4]);
        assert_eq!(pair.checksum, 10);
        assert!(pair.first_ns > 0);
        assert!(pair.second_ns > 0);
    }

    #[test]
    fn reciprocal_position_effect_cancels() {
        let ratio = order_cancelled_ratio(4.0, 0.25).expect("positive ratios");
        assert!((ratio - 1.0).abs() < f64::EPSILON);
    }

    #[test]
    fn invalid_ratios_are_rejected() {
        assert_eq!(order_cancelled_ratio(0.0, 1.0), None);
        assert_eq!(order_cancelled_ratio(f64::INFINITY, 1.0), None);
    }
}
