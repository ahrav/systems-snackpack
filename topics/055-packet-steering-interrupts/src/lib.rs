//! Bounded planning models for Linux packet steering and interrupt work.
//!
//! Receive Side Scaling (RSS), Receive Packet Steering (RPS), Receive Flow
//! Steering (RFS), and Transmit Packet Steering (XPS) act at different stages.
//! These functions keep their costs separate. They combine caller-supplied
//! rates and cycle estimates; they do not inspect a host or predict a driver.
//!
//! # Running example
//!
//! ```
//! use packet_steering_interrupts::{
//!     interrupt_cost, queue_utilization, rfs_cost_delta, rps_cost,
//!     table_alias_probability, xps_core_savings,
//! };
//!
//! let queue = queue_utilization(&[50_000.0; 8], 700.0, 3_000_000_000.0)?;
//! assert!((queue.utilization - 0.093_333_333_333).abs() < 1e-12);
//!
//! let interrupt = interrupt_cost(3_200_000.0, 32, 0.8e-6)?;
//! assert_eq!(interrupt.interrupts_per_second, 100_000.0);
//! assert!((interrupt.required_cores - 0.08).abs() < 1e-12);
//!
//! let rps = rps_cost(
//!     3_200_000.0,
//!     40.0,
//!     80.0,
//!     1.0,
//!     60.0,
//!     900.0,
//!     32,
//!     3_000_000_000.0,
//! )?;
//! assert!((rps.required_cores - 0.222).abs() < 1e-12);
//!
//! let rfs = rfs_cost_delta(
//!     3_200_000.0,
//!     30.0,
//!     2_000.0,
//!     10_000,
//!     80.0,
//!     3_000_000_000.0,
//! )?;
//! assert!((rfs.net_cycles_per_packet + 49.8).abs() < 1e-12);
//! assert!((rfs.required_cores_delta + 0.053_12).abs() < 1e-12);
//!
//! let alias = table_alias_probability(10_000, 65_536)?;
//! assert!((alias - 0.141_504).abs() < 1e-6);
//!
//! let xps = xps_core_savings(
//!     3_200_000.0,
//!     120.0,
//!     40.0,
//!     3_000_000_000.0,
//! )?;
//! assert!((xps - 0.085_333_333_333).abs() < 1e-12);
//! # Ok::<(), packet_steering_interrupts::CostError>(())
//! ```

use std::error::Error;
use std::fmt;

/// Invalid input or unrepresentable output from a planning model.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CostError {
    /// A floating-point input was NaN or infinite.
    NonFinite,
    /// A finite floating-point input was below zero.
    Negative,
    /// A probability or fraction was greater than one.
    OutOfRange,
    /// A rate, batch, table, or cycle denominator was zero.
    ZeroDenominator,
    /// Floating-point arithmetic produced an infinite result.
    Overflow,
}

impl fmt::Display for CostError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::NonFinite => "input must be finite",
            Self::Negative => "input must be non-negative",
            Self::OutOfRange => "fraction must be between zero and one",
            Self::ZeroDenominator => "denominator must be positive",
            Self::Overflow => "calculation overflowed",
        })
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

/// Per-queue arrival, service, and utilization estimates.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct QueueUtilization {
    /// Sum of flow rates assigned to the receive queue, in packets per second.
    pub arrival_packets_per_second: f64,
    /// Modeled receive-queue capacity, in packets per second.
    pub service_packets_per_second: f64,
    /// Arrival rate divided by service rate. Values at or above one are unstable.
    pub utilization: f64,
}

/// Computes the load on one receive queue.
///
/// The arrival rate is the sum of `flow_rates_packets_per_second`. The service
/// rate is `usable_cycles_per_second / receive_cycles_per_packet`. The result
/// is a capacity screen, not a queueing-delay prediction.
///
/// # Errors
///
/// Returns [`CostError::NonFinite`] or [`CostError::Negative`] for invalid
/// floating-point inputs, [`CostError::ZeroDenominator`] for a zero per-packet
/// cost or cycle rate, and [`CostError::Overflow`] for an unrepresentable sum
/// or result.
pub fn queue_utilization(
    flow_rates_packets_per_second: &[f64],
    receive_cycles_per_packet: f64,
    usable_cycles_per_second: f64,
) -> Result<QueueUtilization, CostError> {
    finite_non_negative(flow_rates_packets_per_second)?;
    positive(receive_cycles_per_packet)?;
    positive(usable_cycles_per_second)?;

    let mut arrival = 0.0;
    for rate in flow_rates_packets_per_second {
        arrival = finite_result(arrival + rate)?;
    }
    let service = finite_result(usable_cycles_per_second / receive_cycles_per_packet)?;
    let utilization = finite_result(arrival / service)?;
    Ok(QueueUtilization {
        arrival_packets_per_second: arrival,
        service_packets_per_second: service,
        utilization,
    })
}

/// Interrupt-rate and CPU-work estimates.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct InterruptCost {
    /// Modeled interrupts per second.
    pub interrupts_per_second: f64,
    /// CPU seconds consumed per wall-clock second, also expressed as cores.
    pub required_cores: f64,
}

/// Amortizes fixed interrupt work over a caller-supplied packet batch.
///
/// `interrupts_per_second = packet_rate / packets_per_interrupt`. Required
/// cores equal that rate times `seconds_per_interrupt`.
///
/// # Errors
///
/// Returns [`CostError`] for non-finite or negative inputs, a zero batch, or an
/// unrepresentable result.
pub fn interrupt_cost(
    packet_rate: f64,
    packets_per_interrupt: u64,
    seconds_per_interrupt: f64,
) -> Result<InterruptCost, CostError> {
    finite_non_negative(&[packet_rate, seconds_per_interrupt])?;
    if packets_per_interrupt == 0 {
        return Err(CostError::ZeroDenominator);
    }
    let interrupts = finite_result(packet_rate / packets_per_interrupt as f64)?;
    let cores = finite_result(interrupts * seconds_per_interrupt)?;
    Ok(InterruptCost {
        interrupts_per_second: interrupts,
        required_cores: cores,
    })
}

/// Per-packet and aggregate CPU cost for Receive Packet Steering (RPS).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RpsCost {
    /// Modeled steering cost per packet.
    pub cycles_per_packet: f64,
    /// CPU cores required at the supplied packet rate.
    pub required_cores: f64,
}

/// Computes the CPU cost of RPS software steering.
///
/// The model is:
///
/// `hash + enqueue + remote_fraction * (remote_cache + ipi / ipi_batch)`.
///
/// It does not include later protocol or application work. A remote fraction
/// of one models every packet crossing to a different CPU.
///
/// # Errors
///
/// Returns [`CostError`] for invalid values, a zero IPI batch or cycle rate, or
/// an unrepresentable result.
#[allow(clippy::too_many_arguments)]
pub fn rps_cost(
    packet_rate: f64,
    hash_cycles: f64,
    enqueue_cycles: f64,
    remote_fraction: f64,
    remote_cache_cycles: f64,
    ipi_cycles: f64,
    packets_per_ipi: u64,
    usable_cycles_per_core_second: f64,
) -> Result<RpsCost, CostError> {
    finite_non_negative(&[
        packet_rate,
        hash_cycles,
        enqueue_cycles,
        remote_fraction,
        remote_cache_cycles,
        ipi_cycles,
    ])?;
    if remote_fraction > 1.0 {
        return Err(CostError::OutOfRange);
    }
    if packets_per_ipi == 0 {
        return Err(CostError::ZeroDenominator);
    }
    positive(usable_cycles_per_core_second)?;

    let remote = finite_result(remote_cache_cycles + ipi_cycles / packets_per_ipi as f64)?;
    let per_packet = finite_result(hash_cycles + enqueue_cycles + remote_fraction * remote)?;
    let cores = finite_result(packet_rate * per_packet / usable_cycles_per_core_second)?;
    Ok(RpsCost {
        cycles_per_packet: per_packet,
        required_cores: cores,
    })
}

/// Signed per-packet and aggregate cost change for Receive Flow Steering (RFS).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RfsCostDelta {
    /// Added cost minus saved locality work, in cycles per packet.
    pub net_cycles_per_packet: f64,
    /// Signed change in required cores. Negative values are modeled savings.
    pub required_cores_delta: f64,
}

/// Computes the signed cost change from adding RFS locality tracking.
///
/// The model is `lookup + migration / packets_per_migration - locality_saved`.
/// It exposes the common failure mode directly: frequent flow movement can
/// turn a locality win into extra work.
///
/// # Errors
///
/// Returns [`CostError`] for invalid values, a zero migration interval or
/// cycle rate, or an unrepresentable result.
pub fn rfs_cost_delta(
    packet_rate: f64,
    lookup_cycles: f64,
    migration_cycles: f64,
    packets_per_migration: u64,
    locality_cycles_saved: f64,
    usable_cycles_per_core_second: f64,
) -> Result<RfsCostDelta, CostError> {
    finite_non_negative(&[
        packet_rate,
        lookup_cycles,
        migration_cycles,
        locality_cycles_saved,
    ])?;
    if packets_per_migration == 0 {
        return Err(CostError::ZeroDenominator);
    }
    positive(usable_cycles_per_core_second)?;

    let net = finite_result(
        lookup_cycles + migration_cycles / packets_per_migration as f64 - locality_cycles_saved,
    )?;
    let cores = finite_result(packet_rate * net / usable_cycles_per_core_second)?;
    Ok(RfsCostDelta {
        net_cycles_per_packet: net,
        required_cores_delta: cores,
    })
}

/// Returns the probability that at least one other active flow aliases a slot.
///
/// The model assumes independent uniform placement into `table_entries` slots:
/// `1 - (1 - 1 / table_entries)^(active_flows - 1)`. Real flow hashes and
/// lifetimes may violate both assumptions.
///
/// # Errors
///
/// Returns [`CostError::ZeroDenominator`] when `table_entries` is zero.
pub fn table_alias_probability(active_flows: u64, table_entries: u64) -> Result<f64, CostError> {
    if table_entries == 0 {
        return Err(CostError::ZeroDenominator);
    }
    if active_flows <= 1 {
        return Ok(0.0);
    }
    if table_entries == 1 {
        return Ok(1.0);
    }
    let exponent = (active_flows - 1) as f64 * (-1.0 / table_entries as f64).ln_1p();
    finite_result(-exponent.exp_m1())
}

/// Computes CPU cores saved by a caller-modeled XPS placement change.
///
/// The result is `(before_cycles - after_cycles) * packet_rate / cycle_rate`.
/// It is negative when the selected placement costs more. This model does not
/// assert that XPS caused either cycle estimate.
///
/// # Errors
///
/// Returns [`CostError`] for invalid inputs, a zero cycle rate, or an
/// unrepresentable result.
pub fn xps_core_savings(
    packet_rate: f64,
    before_cycles_per_packet: f64,
    after_cycles_per_packet: f64,
    usable_cycles_per_core_second: f64,
) -> Result<f64, CostError> {
    finite_non_negative(&[
        packet_rate,
        before_cycles_per_packet,
        after_cycles_per_packet,
    ])?;
    positive(usable_cycles_per_core_second)?;
    finite_result(
        packet_rate * (before_cycles_per_packet - after_cycles_per_packet)
            / usable_cycles_per_core_second,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn queue_model_exposes_balanced_and_elephant_load() {
        let balanced = queue_utilization(&[50_000.0; 8], 700.0, 3e9).unwrap();
        assert_eq!(balanced.arrival_packets_per_second, 400_000.0);
        assert!((balanced.service_packets_per_second - 4_285_714.285_714).abs() < 1e-6);
        assert!((balanced.utilization - 0.093_333_333_333).abs() < 1e-12);

        let elephant = queue_utilization(&[5_000_000.0, 350_000.0], 700.0, 3e9).unwrap();
        assert!((elephant.utilization - 1.248_333_333_333).abs() < 1e-12);
    }

    #[test]
    fn interrupt_batch_amortizes_fixed_work() {
        let wide = interrupt_cost(3_200_000.0, 32, 0.8e-6).unwrap();
        let narrow = interrupt_cost(3_200_000.0, 8, 0.8e-6).unwrap();
        assert_eq!(wide.interrupts_per_second, 100_000.0);
        assert!((wide.required_cores - 0.08).abs() < 1e-12);
        assert!((narrow.required_cores - 0.32).abs() < 1e-12);
    }

    #[test]
    fn rps_matches_running_example() {
        let cost = rps_cost(3.2e6, 40.0, 80.0, 1.0, 60.0, 900.0, 32, 3e9).unwrap();
        assert!((cost.cycles_per_packet - 208.125).abs() < 1e-12);
        assert!((cost.required_cores - 0.222).abs() < 1e-12);
    }

    #[test]
    fn rfs_exposes_stable_and_migrating_regimes() {
        let stable = rfs_cost_delta(3.2e6, 30.0, 2_000.0, 10_000, 80.0, 3e9).unwrap();
        let moving = rfs_cost_delta(3.2e6, 30.0, 2_000.0, 100, 20.0, 3e9).unwrap();
        assert!((stable.net_cycles_per_packet + 49.8).abs() < 1e-12);
        assert!((stable.required_cores_delta + 0.053_12).abs() < 1e-12);
        assert_eq!(moving.net_cycles_per_packet, 30.0);
        assert!((moving.required_cores_delta - 0.032).abs() < 1e-12);
    }

    #[test]
    fn alias_model_handles_edges_and_example() {
        assert_eq!(table_alias_probability(0, 65_536), Ok(0.0));
        assert_eq!(table_alias_probability(1, 65_536), Ok(0.0));
        assert_eq!(table_alias_probability(2, 1), Ok(1.0));
        assert_eq!(
            table_alias_probability(10, 0),
            Err(CostError::ZeroDenominator)
        );
        let example = table_alias_probability(10_000, 65_536).unwrap();
        assert!((example - 0.141_504).abs() < 1e-6);
        let large = table_alias_probability(1_u64 << 54, 1_u64 << 54).unwrap();
        assert!((large - (1.0 - (-1.0_f64).exp())).abs() < 1e-12);
    }

    #[test]
    fn xps_savings_can_be_positive_or_negative() {
        assert!(
            (xps_core_savings(3.2e6, 120.0, 40.0, 3e9).unwrap() - 0.085_333_333_333).abs() < 1e-12
        );
        assert!(xps_core_savings(3.2e6, 40.0, 120.0, 3e9).unwrap() < 0.0);
    }

    #[test]
    fn invalid_values_fail_closed() {
        assert_eq!(
            queue_utilization(&[f64::NAN], 1.0, 1.0),
            Err(CostError::NonFinite)
        );
        assert_eq!(interrupt_cost(1.0, 0, 1.0), Err(CostError::ZeroDenominator));
        assert_eq!(
            rps_cost(1.0, 1.0, 1.0, 1.1, 1.0, 1.0, 1, 1.0),
            Err(CostError::OutOfRange)
        );
        assert_eq!(
            rfs_cost_delta(1.0, 1.0, 1.0, 0, 1.0, 1.0),
            Err(CostError::ZeroDenominator)
        );
        assert_eq!(
            xps_core_savings(1.0, 1.0, 1.0, 0.0),
            Err(CostError::ZeroDenominator)
        );
    }
}
