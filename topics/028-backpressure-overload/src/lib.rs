//! Closed-form accounting and schedule invariants for a synthetic one-key overload wave.
//!
//! The runnable `overload-probe` binary compares independent per-caller retries
//! with one key-scoped flight, one aggregate retry budget, a bounded origin
//! concurrency permit, and a separate admitted-waiter cap. This library keeps
//! the deterministic count claims and restricted process schedule independently
//! testable.
//!
//! # Model boundary
//!
//! The model supplies exactly one synthetic key and the physical outcome sequence
//! transient, transient, then success. It performs CPU work in place of an origin
//! request; it does not implement or measure DNS, caching, networking, backoff,
//! cancellation, recovery timing, multiple keys, or a global active-key bound.

#![forbid(unsafe_code)]

use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::str::FromStr;

/// Callers in the primary same-key miss wave.
pub const DEFAULT_CALLERS: usize = 64;
/// Maximum simultaneously admitted callers, including the flight leader.
pub const DEFAULT_WAITER_CAP: usize = 64;
/// Maximum concurrently executing physical origin attempts.
pub const DEFAULT_ORIGIN_CAPACITY: usize = 4;
/// Maximum physical attempts allowed for one flight.
pub const DEFAULT_MAX_ATTEMPTS: usize = 3;
/// Retry tokens available after a flight's first physical attempt.
pub const DEFAULT_RETRY_TOKENS: usize = 2;
/// Per-host calibration target of 200 µs for one synthetic origin attempt.
///
/// The harness reports the achieved mean without imposing an acceptance tolerance.
pub const TARGET_ATTEMPT_NS: u64 = 200_000;
/// First physical attempt that succeeds in the synthetic outcome schedule.
pub const SUCCESS_ATTEMPT: usize = 3;
/// Prefix used to derive main-phase block seeds.
pub const MAIN_SCHEDULE_SEED: u64 = 28_082_026;
/// Prefix used to derive A/A block seeds.
pub const AA_SCHEDULE_SEED: u64 = 28_082_027;
/// Eight predeclared balanced main-phase treatment templates.
pub const MAIN_TEMPLATES: [&str; 8] = [
    "ABBA", "ABBA", "BAAB", "BAAB", "BAAB", "ABBA", "ABBA", "BAAB",
];
/// Four predeclared balanced A/A templates.
pub const AA_TEMPLATES: [&str; 4] = ["ABBA", "BAAB", "BAAB", "ABBA"];

/// Retry and coalescing treatment used by one fresh process.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Treatment {
    /// Every admitted caller owns a flight and its own retry tokens.
    Naive,
    /// All admitted callers join one key-scoped flight and aggregate retry budget.
    Controlled,
}

impl Treatment {
    /// Returns the stable receipt spelling.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Naive => "naive",
            Self::Controlled => "controlled",
        }
    }
}

impl FromStr for Treatment {
    type Err = ParseTreatmentError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "naive" => Ok(Self::Naive),
            "controlled" => Ok(Self::Controlled),
            _ => Err(ParseTreatmentError),
        }
    }
}

/// Error returned for an unknown [`Treatment`] spelling.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ParseTreatmentError;

impl Display for ParseTreatmentError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("treatment must be naive or controlled")
    }
}

impl Error for ParseTreatmentError {}

/// Experiment phase.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Phase {
    /// Naive-versus-controlled comparison.
    Main,
    /// Identical controlled-versus-controlled harness diagnostic.
    Aa,
}

impl Phase {
    /// Returns the stable receipt spelling.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Main => "main",
            Self::Aa => "aa",
        }
    }
}

impl FromStr for Phase {
    type Err = ParsePhaseError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "main" => Ok(Self::Main),
            "aa" => Ok(Self::Aa),
            _ => Err(ParsePhaseError),
        }
    }
}

/// Error returned for an unknown [`Phase`] spelling.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ParsePhaseError;

impl Display for ParsePhaseError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("phase must be main or aa")
    }
}

impl Error for ParsePhaseError {}

/// Schedule label kept separate from treatment assignment.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Label {
    /// Naive in the main phase and controlled in the A/A phase.
    A,
    /// Controlled in both phases.
    B,
}

impl Label {
    /// Returns the stable receipt spelling.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::A => "A",
            Self::B => "B",
        }
    }
}

impl FromStr for Label {
    type Err = ParseLabelError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "A" => Ok(Self::A),
            "B" => Ok(Self::B),
            _ => Err(ParseLabelError),
        }
    }
}

/// Error returned for an unknown [`Label`] spelling.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ParseLabelError;

impl Display for ParseLabelError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("label must be A or B")
    }
}

impl Error for ParseLabelError {}

/// Returns the treatment required by one phase and label.
#[must_use]
pub const fn treatment_for(phase: Phase, label: Label) -> Treatment {
    match (phase, label) {
        (Phase::Main, Label::A) => Treatment::Naive,
        _ => Treatment::Controlled,
    }
}

/// One fresh-process assignment in the fixed protocol.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Assignment {
    /// Main comparison or A/A diagnostic.
    pub phase: Phase,
    /// One-based block number within the phase.
    pub block: usize,
    /// One-based period within the block.
    pub period: usize,
    /// Four-letter restricted-randomization template.
    pub template: &'static str,
    /// Label routed through receipts and analysis.
    pub label: Label,
    /// Treatment selected by [`treatment_for`].
    pub treatment: Treatment,
    /// Deterministic workload seed shared within the block.
    pub seed: u64,
}

/// Returns 32 main assignments followed by 16 A/A assignments.
#[must_use]
pub fn assignments() -> Vec<Assignment> {
    let mut result = Vec::with_capacity(MAIN_TEMPLATES.len() * 4 + AA_TEMPLATES.len() * 4);
    append_phase(
        &mut result,
        Phase::Main,
        &MAIN_TEMPLATES,
        MAIN_SCHEDULE_SEED,
    );
    append_phase(&mut result, Phase::Aa, &AA_TEMPLATES, AA_SCHEDULE_SEED);
    result
}

fn append_phase(
    result: &mut Vec<Assignment>,
    phase: Phase,
    templates: &[&'static str],
    seed_prefix: u64,
) {
    for (block_index, &template) in templates.iter().enumerate() {
        let block = block_index + 1;
        for (period_index, byte) in template.bytes().enumerate() {
            let label = match byte {
                b'A' => Label::A,
                b'B' => Label::B,
                _ => unreachable!("templates are compile-time A/B literals"),
            };
            result.push(Assignment {
                phase,
                block,
                period: period_index + 1,
                template,
                label,
                treatment: treatment_for(phase, label),
                seed: seed_prefix * 100 + block as u64,
            });
        }
    }
}

/// Validated configuration for one synthetic miss wave.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExperimentConfig {
    callers: usize,
    waiter_cap: usize,
    origin_capacity: usize,
    max_attempts: usize,
    retry_tokens: usize,
    work_iters: u64,
}

impl ExperimentConfig {
    /// Validates one miss-wave configuration.
    ///
    /// # Errors
    ///
    /// Returns a field-specific [`ConfigError`] when callers, either capacity,
    /// maximum attempts, or calibrated work iterations are zero. Retry tokens
    /// may be zero and are independently bounded by `max_attempts` at runtime.
    pub fn new(
        callers: usize,
        waiter_cap: usize,
        origin_capacity: usize,
        max_attempts: usize,
        retry_tokens: usize,
        work_iters: u64,
    ) -> Result<Self, ConfigError> {
        if callers == 0 {
            return Err(ConfigError::Callers);
        }
        if waiter_cap == 0 {
            return Err(ConfigError::WaiterCap);
        }
        if origin_capacity == 0 {
            return Err(ConfigError::OriginCapacity);
        }
        if max_attempts == 0 {
            return Err(ConfigError::MaxAttempts);
        }
        if work_iters == 0 {
            return Err(ConfigError::WorkIterations);
        }
        Ok(Self {
            callers,
            waiter_cap,
            origin_capacity,
            max_attempts,
            retry_tokens,
            work_iters,
        })
    }

    /// Returns logical caller count.
    #[must_use]
    pub const fn callers(self) -> usize {
        self.callers
    }

    /// Returns the admitted-caller cap, including a controlled leader.
    #[must_use]
    pub const fn waiter_cap(self) -> usize {
        self.waiter_cap
    }

    /// Returns the physical origin-work concurrency cap.
    #[must_use]
    pub const fn origin_capacity(self) -> usize {
        self.origin_capacity
    }

    /// Returns the per-flight maximum physical-attempt count.
    #[must_use]
    pub const fn max_attempts(self) -> usize {
        self.max_attempts
    }

    /// Returns retry tokens available after the first physical attempt.
    #[must_use]
    pub const fn retry_tokens(self) -> usize {
        self.retry_tokens
    }

    /// Returns calibrated loop iterations per physical attempt.
    #[must_use]
    pub const fn work_iters(self) -> u64 {
        self.work_iters
    }
}

/// Invalid [`ExperimentConfig`] field.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ConfigError {
    /// Caller count is zero.
    Callers,
    /// Waiter cap is zero.
    WaiterCap,
    /// Origin permit capacity is zero.
    OriginCapacity,
    /// Maximum attempts is zero.
    MaxAttempts,
    /// Calibrated work iterations are zero.
    WorkIterations,
}

impl Display for ConfigError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Callers => "callers must be nonzero",
            Self::WaiterCap => "waiter cap must be nonzero",
            Self::OriginCapacity => "origin capacity must be nonzero",
            Self::MaxAttempts => "maximum attempts must be nonzero",
            Self::WorkIterations => "work iterations must be nonzero",
        })
    }
}

impl Error for ConfigError {}

/// Exact counts implied by the synthetic outcome prefix and treatment.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ClosedFormCounts {
    /// Logical callers admitted to a flight.
    pub admitted: usize,
    /// Logical callers shed at admission.
    pub shed: usize,
    /// Callers that receive success.
    pub completed: usize,
    /// Callers that receive the shared or independent exhausted result.
    pub retry_exhausted: usize,
    /// Controlled callers assigned the leader role; naive callers remain independent.
    pub leaders: usize,
    /// Controlled callers waiting on the leader's terminal result.
    pub followers: usize,
    /// Independent physical-attempt sequences.
    pub flights: usize,
    /// All physical origin attempts.
    pub origin_attempts: usize,
    /// Attempts after the first attempt in each flight.
    pub retry_attempts: usize,
    /// Physical attempts that return the synthetic transient outcome.
    pub transient_attempts: usize,
    /// Physical attempts that return success.
    pub successful_attempts: usize,
}

/// Returns the exact synthetic count model for one treatment.
///
/// Every created flight issues exactly
/// `min(max_attempts, 1 + retry_tokens, SUCCESS_ATTEMPT)` attempts under the
/// fixed transient, transient, success schedule. Naive mode creates one flight
/// per admitted caller. Controlled mode creates one flight whose aggregate budget
/// and terminal result are shared by every admitted caller. Checked count
/// arithmetic returns `None` on overflow.
#[must_use]
pub fn closed_form_counts(
    treatment: Treatment,
    config: ExperimentConfig,
) -> Option<ClosedFormCounts> {
    let admitted = config.callers().min(config.waiter_cap());
    let shed = config.callers().checked_sub(admitted)?;
    let flights = match treatment {
        Treatment::Naive => admitted,
        Treatment::Controlled => usize::from(admitted != 0),
    };
    let leaders = match treatment {
        Treatment::Naive => 0,
        Treatment::Controlled => flights,
    };
    let followers = match treatment {
        Treatment::Naive => 0,
        Treatment::Controlled => admitted.checked_sub(leaders)?,
    };
    let attempts_per_flight = config
        .max_attempts()
        .min(config.retry_tokens().saturating_add(1))
        .min(SUCCESS_ATTEMPT);
    let succeeds = attempts_per_flight == SUCCESS_ATTEMPT;
    let completed = if succeeds { admitted } else { 0 };
    let retry_exhausted = if succeeds { 0 } else { admitted };
    let origin_attempts = flights.checked_mul(attempts_per_flight)?;
    let retry_attempts = origin_attempts.checked_sub(flights)?;
    let transient_attempts = flights.checked_mul(attempts_per_flight.min(2))?;
    let successful_attempts = if succeeds { flights } else { 0 };
    Some(ClosedFormCounts {
        admitted,
        shed,
        completed,
        retry_exhausted,
        leaders,
        followers,
        flights,
        origin_attempts,
        retry_attempts,
        transient_attempts,
        successful_attempts,
    })
}

/// Deterministically mixes a seed for synthetic work and receipt identities.
#[must_use]
pub fn mix64(mut value: u64) -> u64 {
    value ^= value >> 30;
    value = value.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value ^= value >> 27;
    value = value.wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config(callers: usize, waiter_cap: usize, retry_tokens: usize) -> ExperimentConfig {
        ExperimentConfig::new(callers, waiter_cap, 4, 3, retry_tokens, 1)
            .expect("valid test configuration")
    }

    #[test]
    fn primary_naive_wave_has_three_attempts_per_caller() {
        let counts =
            closed_form_counts(Treatment::Naive, config(64, 64, 2)).expect("bounded arithmetic");
        assert_eq!(counts.completed, 64);
        assert_eq!(counts.shed, 0);
        assert_eq!(counts.leaders, 0);
        assert_eq!(counts.followers, 0);
        assert_eq!(counts.flights, 64);
        assert_eq!(counts.origin_attempts, 192);
        assert_eq!(counts.retry_attempts, 128);
        assert_eq!(counts.transient_attempts, 128);
        assert_eq!(counts.successful_attempts, 64);
    }

    #[test]
    fn controlled_wave_shares_one_flight_and_budget() {
        let counts = closed_form_counts(Treatment::Controlled, config(64, 64, 2))
            .expect("bounded arithmetic");
        assert_eq!(counts.completed, 64);
        assert_eq!(counts.shed, 0);
        assert_eq!(counts.leaders, 1);
        assert_eq!(counts.followers, 63);
        assert_eq!(counts.flights, 1);
        assert_eq!(counts.origin_attempts, 3);
        assert_eq!(counts.retry_attempts, 2);
    }

    #[test]
    fn waiter_cap_sheds_without_growing_the_flight() {
        let counts = closed_form_counts(Treatment::Controlled, config(128, 64, 2))
            .expect("bounded arithmetic");
        assert_eq!(counts.completed, 64);
        assert_eq!(counts.shed, 64);
        assert_eq!(counts.leaders, 1);
        assert_eq!(counts.followers, 63);
        assert_eq!(counts.origin_attempts, 3);
    }

    #[test]
    fn one_retry_token_exhausts_and_propagates() {
        let counts =
            closed_form_counts(Treatment::Controlled, config(8, 4, 1)).expect("bounded arithmetic");
        assert_eq!(counts.completed, 0);
        assert_eq!(counts.retry_exhausted, 4);
        assert_eq!(counts.shed, 4);
        assert_eq!(counts.origin_attempts, 2);
        assert_eq!(counts.transient_attempts, 2);
        assert_eq!(counts.successful_attempts, 0);
    }

    #[test]
    fn schedule_is_balanced_and_aa_is_identical_controlled() {
        let schedule = assignments();
        assert_eq!(schedule.len(), 48);
        for phase in [Phase::Main, Phase::Aa] {
            let blocks = if phase == Phase::Main { 8 } else { 4 };
            for block in 1..=blocks {
                let entries: Vec<_> = schedule
                    .iter()
                    .filter(|assignment| assignment.phase == phase && assignment.block == block)
                    .collect();
                assert_eq!(entries.len(), 4);
                assert_eq!(entries.iter().filter(|a| a.label == Label::A).count(), 2);
                assert_eq!(entries.iter().filter(|a| a.label == Label::B).count(), 2);
                assert_eq!(
                    entries.iter().map(|a| a.period).collect::<Vec<_>>(),
                    [1, 2, 3, 4]
                );
                if phase == Phase::Aa {
                    assert!(
                        entries
                            .iter()
                            .all(|assignment| assignment.treatment == Treatment::Controlled)
                    );
                }
            }
        }
    }

    #[test]
    fn configuration_rejects_zero_resource_fields() {
        assert_eq!(
            ExperimentConfig::new(0, 1, 1, 1, 0, 1),
            Err(ConfigError::Callers)
        );
        assert_eq!(
            ExperimentConfig::new(1, 0, 1, 1, 0, 1),
            Err(ConfigError::WaiterCap)
        );
        assert_eq!(
            ExperimentConfig::new(1, 1, 0, 1, 0, 1),
            Err(ConfigError::OriginCapacity)
        );
        assert_eq!(
            ExperimentConfig::new(1, 1, 1, 0, 0, 1),
            Err(ConfigError::MaxAttempts)
        );
        assert_eq!(
            ExperimentConfig::new(1, 1, 1, 1, 0, 0),
            Err(ConfigError::WorkIterations)
        );
    }
}
