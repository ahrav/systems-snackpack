//! Checked accounting models for dynamic random-access memory (DRAM).
//!
//! A memory request can find its row already open, find no row open, or need
//! to close a different row first. [`BankState`] names those three cases.
//! [`DramTiming`] adds the timing components for each case, and
//! [`expected_device_component_ns`] takes a validated weighted average.
//!
//! The other helpers make each quantity's unit explicit in its name and
//! documentation. They apply Little's law, calculate data-pin bandwidth,
//! select the smallest supplied throughput ceiling, and calculate a refresh
//! schedule fraction. The `f64` types do not enforce those dimensional labels.
//!
//! These functions are accounting and consistency models. They do not model a
//! controller's queue, address mapping, bank parallelism, command-scheduling
//! constraints, refresh scheduling, contention, or host-observed load-to-use
//! latency.
//!
//! # Example
//!
//! ```
//! use dram_memory_controller_behavior::{
//!     BankStateMix, DramTiming, expected_device_component_ns, pin_bandwidth,
//!     required_inflight,
//! };
//!
//! let timing = DramTiming::new(14.0, 2.5, 14.0, 14.0)?;
//! let mix = BankStateMix::new(0.50, 0.20, 0.30)?;
//!
//! let expected = expected_device_component_ns(timing, mix)?;
//! assert!((expected - 27.70).abs() < 1e-12);
//! assert_eq!(required_inflight(20e9, 100e-9, 64.0)?, 31.25);
//! assert_eq!(pin_bandwidth(4.8e9, 32)?, 19.2e9);
//! # Ok::<(), dram_memory_controller_behavior::ModelError>(())
//! ```

#![forbid(unsafe_code)]

use std::error::Error;
use std::fmt::{self, Display, Formatter};

const PROBABILITY_SUM_TOLERANCE: f64 = 1e-12;

/// A bank's row state when a memory command is considered.
///
/// This classification describes one request at one bank. It does not predict
/// how physical addresses map to banks or how a controller reorders requests.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BankState {
    /// The requested row is already open.
    Hit,
    /// No row is open, so the requested row must be activated.
    Closed,
    /// A different row is open and must be precharged before activation.
    Conflict,
}

/// Validated DRAM timing components in nanoseconds.
///
/// The model uses column access latency (`tCL`), burst duration (`tBURST`),
/// row-to-column delay (`tRCD`), and precharge time (`tRP`). The names follow
/// common DRAM notation, but the caller must supply values that belong to the
/// same device, operating point, and command interpretation. The type does not
/// encode or verify that relationship.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DramTiming {
    t_cl_ns: f64,
    t_burst_ns: f64,
    t_rcd_ns: f64,
    t_rp_ns: f64,
}

impl DramTiming {
    /// Creates a timing set after validating the inputs and row-conflict sum.
    ///
    /// Arguments are `tCL`, `tBURST`, `tRCD`, and `tRP`, in that order. Each
    /// value may be zero for a deliberately simplified accounting model, but
    /// it must be finite and non-negative.
    ///
    /// # Errors
    ///
    /// Returns [`ModelError`] when a value is negative or non-finite, or when
    /// the sum for a row conflict cannot be represented as a finite `f64`.
    ///
    /// # Examples
    ///
    /// ```
    /// use dram_memory_controller_behavior::{BankState, DramTiming};
    ///
    /// let timing = DramTiming::new(14.0, 2.5, 14.0, 14.0)?;
    /// assert_eq!(timing.device_component_ns(BankState::Hit), 16.5);
    /// assert_eq!(timing.device_component_ns(BankState::Closed), 30.5);
    /// assert_eq!(timing.device_component_ns(BankState::Conflict), 44.5);
    /// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
    /// ```
    pub fn new(
        t_cl_ns: f64,
        t_burst_ns: f64,
        t_rcd_ns: f64,
        t_rp_ns: f64,
    ) -> Result<Self, ModelError> {
        validate_non_negative_finite(t_cl_ns, "t_cl_ns")?;
        validate_non_negative_finite(t_burst_ns, "t_burst_ns")?;
        validate_non_negative_finite(t_rcd_ns, "t_rcd_ns")?;
        validate_non_negative_finite(t_rp_ns, "t_rp_ns")?;

        let timing = Self {
            t_cl_ns,
            t_burst_ns,
            t_rcd_ns,
            t_rp_ns,
        };
        if !timing.device_component_ns(BankState::Conflict).is_finite() {
            return Err(ModelError::DerivedValueNotFinite(
                "row-conflict device component",
            ));
        }
        Ok(timing)
    }

    /// Returns column access latency (`tCL`) in nanoseconds.
    #[must_use]
    pub const fn t_cl_ns(self) -> f64 {
        self.t_cl_ns
    }

    /// Returns burst duration (`tBURST`) in nanoseconds.
    #[must_use]
    pub const fn t_burst_ns(self) -> f64 {
        self.t_burst_ns
    }

    /// Returns row-to-column delay (`tRCD`) in nanoseconds.
    #[must_use]
    pub const fn t_rcd_ns(self) -> f64 {
        self.t_rcd_ns
    }

    /// Returns precharge time (`tRP`) in nanoseconds.
    #[must_use]
    pub const fn t_rp_ns(self) -> f64 {
        self.t_rp_ns
    }

    /// Returns the modeled device component for one bank state.
    ///
    /// The accounting is:
    ///
    /// - hit: `tCL + tBURST`;
    /// - closed: `tRCD + tCL + tBURST`;
    /// - conflict: `tRP + tRCD + tCL + tBURST`.
    ///
    /// It excludes controller queueing, interconnect time, cache lookup time,
    /// and overlap with other banks.
    #[must_use]
    pub fn device_component_ns(self, state: BankState) -> f64 {
        let hit = self.t_cl_ns + self.t_burst_ns;
        match state {
            BankState::Hit => hit,
            BankState::Closed => self.t_rcd_ns + hit,
            BankState::Conflict => self.t_rp_ns + self.t_rcd_ns + hit,
        }
    }
}

/// A validated probability distribution over [`BankState`] values.
///
/// [`BankStateMix::new`] requires finite probabilities in the inclusive range
/// from zero to one. Their sum must be within `1e-12` of one. It then
/// normalizes the accepted values so later calculations use a convex mixture.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct BankStateMix {
    hit: f64,
    closed: f64,
    conflict: f64,
}

impl BankStateMix {
    /// Validates and normalizes hit, closed-bank, and conflict probabilities.
    ///
    /// # Errors
    ///
    /// Returns [`ModelError`] when a probability is outside `[0, 1]`, is not
    /// finite, or when the three probabilities do not sum to one within
    /// `1e-12`.
    ///
    /// # Examples
    ///
    /// ```
    /// use dram_memory_controller_behavior::{BankState, BankStateMix};
    ///
    /// let mix = BankStateMix::new(0.50, 0.20, 0.30)?;
    /// assert_eq!(mix.probability(BankState::Hit), 0.50);
    /// assert_eq!(mix.probability(BankState::Closed), 0.20);
    /// assert_eq!(mix.probability(BankState::Conflict), 0.30);
    /// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
    /// ```
    pub fn new(hit: f64, closed: f64, conflict: f64) -> Result<Self, ModelError> {
        validate_probability(hit, "hit probability")?;
        validate_probability(closed, "closed probability")?;
        validate_probability(conflict, "conflict probability")?;

        let sum = hit + closed + conflict;
        if !sum.is_finite() || (sum - 1.0).abs() > PROBABILITY_SUM_TOLERANCE {
            return Err(ModelError::ProbabilitySum);
        }

        Ok(Self {
            hit: hit / sum,
            closed: closed / sum,
            conflict: conflict / sum,
        })
    }

    /// Returns the normalized probability for `state`.
    #[must_use]
    pub const fn probability(self, state: BankState) -> f64 {
        match state {
            BankState::Hit => self.hit,
            BankState::Closed => self.closed,
            BankState::Conflict => self.conflict,
        }
    }
}

/// Returns the probability-weighted device component in nanoseconds.
///
/// This is a mean of the three values from
/// [`DramTiming::device_component_ns`]. It is not a latency percentile and does
/// not include controller, interconnect, cache, or processor time.
///
/// # Errors
///
/// Returns [`ModelError`] if the weighted sum is not finite.
///
/// # Examples
///
/// ```
/// use dram_memory_controller_behavior::{
///     BankStateMix, DramTiming, expected_device_component_ns,
/// };
///
/// let timing = DramTiming::new(14.0, 2.5, 14.0, 14.0)?;
/// let mix = BankStateMix::new(0.50, 0.20, 0.30)?;
/// let expected = expected_device_component_ns(timing, mix)?;
/// assert!((expected - 27.70).abs() < 1e-12);
/// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
/// ```
pub fn expected_device_component_ns(
    timing: DramTiming,
    mix: BankStateMix,
) -> Result<f64, ModelError> {
    let expected = mix.probability(BankState::Hit) * timing.device_component_ns(BankState::Hit)
        + mix.probability(BankState::Closed) * timing.device_component_ns(BankState::Closed)
        + mix.probability(BankState::Conflict) * timing.device_component_ns(BankState::Conflict);
    finite_result(expected, "expected device component")
}

/// Applies Little's law to a byte-throughput target.
///
/// The result is the average number of requests that must be in flight:
/// `(target bytes/second / useful bytes/request) * average seconds/request`.
/// Round up separately when sizing an integer slot count.
///
/// Little's law is an average-flow identity for a stable observation interval.
/// This calculation does not prove that the target is reachable, that requests
/// are independent, or that the controller has enough bank parallelism.
///
/// # Errors
///
/// Returns [`ModelError`] unless the target is finite and non-negative and the
/// latency and useful byte count are finite and strictly positive. It also
/// rejects a non-finite result.
///
/// # Examples
///
/// ```
/// use dram_memory_controller_behavior::required_inflight;
///
/// let average = required_inflight(20e9, 100e-9, 64.0)?;
/// assert_eq!(average, 31.25);
/// assert_eq!(average.ceil() as u64, 32);
/// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
/// ```
pub fn required_inflight(
    target_bytes_per_second: f64,
    average_latency_seconds: f64,
    useful_bytes_per_request: f64,
) -> Result<f64, ModelError> {
    validate_non_negative_finite(target_bytes_per_second, "target bytes per second")?;
    validate_positive_finite(average_latency_seconds, "average latency seconds")?;
    validate_positive_finite(useful_bytes_per_request, "useful bytes per request")?;

    let inflight = target_bytes_per_second / useful_bytes_per_request * average_latency_seconds;
    finite_result(inflight, "required in-flight request count")
}

/// Returns the payload-rate ceiling implied by an in-flight count and latency.
///
/// This is the inverse of [`required_inflight`]:
/// `in-flight requests * useful bytes/request / average seconds/request`.
/// It is one candidate ceiling, not a prediction of achieved bandwidth.
///
/// # Errors
///
/// Returns [`ModelError`] unless the in-flight count is finite and
/// non-negative and the latency and byte count are finite and strictly
/// positive. It also rejects a non-finite result.
///
/// # Examples
///
/// ```
/// use dram_memory_controller_behavior::inflight_payload_ceiling;
///
/// assert_eq!(inflight_payload_ceiling(32.0, 100e-9, 64.0)?, 20.48e9);
/// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
/// ```
pub fn inflight_payload_ceiling(
    inflight_requests: f64,
    average_latency_seconds: f64,
    useful_bytes_per_request: f64,
) -> Result<f64, ModelError> {
    validate_non_negative_finite(inflight_requests, "in-flight requests")?;
    validate_positive_finite(average_latency_seconds, "average latency seconds")?;
    validate_positive_finite(useful_bytes_per_request, "useful bytes per request")?;

    let ceiling = inflight_requests * useful_bytes_per_request / average_latency_seconds;
    finite_result(ceiling, "in-flight payload ceiling")
}

/// Calculates raw data-pin bandwidth in bytes per second.
///
/// Pass an effective transfer rate, not the underlying clock frequency. For
/// example, `4.8e9` transfers per second across 32 data pins yields `19.2e9`
/// bytes per second. The result excludes command, refresh, turnaround, error
/// correction, and workload-efficiency losses.
///
/// # Errors
///
/// Returns [`ModelError`] when the transfer rate is not finite and strictly
/// positive, the data-bus width is zero, or the product is not finite.
///
/// # Examples
///
/// ```
/// use dram_memory_controller_behavior::pin_bandwidth;
///
/// assert_eq!(pin_bandwidth(4.8e9, 32)?, 19.2e9);
/// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
/// ```
pub fn pin_bandwidth(
    transfers_per_second: f64,
    data_bus_width_bits: u32,
) -> Result<f64, ModelError> {
    validate_positive_finite(transfers_per_second, "transfers per second")?;
    if data_bus_width_bits == 0 {
        return Err(ModelError::NotPositive("data bus width bits"));
    }
    let bytes_per_transfer = f64::from(data_bus_width_bits) / 8.0;
    finite_result(
        transfers_per_second * bytes_per_transfer,
        "data-pin bandwidth",
    )
}

/// Four caller-supplied byte-rate candidates.
///
/// `pin_payload_bytes_per_second` is the caller's already-derived `B_pin * u`,
/// where `B_pin` is raw pin bandwidth and `u` is the useful-transfer fraction.
/// The caller must bound `u` for the workload; [`useful_throughput_cap`]
/// validates only the four final rates. The other fields represent the
/// in-flight, processor-core, and fabric ceilings. The type does not enforce
/// that the candidates describe the same endpoint, direction, time window, or
/// payload definition.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ThroughputCandidates {
    /// Data-pin bandwidth multiplied by a caller-justified useful fraction.
    pub pin_payload_bytes_per_second: f64,
    /// Payload rate implied by the allowed in-flight work and average latency.
    pub inflight_payload_bytes_per_second: f64,
    /// Payload-rate ceiling supplied for the processor core.
    pub core_bytes_per_second: f64,
    /// Payload-rate ceiling supplied for the connecting fabric.
    pub fabric_bytes_per_second: f64,
}

/// Label for the smallest supplied throughput candidate.
///
/// The label is an arithmetic result, not causal evidence that the named
/// component is a measured bottleneck.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThroughputLimit {
    /// The data-pin bandwidth after the caller's useful-transfer fraction.
    PinPayload,
    /// The in-flight work and average-latency candidate.
    InflightPayload,
    /// The processor-core candidate.
    Core,
    /// The connecting-fabric candidate.
    Fabric,
}

/// Result produced by [`useful_throughput_cap`].
///
/// The function returns the smallest validated input candidate. Because these
/// fields are public, direct struct construction does not enforce that
/// relationship.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct UsefulThroughputCap {
    /// Smallest supplied candidate, in bytes per second.
    pub bytes_per_second: f64,
    /// Component that supplied `bytes_per_second`.
    pub limiting_candidate: ThroughputLimit,
}

/// Selects the minimum of four finite, non-negative byte-rate candidates.
///
/// The calculation represents
/// `min(B_pin * u, N * S / L, B_core, B_fabric)`. The caller must derive each
/// term for the same endpoint, direction, time window, and payload definition.
/// The function does not verify that semantic precondition. A tie uses the
/// field order shown in the formula. The returned label is not a bottleneck
/// diagnosis, and the minimum is not an achieved-throughput model.
///
/// # Errors
///
/// Returns [`ModelError`] when any candidate is negative or non-finite.
///
/// # Examples
///
/// ```
/// use dram_memory_controller_behavior::{
///     ThroughputCandidates, ThroughputLimit, useful_throughput_cap,
/// };
///
/// let cap = useful_throughput_cap(ThroughputCandidates {
///     pin_payload_bytes_per_second: 19.2e9,
///     inflight_payload_bytes_per_second: 20.48e9,
///     core_bytes_per_second: 24e9,
///     fabric_bytes_per_second: 22e9,
/// })?;
/// assert_eq!(cap.bytes_per_second, 19.2e9);
/// assert_eq!(cap.limiting_candidate, ThroughputLimit::PinPayload);
/// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
/// ```
pub fn useful_throughput_cap(
    candidates: ThroughputCandidates,
) -> Result<UsefulThroughputCap, ModelError> {
    let ordered = [
        (
            ThroughputLimit::PinPayload,
            candidates.pin_payload_bytes_per_second,
            "pin payload bytes per second",
        ),
        (
            ThroughputLimit::InflightPayload,
            candidates.inflight_payload_bytes_per_second,
            "in-flight payload bytes per second",
        ),
        (
            ThroughputLimit::Core,
            candidates.core_bytes_per_second,
            "core bytes per second",
        ),
        (
            ThroughputLimit::Fabric,
            candidates.fabric_bytes_per_second,
            "fabric bytes per second",
        ),
    ];

    for (_, value, name) in ordered {
        validate_non_negative_finite(value, name)?;
    }

    let mut limiting_candidate = ordered[0].0;
    let mut bytes_per_second = ordered[0].1;
    for (candidate, value, _) in &ordered[1..] {
        if *value < bytes_per_second {
            limiting_candidate = *candidate;
            bytes_per_second = *value;
        }
    }

    Ok(UsefulThroughputCap {
        bytes_per_second,
        limiting_candidate,
    })
}

/// Returns the nominal fraction of a refresh interval occupied by refresh.
///
/// Both arguments use the same time unit. `tRFC` is refresh cycle time and
/// `tREFI` is the average refresh interval. The quotient `tRFC / tREFI` is a
/// crude no-overlap schedule fraction. It is not a measured bandwidth loss:
/// controllers can reschedule refresh, and device modes differ in whether
/// refresh blocks all banks or a subset, such as one bank per bank group.
///
/// # Errors
///
/// Returns [`ModelError`] unless `tRFC` is finite and non-negative, `tREFI` is
/// finite and strictly positive, and `tRFC` does not exceed `tREFI`.
///
/// # Examples
///
/// ```
/// use dram_memory_controller_behavior::refresh_duty_fraction;
///
/// let fraction = refresh_duty_fraction(295.0, 3_900.0)?;
/// assert!((fraction - 0.075_641_025_641_025_64).abs() < 1e-15);
/// # Ok::<(), dram_memory_controller_behavior::ModelError>(())
/// ```
pub fn refresh_duty_fraction(t_rfc: f64, t_refi: f64) -> Result<f64, ModelError> {
    validate_non_negative_finite(t_rfc, "tRFC")?;
    validate_positive_finite(t_refi, "tREFI")?;
    if t_rfc > t_refi {
        return Err(ModelError::OutOfRange("tRFC must not exceed tREFI"));
    }
    Ok(t_rfc / t_refi)
}

/// Invalid input or non-finite output from an accounting helper.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ModelError {
    /// A named input was not finite.
    NotFinite(&'static str),
    /// A named input was negative.
    Negative(&'static str),
    /// A named input was zero or negative.
    NotPositive(&'static str),
    /// A value violated a model-specific range condition.
    OutOfRange(&'static str),
    /// Bank-state probabilities did not sum to one within the accepted tolerance.
    ProbabilitySum,
    /// A named derived value could not be represented as a finite `f64`.
    DerivedValueNotFinite(&'static str),
}

impl Display for ModelError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFinite(name) => write!(formatter, "{name} must be finite"),
            Self::Negative(name) => write!(formatter, "{name} must be non-negative"),
            Self::NotPositive(name) => write!(formatter, "{name} must be positive"),
            Self::OutOfRange(message) => formatter.write_str(message),
            Self::ProbabilitySum => formatter.write_str("bank-state probabilities must sum to one"),
            Self::DerivedValueNotFinite(name) => {
                write!(formatter, "derived {name} is not finite")
            }
        }
    }
}

impl Error for ModelError {}

fn validate_probability(value: f64, name: &'static str) -> Result<(), ModelError> {
    if !value.is_finite() {
        return Err(ModelError::NotFinite(name));
    }
    if !(0.0..=1.0).contains(&value) {
        return Err(ModelError::OutOfRange(
            "each bank-state probability must be between zero and one",
        ));
    }
    Ok(())
}

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

    fn lesson_timing() -> DramTiming {
        DramTiming::new(14.0, 2.5, 14.0, 14.0).expect("lesson timings are valid")
    }

    #[test]
    fn bank_state_components_match_lesson_arithmetic() {
        let timing = lesson_timing();
        assert_close(timing.device_component_ns(BankState::Hit), 16.5);
        assert_close(timing.device_component_ns(BankState::Closed), 30.5);
        assert_close(timing.device_component_ns(BankState::Conflict), 44.5);
    }

    #[test]
    fn expected_component_matches_lesson_mix() {
        let mix = BankStateMix::new(0.50, 0.20, 0.30).expect("lesson mix is valid");
        let expected =
            expected_device_component_ns(lesson_timing(), mix).expect("finite weighted mean");
        assert_close(expected, 27.70);
    }

    #[test]
    fn mix_rejects_invalid_probabilities_and_sum() {
        assert_eq!(
            BankStateMix::new(-0.1, 0.5, 0.6),
            Err(ModelError::OutOfRange(
                "each bank-state probability must be between zero and one"
            ))
        );
        assert_eq!(
            BankStateMix::new(0.5, f64::NAN, 0.5),
            Err(ModelError::NotFinite("closed probability"))
        );
        assert_eq!(
            BankStateMix::new(0.5, 0.2, 0.2),
            Err(ModelError::ProbabilitySum)
        );
    }

    #[test]
    fn timing_rejects_negative_and_overflowing_components() {
        assert_eq!(
            DramTiming::new(14.0, -1.0, 14.0, 14.0),
            Err(ModelError::Negative("t_burst_ns"))
        );
        assert_eq!(
            DramTiming::new(f64::MAX, f64::MAX, 0.0, 0.0),
            Err(ModelError::DerivedValueNotFinite(
                "row-conflict device component"
            ))
        );
    }

    #[test]
    fn little_law_helpers_are_inverse_for_same_inputs() {
        let required = required_inflight(20e9, 100e-9, 64.0).expect("valid inputs");
        assert_close(required, 31.25);
        assert_eq!(required.ceil() as u64, 32);

        let reconstructed = inflight_payload_ceiling(required, 100e-9, 64.0).expect("valid inputs");
        assert_close(reconstructed, 20e9);
    }

    #[test]
    fn throughput_helpers_match_lesson_arithmetic() {
        let pin = pin_bandwidth(4.8e9, 32).expect("valid pin inputs");
        assert_close(pin, 19.2e9);
        let inflight = inflight_payload_ceiling(32.0, 100e-9, 64.0).expect("valid inflight inputs");

        let cap = useful_throughput_cap(ThroughputCandidates {
            pin_payload_bytes_per_second: pin,
            inflight_payload_bytes_per_second: inflight,
            core_bytes_per_second: 24e9,
            fabric_bytes_per_second: 22e9,
        })
        .expect("finite candidates");
        assert_close(cap.bytes_per_second, 19.2e9);
        assert_eq!(cap.limiting_candidate, ThroughputLimit::PinPayload);
    }

    #[test]
    fn throughput_cap_validates_candidates_and_has_stable_ties() {
        let tied = useful_throughput_cap(ThroughputCandidates {
            pin_payload_bytes_per_second: 10.0,
            inflight_payload_bytes_per_second: 10.0,
            core_bytes_per_second: 11.0,
            fabric_bytes_per_second: 12.0,
        })
        .expect("finite candidates");
        assert_eq!(tied.limiting_candidate, ThroughputLimit::PinPayload);

        assert_eq!(
            useful_throughput_cap(ThroughputCandidates {
                pin_payload_bytes_per_second: 10.0,
                inflight_payload_bytes_per_second: f64::INFINITY,
                core_bytes_per_second: 11.0,
                fabric_bytes_per_second: 12.0,
            }),
            Err(ModelError::NotFinite("in-flight payload bytes per second"))
        );
    }

    #[test]
    fn refresh_fraction_matches_lesson_and_checks_domain() {
        let fraction = refresh_duty_fraction(295.0, 3_900.0).expect("valid schedule values");
        assert_close(fraction, 295.0 / 3_900.0);
        assert_eq!(
            refresh_duty_fraction(4_000.0, 3_900.0),
            Err(ModelError::OutOfRange("tRFC must not exceed tREFI"))
        );
        assert_eq!(
            refresh_duty_fraction(295.0, 0.0),
            Err(ModelError::NotPositive("tREFI"))
        );
    }

    #[test]
    fn scalar_helpers_reject_invalid_inputs() {
        assert_eq!(
            required_inflight(20e9, 100e-9, 0.0),
            Err(ModelError::NotPositive("useful bytes per request"))
        );
        assert_eq!(
            required_inflight(20e9, -1.0, 64.0),
            Err(ModelError::NotPositive("average latency seconds"))
        );
        assert_eq!(
            inflight_payload_ceiling(-1.0, 100e-9, 64.0),
            Err(ModelError::Negative("in-flight requests"))
        );
        assert_eq!(
            pin_bandwidth(f64::NAN, 32),
            Err(ModelError::NotFinite("transfers per second"))
        );
        assert_eq!(
            pin_bandwidth(4.8e9, 0),
            Err(ModelError::NotPositive("data bus width bits"))
        );
    }
}
