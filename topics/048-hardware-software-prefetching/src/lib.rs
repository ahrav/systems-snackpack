//! Arithmetic checks for hardware and software prefetch decisions.
//!
//! A prefetch asks the memory system to start fetching a cache line before an
//! ordinary load needs it. The request helps only when the program can name a
//! valid future address early enough and the line remains useful when demanded.
//! These helpers expose four first-order limits: lead distance, in-flight cache
//! footprint, throughput, and the useful-prefetch fraction needed to repay
//! software overhead. They do not predict elapsed time or cache residency.
//!
//! # Example
//!
//! ```
//! use hardware_software_prefetching::{
//!     LimitingFactor, ModelError, ThroughputInputs, in_flight_bytes,
//!     required_lead_iterations, throughput_ceiling, useful_fraction_break_even,
//! };
//! # fn main() -> Result<(), ModelError> {
//!
//! let distance = required_lead_iterations(240, 6)?;
//! let footprint = in_flight_bytes(distance, 1, 64)?;
//! let bound = throughput_ceiling(ThroughputInputs {
//!     cpu_iterations_per_cycle: 0.5,
//!     maximum_concurrent_misses: 12.0,
//!     miss_latency_cycles: 240.0,
//!     misses_per_iteration: 1.0,
//!     memory_bytes_per_cycle: 16.0,
//!     bytes_per_iteration: 64.0,
//! })?;
//! let threshold = useful_fraction_break_even(0.5, 20.0)?;
//!
//! assert_eq!(distance, 40);
//! assert_eq!(footprint, 2_560);
//! assert_eq!(bound.limiting_factor, LimitingFactor::Concurrency);
//! assert!((threshold - 0.025).abs() < f64::EPSILON);
//! # Ok(())
//! # }
//! ```

#![deny(missing_docs)]

use std::fmt;

/// Invalid or overflowing arithmetic in a prefetch cost model.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ModelError {
    /// An integer input that appears in a divisor or size was zero.
    Zero(&'static str),
    /// A floating-point input or derived result was negative, zero where
    /// forbidden, or non-finite.
    Invalid(&'static str),
    /// A floating-point input was negative or non-finite where zero is allowed.
    Negative(&'static str),
    /// A derived byte count exceeded `u64`.
    Overflow(&'static str),
}

impl fmt::Display for ModelError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Zero(name) => write!(formatter, "{name} must be nonzero"),
            Self::Invalid(name) => write!(formatter, "{name} must be finite and positive"),
            Self::Negative(name) => write!(formatter, "{name} must be finite and nonnegative"),
            Self::Overflow(name) => write!(formatter, "{name} overflows u64"),
        }
    }
}

impl std::error::Error for ModelError {}

/// Returns the smallest whole-iteration prefetch distance that covers latency.
///
/// `latency_cycles` is the observed or assumed time from request to useful
/// data. `cycles_per_iteration` is the useful independent work performed while
/// the request is outstanding. The quotient is a scheduling target, not proof
/// that the line will arrive or remain resident.
///
/// # Errors
///
/// Returns [`ModelError::Zero`] when `cycles_per_iteration` is zero.
pub fn required_lead_iterations(
    latency_cycles: u64,
    cycles_per_iteration: u64,
) -> Result<u64, ModelError> {
    if cycles_per_iteration == 0 {
        return Err(ModelError::Zero("cycles_per_iteration"));
    }
    Ok(latency_cycles.div_ceil(cycles_per_iteration))
}

/// Returns the cache-line footprint created by requests that remain in flight.
///
/// The result is `distance_iterations * lines_per_iteration * line_bytes`.
/// It is an upper-bound accounting value. Hardware can drop hints, merge
/// requests, or evict lines before demand.
///
/// # Errors
///
/// - Returns [`ModelError::Zero`] when `lines_per_iteration` is zero.
/// - Returns [`ModelError::Zero`] when `line_bytes` is zero.
/// - Returns [`ModelError::Overflow`] when the product exceeds `u64`.
pub fn in_flight_bytes(
    distance_iterations: u64,
    lines_per_iteration: u64,
    line_bytes: u64,
) -> Result<u64, ModelError> {
    if lines_per_iteration == 0 {
        return Err(ModelError::Zero("lines_per_iteration"));
    }
    if line_bytes == 0 {
        return Err(ModelError::Zero("line_bytes"));
    }
    distance_iterations
        .checked_mul(lines_per_iteration)
        .and_then(|lines| lines.checked_mul(line_bytes))
        .ok_or(ModelError::Overflow("in-flight byte footprint"))
}

/// Inputs to a first-order steady-state throughput ceiling.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ThroughputInputs {
    /// Maximum iterations per cycle allowed by instruction execution.
    pub cpu_iterations_per_cycle: f64,
    /// Maximum independent cache misses that can overlap.
    pub maximum_concurrent_misses: f64,
    /// Average cycles from a cache miss request to usable data.
    pub miss_latency_cycles: f64,
    /// Average matching cache misses required by one completed iteration.
    pub misses_per_iteration: f64,
    /// Sustained memory bytes delivered per processor cycle.
    pub memory_bytes_per_cycle: f64,
    /// Bytes transferred for each completed iteration.
    pub bytes_per_iteration: f64,
}

/// Component selected for the smallest throughput ceiling.
///
/// Equal ceilings select CPU before concurrency, and concurrency before
/// bandwidth.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LimitingFactor {
    /// Instruction execution is the smallest modeled ceiling.
    Cpu,
    /// Overlapping miss throughput converted to iteration throughput is smallest.
    Concurrency,
    /// Memory bandwidth divided by bytes per iteration is smallest.
    Bandwidth,
}

/// Three component ceilings and their minimum.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ThroughputBound {
    /// Instruction-execution ceiling in iterations per cycle.
    pub cpu_iterations_per_cycle: f64,
    /// Concurrent-miss ceiling in iterations per cycle.
    pub concurrency_iterations_per_cycle: f64,
    /// Memory-bandwidth ceiling in iterations per cycle.
    pub bandwidth_iterations_per_cycle: f64,
    /// Smallest of the three component ceilings.
    pub iterations_per_cycle: f64,
    /// Component that produced `iterations_per_cycle`.
    pub limiting_factor: LimitingFactor,
}

/// Computes the minimum of CPU, concurrent-miss, and bandwidth ceilings.
///
/// The concurrency term is evaluated as `(maximum_concurrent_misses /
/// miss_latency_cycles) / misses_per_iteration`. Sequential division avoids
/// overflow in a multiplied denominator; its floating-point rounding and
/// underflow can differ from the algebraically equivalent product form.
/// The bandwidth term is `memory_bytes_per_cycle / bytes_per_iteration`.
/// The function is a capacity screen. It does not include address-generation,
/// translation, cache-conflict, or queuing effects.
///
/// # Errors
///
/// Returns [`ModelError::Invalid`] when any input is non-finite or not
/// positive, or when a derived ceiling is not representable as a finite
/// positive number.
pub fn throughput_ceiling(inputs: ThroughputInputs) -> Result<ThroughputBound, ModelError> {
    validate_positive(inputs.cpu_iterations_per_cycle, "cpu_iterations_per_cycle")?;
    validate_positive(
        inputs.maximum_concurrent_misses,
        "maximum_concurrent_misses",
    )?;
    validate_positive(inputs.miss_latency_cycles, "miss_latency_cycles")?;
    validate_positive(inputs.misses_per_iteration, "misses_per_iteration")?;
    validate_positive(inputs.memory_bytes_per_cycle, "memory_bytes_per_cycle")?;
    validate_positive(inputs.bytes_per_iteration, "bytes_per_iteration")?;
    // The three-factor ratio is evaluated through mantissa/exponent scaling:
    // a plain division order can overflow or underflow an intermediate for
    // inputs whose true ceiling is representable. Validation below still
    // rejects a ceiling that is genuinely outside f64's range.
    let concurrency = scaled_ratio(
        inputs.maximum_concurrent_misses,
        inputs.miss_latency_cycles,
        inputs.misses_per_iteration,
    );
    let bandwidth = inputs.memory_bytes_per_cycle / inputs.bytes_per_iteration;
    validate_positive(concurrency, "concurrency ceiling")?;
    validate_positive(bandwidth, "bandwidth ceiling")?;
    let (iterations_per_cycle, limiting_factor) = if inputs.cpu_iterations_per_cycle <= concurrency
        && inputs.cpu_iterations_per_cycle <= bandwidth
    {
        (inputs.cpu_iterations_per_cycle, LimitingFactor::Cpu)
    } else if concurrency <= bandwidth {
        (concurrency, LimitingFactor::Concurrency)
    } else {
        (bandwidth, LimitingFactor::Bandwidth)
    };

    Ok(ThroughputBound {
        cpu_iterations_per_cycle: inputs.cpu_iterations_per_cycle,
        concurrency_iterations_per_cycle: concurrency,
        bandwidth_iterations_per_cycle: bandwidth,
        iterations_per_cycle,
        limiting_factor,
    })
}

/// Returns the useful-prefetch fraction needed to repay software overhead.
///
/// The result is `extra_cycles_per_iteration / avoided_stall_cycles_when_useful`.
/// A result above one means the stated cost cannot break even even if every
/// prefetch is useful. This model excludes cache pollution and extra traffic,
/// so a real implementation can require a higher useful fraction.
///
/// # Errors
///
/// - Returns [`ModelError::Negative`] when `extra_cycles_per_iteration` is
///   negative or non-finite.
/// - Returns [`ModelError::Invalid`] when
///   `avoided_stall_cycles_when_useful` is not finite and positive.
/// - Returns [`ModelError::Invalid`] when a positive extra cost produces a
///   fraction that is not representable as a finite positive number.
pub fn useful_fraction_break_even(
    extra_cycles_per_iteration: f64,
    avoided_stall_cycles_when_useful: f64,
) -> Result<f64, ModelError> {
    if !extra_cycles_per_iteration.is_finite() || extra_cycles_per_iteration < 0.0 {
        return Err(ModelError::Negative("extra_cycles_per_iteration"));
    }
    validate_positive(
        avoided_stall_cycles_when_useful,
        "avoided_stall_cycles_when_useful",
    )?;
    let ratio = extra_cycles_per_iteration / avoided_stall_cycles_when_useful;
    // A positive cost with a ratio that underflowed to zero would claim no
    // useful prefetches are needed; an overflow to infinity is equally
    // meaningless. Zero cost legitimately yields a zero ratio.
    if extra_cycles_per_iteration > 0.0 {
        validate_positive(ratio, "break-even fraction")?;
    }
    Ok(ratio)
}

fn validate_positive(value: f64, name: &'static str) -> Result<(), ModelError> {
    if value.is_finite() && value > 0.0 {
        Ok(())
    } else {
        Err(ModelError::Invalid(name))
    }
}

/// Splits a finite positive `f64` into a mantissa in `[1, 2)` and a
/// power-of-two exponent, normalizing subnormal inputs first.
fn split_mantissa_exponent(value: f64) -> (f64, i32) {
    const EXPONENT_MASK: u64 = 0x7ff << 52;
    const EXPONENT_ONE: u64 = 1023 << 52;
    let (value, adjustment) = if value < f64::MIN_POSITIVE {
        // Multiplying a subnormal by an exact power of two is exact and moves
        // it into the range where the exponent bits are meaningful.
        (value * 2f64.powi(64), -64)
    } else {
        (value, 0)
    };
    let bits = value.to_bits();
    let exponent = ((bits >> 52) & 0x7ff) as i32 - 1023 + adjustment;
    let mantissa = f64::from_bits((bits & !EXPONENT_MASK) | EXPONENT_ONE);
    (mantissa, exponent)
}

/// Computes `numerator / (factor_a * factor_b)` for finite positive inputs
/// without intermediate overflow or underflow. The mantissa ratio stays in
/// `(1/4, 2)`, so only the final power-of-two scaling can leave `f64`'s
/// range, and then only when the true value itself does. The result is exact
/// to within a few units in the last place.
fn scaled_ratio(numerator: f64, factor_a: f64, factor_b: f64) -> f64 {
    let (numerator_mantissa, numerator_exponent) = split_mantissa_exponent(numerator);
    let (a_mantissa, a_exponent) = split_mantissa_exponent(factor_a);
    let (b_mantissa, b_exponent) = split_mantissa_exponent(factor_b);
    let mantissa_ratio = numerator_mantissa / a_mantissa / b_mantissa;
    let exponent = numerator_exponent - a_exponent - b_exponent;
    if exponent > 1100 {
        f64::INFINITY
    } else if exponent < -1200 {
        0.0
    } else {
        // Two-step scaling keeps each power-of-two factor representable even
        // when the combined exponent reaches the subnormal boundary.
        let half = exponent / 2;
        mantissa_ratio * 2f64.powi(half) * 2f64.powi(exponent - half)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lead_distance_rounds_up() {
        assert_eq!(required_lead_iterations(240, 6), Ok(40));
        assert_eq!(required_lead_iterations(241, 6), Ok(41));
        assert_eq!(required_lead_iterations(0, 6), Ok(0));
        assert_eq!(
            required_lead_iterations(1, 0),
            Err(ModelError::Zero("cycles_per_iteration"))
        );
    }

    #[test]
    fn footprint_checks_zeros_and_overflow() {
        assert_eq!(in_flight_bytes(40, 1, 64), Ok(2_560));
        assert_eq!(
            in_flight_bytes(1, 0, 64),
            Err(ModelError::Zero("lines_per_iteration"))
        );
        assert_eq!(
            in_flight_bytes(u64::MAX, 2, 64),
            Err(ModelError::Overflow("in-flight byte footprint"))
        );
    }

    #[test]
    fn throughput_reports_each_limiting_factor() {
        let common = ThroughputInputs {
            cpu_iterations_per_cycle: 0.5,
            maximum_concurrent_misses: 12.0,
            miss_latency_cycles: 240.0,
            misses_per_iteration: 1.0,
            memory_bytes_per_cycle: 16.0,
            bytes_per_iteration: 64.0,
        };
        let bound = throughput_ceiling(common).unwrap();
        assert_eq!(bound.limiting_factor, LimitingFactor::Concurrency);
        assert!((bound.iterations_per_cycle - 0.05).abs() < f64::EPSILON);

        let two_misses = throughput_ceiling(ThroughputInputs {
            misses_per_iteration: 2.0,
            ..common
        })
        .unwrap();
        assert!((two_misses.iterations_per_cycle - 0.025).abs() < f64::EPSILON);

        let cpu = throughput_ceiling(ThroughputInputs {
            cpu_iterations_per_cycle: 0.01,
            ..common
        })
        .unwrap();
        assert_eq!(cpu.limiting_factor, LimitingFactor::Cpu);

        let bandwidth = throughput_ceiling(ThroughputInputs {
            maximum_concurrent_misses: 120.0,
            memory_bytes_per_cycle: 1.0,
            ..common
        })
        .unwrap();
        assert_eq!(bandwidth.limiting_factor, LimitingFactor::Bandwidth);
    }

    #[test]
    fn throughput_rejects_invalid_inputs() {
        let invalid = ThroughputInputs {
            cpu_iterations_per_cycle: f64::NAN,
            maximum_concurrent_misses: 12.0,
            miss_latency_cycles: 240.0,
            misses_per_iteration: 1.0,
            memory_bytes_per_cycle: 16.0,
            bytes_per_iteration: 64.0,
        };
        assert_eq!(
            throughput_ceiling(invalid),
            Err(ModelError::Invalid("cpu_iterations_per_cycle"))
        );
    }

    #[test]
    fn throughput_survives_huge_denominator_product() {
        // `miss_latency_cycles * misses_per_iteration` overflows f64, yet the
        // true ceiling is a representable positive subnormal; the product form
        // returned a silent zero bound here.
        let bound = throughput_ceiling(ThroughputInputs {
            cpu_iterations_per_cycle: 4.0,
            maximum_concurrent_misses: 1.0,
            miss_latency_cycles: f64::MAX,
            misses_per_iteration: 2.0,
            memory_bytes_per_cycle: 16.0,
            bytes_per_iteration: 64.0,
        })
        .unwrap();
        assert!(bound.concurrency_iterations_per_cycle > 0.0);
        assert_eq!(bound.limiting_factor, LimitingFactor::Concurrency);
    }

    #[test]
    fn throughput_survives_huge_numerator_and_mixed_factors() {
        // Dividing by the smaller factor first would overflow the
        // intermediate to infinity even though the true ceiling is a
        // representable ~4.49e307.
        let bound = throughput_ceiling(ThroughputInputs {
            cpu_iterations_per_cycle: 4.0,
            maximum_concurrent_misses: f64::MAX,
            miss_latency_cycles: f64::MIN_POSITIVE,
            misses_per_iteration: f64::MAX,
            memory_bytes_per_cycle: 16.0,
            bytes_per_iteration: 64.0,
        })
        .unwrap();
        assert!(bound.concurrency_iterations_per_cycle.is_finite());
        assert!(bound.concurrency_iterations_per_cycle > 4.0e307);
        assert_eq!(bound.limiting_factor, LimitingFactor::Bandwidth);
    }

    #[test]
    fn throughput_preserves_subnormal_operand_ratios() {
        // Smallest subnormal in both the numerator and one factor: the true
        // ceiling is exactly 0.5, but any plain division order loses it to
        // intermediate underflow or overflow.
        let smallest = f64::from_bits(1);
        let bound = throughput_ceiling(ThroughputInputs {
            cpu_iterations_per_cycle: 4.0,
            maximum_concurrent_misses: smallest,
            miss_latency_cycles: 2.0,
            misses_per_iteration: smallest,
            memory_bytes_per_cycle: 16.0,
            bytes_per_iteration: 64.0,
        })
        .unwrap();
        assert_eq!(bound.concurrency_iterations_per_cycle, 0.5);
        assert_eq!(bound.limiting_factor, LimitingFactor::Bandwidth);
    }

    #[test]
    fn throughput_rejects_unrepresentable_ceilings() {
        let common = ThroughputInputs {
            cpu_iterations_per_cycle: 0.5,
            maximum_concurrent_misses: 12.0,
            miss_latency_cycles: 240.0,
            misses_per_iteration: 1.0,
            memory_bytes_per_cycle: 16.0,
            bytes_per_iteration: 64.0,
        };
        let underflow = throughput_ceiling(ThroughputInputs {
            maximum_concurrent_misses: f64::MIN_POSITIVE,
            miss_latency_cycles: f64::MAX,
            misses_per_iteration: f64::MAX,
            ..common
        });
        assert_eq!(underflow, Err(ModelError::Invalid("concurrency ceiling")));
        let overflow = throughput_ceiling(ThroughputInputs {
            memory_bytes_per_cycle: f64::MAX,
            bytes_per_iteration: f64::MIN_POSITIVE,
            ..common
        });
        assert_eq!(overflow, Err(ModelError::Invalid("bandwidth ceiling")));
    }

    #[test]
    fn useful_fraction_exposes_impossible_break_even() {
        assert_eq!(useful_fraction_break_even(0.5, 20.0), Ok(0.025));
        assert_eq!(useful_fraction_break_even(30.0, 20.0), Ok(1.5));
        assert_eq!(useful_fraction_break_even(0.0, 20.0), Ok(0.0));
        assert_eq!(
            useful_fraction_break_even(-1.0, 20.0),
            Err(ModelError::Negative("extra_cycles_per_iteration"))
        );
    }

    #[test]
    fn useful_fraction_rejects_unrepresentable_ratios() {
        assert_eq!(
            useful_fraction_break_even(f64::MIN_POSITIVE, f64::MAX),
            Err(ModelError::Invalid("break-even fraction"))
        );
        assert_eq!(
            useful_fraction_break_even(f64::MAX, f64::MIN_POSITIVE),
            Err(ModelError::Invalid("break-even fraction"))
        );
    }
}
