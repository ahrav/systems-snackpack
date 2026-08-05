//! Accounting identities for NIC datapath work, TCP flight size, and socket queues.
//!
//! # Datapath accounting
//!
//! [`compare_transmit_cost`] keeps wire-segment and payload-byte work fixed
//! while changing the number of modeled system calls and software submissions.
//! Scalar sends pay both costs per wire segment, `sendmmsg(2)` groups only
//! system calls, and Generic Segmentation Offload (GSO) groups both costs.
//! [`compare_gro_receive_cost`] keeps wire-packet and payload-byte work fixed
//! while Generic Receive Offload (GRO) groups upper-stack delivery units.
//!
//! # Capacity identities
//!
//! [`tcp_bandwidth_delay_window_bytes`] computes the bytes represented by a bit
//! rate during one round trip. [`listen_backlog_burst_need`] computes the excess
//! completed connections accumulated during a constant-rate burst.
//! [`udp_buffer_fill_time_seconds`] computes when a constant positive byte-rate
//! imbalance fills an initially empty receive buffer.
//!
//! # Model boundary
//!
//! The functions calculate identities over caller-supplied costs, rates,
//! counts, and grouping factors. They do not infer those inputs or model
//! contention, cache state, interrupt scheduling, packet loss, protocol
//! overhead, socket policy, or device limits. Treat a result as a workload
//! prediction only when every input represents the same workload and
//! configuration.
//! Calculations use binary `f64` arithmetic: finite results can round or
//! underflow, while [`ModelError::ArithmeticOverflow`] covers only non-finite
//! derived values.
//!
//! # Example
//!
//! ```
//! use nic_datapath_cost_model::{
//!     TransmitInputs, compare_transmit_cost, tcp_bandwidth_delay_window_bytes,
//! };
//!
//! let costs = compare_transmit_cost(TransmitInputs {
//!     wire_segments: 10,
//!     payload_bytes: 1_000,
//!     syscall_cost_ns: 100.0,
//!     submission_cost_ns: 20.0,
//!     residual_segment_cost_ns: 3.0,
//!     payload_byte_cost_ns: 0.1,
//!     sendmmsg_batch_size: 4,
//!     gso_segments_per_submission: 5,
//! })?;
//! assert_eq!(costs.scalar.total_ns, 1_330.0);
//! assert_eq!(costs.sendmmsg.total_ns, 630.0);
//! assert_eq!(costs.gso.total_ns, 370.0);
//!
//! let window = tcp_bandwidth_delay_window_bytes(10_000_000_000.0, 0.020)?;
//! assert_eq!(window, 25_000_000.0);
//! # Ok::<(), nic_datapath_cost_model::ModelError>(())
//! ```

#![forbid(unsafe_code)]

/// An input-domain violation or non-finite derived result.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ModelError {
    /// The named floating-point input is NaN or positive or negative infinity.
    NonFinite(&'static str),
    /// The named floating-point input is less than zero.
    Negative(&'static str),
    /// The named integer grouping factor is zero.
    MustBePositive(&'static str),
    /// A derived product, quotient, or running sum is not finite.
    ArithmeticOverflow,
}

/// Inputs shared by the three transmit accounting paths.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TransmitInputs {
    /// Number of packets that segmentation ultimately places on the wire.
    pub wire_segments: u64,
    /// Payload bytes represented by all wire segments.
    pub payload_bytes: u64,
    /// Cost assigned to one modeled send system call, in nanoseconds.
    pub syscall_cost_ns: f64,
    /// Cost assigned to one modeled software submission, in nanoseconds.
    pub submission_cost_ns: f64,
    /// Cost assigned to each resulting wire segment, in nanoseconds.
    pub residual_segment_cost_ns: f64,
    /// Payload-processing cost assigned per byte, in nanoseconds.
    pub payload_byte_cost_ns: f64,
    /// Maximum messages placed in one modeled `sendmmsg(2)` call.
    pub sendmmsg_batch_size: u64,
    /// Maximum wire segments represented by one modeled GSO submission.
    pub gso_segments_per_submission: u64,
}

/// Decomposed time cost for one transmit grouping rule.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TransmitCost {
    /// Modeled number of system calls.
    pub syscall_count: u64,
    /// Modeled number of software submissions.
    pub submission_count: u64,
    /// `syscall_count * syscall_cost_ns`.
    pub syscall_component_ns: f64,
    /// `submission_count * submission_cost_ns`.
    pub submission_component_ns: f64,
    /// `wire_segments * residual_segment_cost_ns`.
    pub residual_segment_component_ns: f64,
    /// `payload_bytes * payload_byte_cost_ns`.
    pub payload_byte_component_ns: f64,
    /// Sum of the four component fields, in nanoseconds.
    pub total_ns: f64,
}

/// Transmit costs under scalar, `sendmmsg(2)`, and GSO grouping rules.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TransmitComparison {
    /// One system call and one submission per wire segment.
    pub scalar: TransmitCost,
    /// One submission per wire segment, with system calls amortized across a batch.
    pub sendmmsg: TransmitCost,
    /// System calls and submissions amortized across modeled GSO segments.
    pub gso: TransmitCost,
}

/// Accounts for scalar, `sendmmsg(2)`, and GSO transmit work.
///
/// Each path computes:
///
/// `cost = system_calls * syscall_cost + submissions * submission_cost
///       + wire_segments * residual_segment_cost + payload_bytes * byte_cost`.
///
/// Scalar sends set both counts to `wire_segments`. `sendmmsg(2)` sets the
/// system-call count to `ceil(wire_segments / sendmmsg_batch_size)` but keeps
/// one submission per wire segment. GSO sets both counts to
/// `ceil(wire_segments / gso_segments_per_submission)`. A partial final group
/// counts as one system call or submission; zero wire segments produce zero
/// system calls and submissions.
///
/// The identity holds each unit cost constant across all three paths. It omits
/// hardware queue limits, socket backpressure, packet headers, and maximum GSO
/// byte sizes. It also treats `wire_segments` and `payload_bytes` as independent
/// counts. Modeled non-final `sendmmsg(2)` batches are full; this function does
/// not enforce Linux's per-call vector limit or model partial completion.
///
/// # Errors
///
/// - Returns [`ModelError::NonFinite`] when any `*_cost_ns` input is NaN or
///   infinite.
/// - Returns [`ModelError::Negative`] when any `*_cost_ns` input is less than
///   zero.
/// - Returns [`ModelError::MustBePositive`] when `sendmmsg_batch_size` or
///   `gso_segments_per_submission` is zero.
/// - Returns [`ModelError::ArithmeticOverflow`] when a component product or
///   the four-component sum is not finite.
///
/// # Examples
///
/// ```
/// use nic_datapath_cost_model::{TransmitInputs, compare_transmit_cost};
///
/// let costs = compare_transmit_cost(TransmitInputs {
///     wire_segments: 8,
///     payload_bytes: 8_000,
///     syscall_cost_ns: 50.0,
///     submission_cost_ns: 10.0,
///     residual_segment_cost_ns: 2.0,
///     payload_byte_cost_ns: 0.0,
///     sendmmsg_batch_size: 4,
///     gso_segments_per_submission: 8,
/// })?;
/// assert_eq!(costs.scalar.syscall_count, 8);
/// assert_eq!(costs.sendmmsg.syscall_count, 2);
/// assert_eq!(costs.gso.submission_count, 1);
/// # Ok::<(), nic_datapath_cost_model::ModelError>(())
/// ```
pub fn compare_transmit_cost(inputs: TransmitInputs) -> Result<TransmitComparison, ModelError> {
    validate_non_negative_finite("syscall_cost_ns", inputs.syscall_cost_ns)?;
    validate_non_negative_finite("submission_cost_ns", inputs.submission_cost_ns)?;
    validate_non_negative_finite("residual_segment_cost_ns", inputs.residual_segment_cost_ns)?;
    validate_non_negative_finite("payload_byte_cost_ns", inputs.payload_byte_cost_ns)?;
    validate_positive("sendmmsg_batch_size", inputs.sendmmsg_batch_size)?;
    validate_positive(
        "gso_segments_per_submission",
        inputs.gso_segments_per_submission,
    )?;

    let scalar = transmit_cost(inputs, inputs.wire_segments, inputs.wire_segments)?;
    let sendmmsg = transmit_cost(
        inputs,
        ceiling_div(inputs.wire_segments, inputs.sendmmsg_batch_size),
        inputs.wire_segments,
    )?;
    let gso_units = ceiling_div(inputs.wire_segments, inputs.gso_segments_per_submission);
    let gso = transmit_cost(inputs, gso_units, gso_units)?;

    Ok(TransmitComparison {
        scalar,
        sendmmsg,
        gso,
    })
}

/// Inputs for receive accounting with and without GRO.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct GroReceiveInputs {
    /// Number of packets received from the wire.
    pub wire_packets: u64,
    /// Payload bytes represented by all received packets.
    pub payload_bytes: u64,
    /// Maximum wire packets represented by one modeled GRO delivery unit.
    pub packets_per_gro_unit: u64,
    /// Cost assigned to each wire packet, in nanoseconds.
    pub wire_packet_cost_ns: f64,
    /// Upper-stack cost assigned to each delivered unit, in nanoseconds.
    pub stack_unit_cost_ns: f64,
    /// Payload-processing cost assigned per byte, in nanoseconds.
    pub payload_byte_cost_ns: f64,
}

/// Decomposed time cost for one receive grouping rule.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ReceiveCost {
    /// Number of units delivered to the modeled upper-stack boundary.
    pub stack_unit_count: u64,
    /// `wire_packets * wire_packet_cost_ns`.
    pub wire_packet_component_ns: f64,
    /// `stack_unit_count * stack_unit_cost_ns`.
    pub stack_unit_component_ns: f64,
    /// `payload_bytes * payload_byte_cost_ns`.
    pub payload_byte_component_ns: f64,
    /// Sum of the three component fields, in nanoseconds.
    pub total_ns: f64,
}

/// Receive costs before and after modeled GRO aggregation.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct GroReceiveComparison {
    /// One upper-stack delivery unit per wire packet.
    pub without_gro: ReceiveCost,
    /// Upper-stack delivery units reduced by the supplied aggregation factor.
    pub with_gro: ReceiveCost,
}

/// Accounts for receive work with and without GRO.
///
/// Without GRO, `stack_unit_count` equals `wire_packets`. With GRO, it equals
/// `ceil(wire_packets / packets_per_gro_unit)`. A partial final group counts as
/// one unit, and zero wire packets produce zero units. Both paths preserve the
/// per-wire-packet and per-byte components.
///
/// The identity holds each unit cost constant across both paths and treats
/// `wire_packets` and `payload_bytes` as independent counts. The supplied
/// aggregation factor must represent the workload before the result can serve
/// as a prediction.
///
/// # Errors
///
/// - Returns [`ModelError::NonFinite`] when any `*_cost_ns` input is NaN or
///   infinite.
/// - Returns [`ModelError::Negative`] when any `*_cost_ns` input is less than
///   zero.
/// - Returns [`ModelError::MustBePositive`] when `packets_per_gro_unit` is
///   zero.
/// - Returns [`ModelError::ArithmeticOverflow`] when a component product or
///   the three-component sum is not finite.
///
/// # Examples
///
/// ```
/// use nic_datapath_cost_model::{GroReceiveInputs, compare_gro_receive_cost};
///
/// let costs = compare_gro_receive_cost(GroReceiveInputs {
///     wire_packets: 10,
///     payload_bytes: 1_000,
///     packets_per_gro_unit: 4,
///     wire_packet_cost_ns: 2.0,
///     stack_unit_cost_ns: 10.0,
///     payload_byte_cost_ns: 0.1,
/// })?;
/// assert_eq!(costs.without_gro.stack_unit_count, 10);
/// assert_eq!(costs.with_gro.stack_unit_count, 3);
/// assert_eq!(costs.with_gro.total_ns, 150.0);
/// # Ok::<(), nic_datapath_cost_model::ModelError>(())
/// ```
pub fn compare_gro_receive_cost(
    inputs: GroReceiveInputs,
) -> Result<GroReceiveComparison, ModelError> {
    validate_positive("packets_per_gro_unit", inputs.packets_per_gro_unit)?;
    validate_non_negative_finite("wire_packet_cost_ns", inputs.wire_packet_cost_ns)?;
    validate_non_negative_finite("stack_unit_cost_ns", inputs.stack_unit_cost_ns)?;
    validate_non_negative_finite("payload_byte_cost_ns", inputs.payload_byte_cost_ns)?;

    let without_gro = receive_cost(inputs, inputs.wire_packets)?;
    let with_gro = receive_cost(
        inputs,
        ceiling_div(inputs.wire_packets, inputs.packets_per_gro_unit),
    )?;
    Ok(GroReceiveComparison {
        without_gro,
        with_gro,
    })
}

/// Returns the TCP bandwidth-delay product as a possibly fractional byte count.
///
/// The identity is `bits_per_second * round_trip_seconds / 8`: the bytes
/// transmitted at the supplied rate during one round trip. An effective
/// congestion or receive window smaller than this result cannot keep that many
/// bytes in flight.
///
/// The result does not predict achieved throughput. The identity excludes
/// protocol overhead, congestion control, loss, window scaling limits, and
/// socket autotuning policy. Zero bandwidth or zero round-trip time returns
/// zero.
///
/// # Errors
///
/// - Returns [`ModelError::NonFinite`] when either input is NaN or infinite.
/// - Returns [`ModelError::Negative`] when either input is less than zero.
/// - Returns [`ModelError::ArithmeticOverflow`] when the product is not finite.
///
/// # Examples
///
/// ```
/// use nic_datapath_cost_model::tcp_bandwidth_delay_window_bytes;
///
/// let bytes = tcp_bandwidth_delay_window_bytes(1_000_000_000.0, 0.040)?;
/// assert_eq!(bytes, 5_000_000.0);
/// # Ok::<(), nic_datapath_cost_model::ModelError>(())
/// ```
pub fn tcp_bandwidth_delay_window_bytes(
    bits_per_second: f64,
    round_trip_seconds: f64,
) -> Result<f64, ModelError> {
    validate_non_negative_finite("bits_per_second", bits_per_second)?;
    validate_non_negative_finite("round_trip_seconds", round_trip_seconds)?;
    finite_product(bits_per_second / 8.0, round_trip_seconds)
}

/// Returns the excess completed connections accumulated during a constant-rate burst.
///
/// The identity multiplies each rate by `burst_duration_seconds`, then clamps
/// `arrivals - accepts` to zero. The result is a possibly fractional connection
/// count; round it up before using it as an integer capacity requirement.
///
/// The identity begins with an empty completed-connection queue. It excludes
/// the separate half-open SYN queue, scheduler pauses, retransmissions,
/// per-socket kernel caps, and time-varying rates.
///
/// # Errors
///
/// - Returns [`ModelError::NonFinite`] when any input is NaN or infinite.
/// - Returns [`ModelError::Negative`] when any input is less than zero.
/// - Returns [`ModelError::ArithmeticOverflow`] when either the arrival or
///   acceptance product is not finite.
///
/// # Examples
///
/// ```
/// use nic_datapath_cost_model::listen_backlog_burst_need;
///
/// let connections = listen_backlog_burst_need(12_000.0, 8_000.0, 0.250)?;
/// assert_eq!(connections, 1_000.0);
/// # Ok::<(), nic_datapath_cost_model::ModelError>(())
/// ```
pub fn listen_backlog_burst_need(
    arrival_connections_per_second: f64,
    accept_connections_per_second: f64,
    burst_duration_seconds: f64,
) -> Result<f64, ModelError> {
    validate_non_negative_finite(
        "arrival_connections_per_second",
        arrival_connections_per_second,
    )?;
    validate_non_negative_finite(
        "accept_connections_per_second",
        accept_connections_per_second,
    )?;
    validate_non_negative_finite("burst_duration_seconds", burst_duration_seconds)?;

    let arrivals = finite_product(arrival_connections_per_second, burst_duration_seconds)?;
    let accepts = finite_product(accept_connections_per_second, burst_duration_seconds)?;
    Ok((arrivals - accepts).max(0.0))
}

/// Returns the fill time for an initially empty UDP byte buffer under constant rates.
///
/// A zero-capacity buffer returns `Some(0.0)`. For positive capacity, `None`
/// means the drain rate matches or exceeds the incoming rate. Otherwise the
/// returned time is
/// `capacity_bytes / (incoming_bytes_per_second - drain_bytes_per_second)`.
///
/// The identity excludes burst timing, datagram metadata, kernel
/// buffer-accounting multipliers, socket caps, scheduling delays, and
/// packet-count limits; it does not predict drop time when those factors
/// matter.
///
/// # Errors
///
/// - Returns [`ModelError::NonFinite`] when any input is NaN or infinite.
/// - Returns [`ModelError::Negative`] when any input is less than zero.
/// - Returns [`ModelError::ArithmeticOverflow`] when positive capacity and a
///   positive rate imbalance produce a non-finite quotient.
///
/// # Examples
///
/// ```
/// use nic_datapath_cost_model::udp_buffer_fill_time_seconds;
///
/// let seconds = udp_buffer_fill_time_seconds(1_048_576.0, 3_145_728.0, 1_048_576.0)?;
/// assert_eq!(seconds, Some(0.5));
/// assert_eq!(udp_buffer_fill_time_seconds(1_000.0, 50.0, 50.0)?, None);
/// # Ok::<(), nic_datapath_cost_model::ModelError>(())
/// ```
pub fn udp_buffer_fill_time_seconds(
    capacity_bytes: f64,
    incoming_bytes_per_second: f64,
    drain_bytes_per_second: f64,
) -> Result<Option<f64>, ModelError> {
    validate_non_negative_finite("capacity_bytes", capacity_bytes)?;
    validate_non_negative_finite("incoming_bytes_per_second", incoming_bytes_per_second)?;
    validate_non_negative_finite("drain_bytes_per_second", drain_bytes_per_second)?;

    if capacity_bytes == 0.0 {
        return Ok(Some(0.0));
    }
    if incoming_bytes_per_second <= drain_bytes_per_second {
        return Ok(None);
    }

    let seconds = capacity_bytes / (incoming_bytes_per_second - drain_bytes_per_second);
    if !seconds.is_finite() {
        return Err(ModelError::ArithmeticOverflow);
    }
    Ok(Some(seconds))
}

fn transmit_cost(
    inputs: TransmitInputs,
    syscall_count: u64,
    submission_count: u64,
) -> Result<TransmitCost, ModelError> {
    let syscall_component_ns = scaled_cost(syscall_count, inputs.syscall_cost_ns)?;
    let submission_component_ns = scaled_cost(submission_count, inputs.submission_cost_ns)?;
    let residual_segment_component_ns =
        scaled_cost(inputs.wire_segments, inputs.residual_segment_cost_ns)?;
    let payload_byte_component_ns = scaled_cost(inputs.payload_bytes, inputs.payload_byte_cost_ns)?;
    let total_ns = finite_sum([
        syscall_component_ns,
        submission_component_ns,
        residual_segment_component_ns,
        payload_byte_component_ns,
    ])?;

    Ok(TransmitCost {
        syscall_count,
        submission_count,
        syscall_component_ns,
        submission_component_ns,
        residual_segment_component_ns,
        payload_byte_component_ns,
        total_ns,
    })
}

fn receive_cost(
    inputs: GroReceiveInputs,
    stack_unit_count: u64,
) -> Result<ReceiveCost, ModelError> {
    let wire_packet_component_ns = scaled_cost(inputs.wire_packets, inputs.wire_packet_cost_ns)?;
    let stack_unit_component_ns = scaled_cost(stack_unit_count, inputs.stack_unit_cost_ns)?;
    let payload_byte_component_ns = scaled_cost(inputs.payload_bytes, inputs.payload_byte_cost_ns)?;
    let total_ns = finite_sum([
        wire_packet_component_ns,
        stack_unit_component_ns,
        payload_byte_component_ns,
    ])?;

    Ok(ReceiveCost {
        stack_unit_count,
        wire_packet_component_ns,
        stack_unit_component_ns,
        payload_byte_component_ns,
        total_ns,
    })
}

fn validate_non_negative_finite(name: &'static str, value: f64) -> Result<(), ModelError> {
    if !value.is_finite() {
        return Err(ModelError::NonFinite(name));
    }
    if value < 0.0 {
        return Err(ModelError::Negative(name));
    }
    Ok(())
}

fn validate_positive(name: &'static str, value: u64) -> Result<(), ModelError> {
    if value == 0 {
        return Err(ModelError::MustBePositive(name));
    }
    Ok(())
}

// Every `divisor` is nonzero because public entry points validate grouping factors.
fn ceiling_div(value: u64, divisor: u64) -> u64 {
    value / divisor + u64::from(!value.is_multiple_of(divisor))
}

fn scaled_cost(count: u64, unit_cost: f64) -> Result<f64, ModelError> {
    finite_product(count as f64, unit_cost)
}

fn finite_product(left: f64, right: f64) -> Result<f64, ModelError> {
    let product = left * right;
    if product.is_finite() {
        Ok(product)
    } else {
        Err(ModelError::ArithmeticOverflow)
    }
}

fn finite_sum<const N: usize>(values: [f64; N]) -> Result<f64, ModelError> {
    values.into_iter().try_fold(0.0, |sum, value| {
        let next = sum + value;
        if next.is_finite() {
            Ok(next)
        } else {
            Err(ModelError::ArithmeticOverflow)
        }
    })
}

#[cfg(test)]
mod tests {
    use super::{
        GroReceiveInputs, ModelError, TransmitInputs, compare_gro_receive_cost,
        compare_transmit_cost, listen_backlog_burst_need, tcp_bandwidth_delay_window_bytes,
        udp_buffer_fill_time_seconds,
    };

    fn transmit_inputs() -> TransmitInputs {
        TransmitInputs {
            wire_segments: 10,
            payload_bytes: 1_000,
            syscall_cost_ns: 100.0,
            submission_cost_ns: 20.0,
            residual_segment_cost_ns: 3.0,
            payload_byte_cost_ns: 0.1,
            sendmmsg_batch_size: 4,
            gso_segments_per_submission: 5,
        }
    }

    #[test]
    fn transmit_accounting_separates_batching_levels() {
        let costs = compare_transmit_cost(transmit_inputs()).unwrap();

        assert_eq!(
            (costs.scalar.syscall_count, costs.scalar.submission_count),
            (10, 10)
        );
        assert_eq!(costs.scalar.total_ns, 1_330.0);
        assert_eq!(
            (
                costs.sendmmsg.syscall_count,
                costs.sendmmsg.submission_count
            ),
            (3, 10)
        );
        assert_eq!(costs.sendmmsg.total_ns, 630.0);
        assert_eq!(
            (costs.gso.syscall_count, costs.gso.submission_count),
            (2, 2)
        );
        assert_eq!(costs.gso.total_ns, 370.0);
    }

    #[test]
    fn transmit_zero_work_has_zero_cost() {
        let mut inputs = transmit_inputs();
        inputs.wire_segments = 0;
        inputs.payload_bytes = 0;

        let costs = compare_transmit_cost(inputs).unwrap();
        assert_eq!(costs.scalar.total_ns, 0.0);
        assert_eq!(costs.sendmmsg.syscall_count, 0);
        assert_eq!(costs.gso.submission_count, 0);
    }

    #[test]
    fn transmit_rejects_invalid_costs_grouping_and_overflow() {
        let mut inputs = transmit_inputs();
        inputs.syscall_cost_ns = f64::NAN;
        assert_eq!(
            compare_transmit_cost(inputs),
            Err(ModelError::NonFinite("syscall_cost_ns"))
        );

        let mut inputs = transmit_inputs();
        inputs.submission_cost_ns = -1.0;
        assert_eq!(
            compare_transmit_cost(inputs),
            Err(ModelError::Negative("submission_cost_ns"))
        );

        let mut inputs = transmit_inputs();
        inputs.sendmmsg_batch_size = 0;
        assert_eq!(
            compare_transmit_cost(inputs),
            Err(ModelError::MustBePositive("sendmmsg_batch_size"))
        );

        let mut inputs = transmit_inputs();
        inputs.syscall_cost_ns = f64::MAX;
        assert_eq!(
            compare_transmit_cost(inputs),
            Err(ModelError::ArithmeticOverflow)
        );
    }

    #[test]
    fn gro_preserves_wire_work_and_reduces_stack_units() {
        let costs = compare_gro_receive_cost(GroReceiveInputs {
            wire_packets: 10,
            payload_bytes: 1_000,
            packets_per_gro_unit: 4,
            wire_packet_cost_ns: 2.0,
            stack_unit_cost_ns: 10.0,
            payload_byte_cost_ns: 0.1,
        })
        .unwrap();

        assert_eq!(costs.without_gro.stack_unit_count, 10);
        assert_eq!(costs.without_gro.total_ns, 220.0);
        assert_eq!(costs.with_gro.stack_unit_count, 3);
        assert_eq!(costs.with_gro.wire_packet_component_ns, 20.0);
        assert_eq!(costs.with_gro.total_ns, 150.0);
    }

    #[test]
    fn gro_rejects_zero_grouping_and_non_finite_cost() {
        let mut inputs = GroReceiveInputs {
            wire_packets: 1,
            payload_bytes: 1,
            packets_per_gro_unit: 0,
            wire_packet_cost_ns: 0.0,
            stack_unit_cost_ns: 0.0,
            payload_byte_cost_ns: 0.0,
        };
        assert_eq!(
            compare_gro_receive_cost(inputs),
            Err(ModelError::MustBePositive("packets_per_gro_unit"))
        );

        inputs.packets_per_gro_unit = 1;
        inputs.stack_unit_cost_ns = f64::INFINITY;
        assert_eq!(
            compare_gro_receive_cost(inputs),
            Err(ModelError::NonFinite("stack_unit_cost_ns"))
        );
    }

    #[test]
    fn tcp_window_is_bandwidth_times_round_trip_time() {
        assert_eq!(
            tcp_bandwidth_delay_window_bytes(10_000_000_000.0, 0.020),
            Ok(25_000_000.0)
        );
        assert_eq!(tcp_bandwidth_delay_window_bytes(0.0, 1.0), Ok(0.0));
    }

    #[test]
    fn backlog_accounts_for_arrivals_not_drained_during_burst() {
        assert_eq!(
            listen_backlog_burst_need(12_000.0, 8_000.0, 0.25),
            Ok(1_000.0)
        );
        assert_eq!(listen_backlog_burst_need(8_000.0, 12_000.0, 0.25), Ok(0.0));
    }

    #[test]
    fn udp_fill_time_handles_growth_balance_and_zero_capacity() {
        assert_eq!(
            udp_buffer_fill_time_seconds(1_048_576.0, 3_145_728.0, 1_048_576.0),
            Ok(Some(0.5))
        );
        assert_eq!(udp_buffer_fill_time_seconds(1_000.0, 50.0, 50.0), Ok(None));
        assert_eq!(udp_buffer_fill_time_seconds(0.0, 0.0, 0.0), Ok(Some(0.0)));
    }

    #[test]
    fn scalar_models_reject_negative_and_non_finite_inputs() {
        assert_eq!(
            tcp_bandwidth_delay_window_bytes(-1.0, 1.0),
            Err(ModelError::Negative("bits_per_second"))
        );
        assert_eq!(
            listen_backlog_burst_need(1.0, f64::NAN, 1.0),
            Err(ModelError::NonFinite("accept_connections_per_second"))
        );
        assert_eq!(
            udp_buffer_fill_time_seconds(1.0, 2.0, -1.0),
            Err(ModelError::Negative("drain_bytes_per_second"))
        );
    }
}
