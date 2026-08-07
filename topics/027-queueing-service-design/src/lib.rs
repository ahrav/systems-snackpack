//! Workload and assignment invariants for a bounded single-worker queue.
//!
//! The runnable `queue-probe` binary schedules requests at deterministic offsets
//! from one process origin and offers them without waiting for queue capacity.
//! This library keeps the offered-work equality and restricted process schedule
//! independently testable.
//!
//! The model is intentionally narrow. It does not model retries, request
//! expiry or service deadlines, multiple workers, adaptive admission, or a
//! production arrival process.
//!
//! # Example
//!
//! ```
//! use queueing_service_design::{Mode, REQUESTS, offered_work_x4};
//!
//! let fixed = offered_work_x4(Mode::Fixed, REQUESTS, 27).unwrap();
//! let variable = offered_work_x4(Mode::Variable, REQUESTS, 27).unwrap();
//! assert_eq!(fixed, variable);
//! ```

use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::str::FromStr;

/// Requests offered by every retained process invocation.
pub const REQUESTS: usize = 8_000;
/// Waiting slots in the bounded channel, excluding the job in service.
pub const QUEUE_CAPACITY: usize = 4;
/// Per-host calibration target for one fixed-service job.
pub const TARGET_SERVICE_NS: u64 = 200_000;
/// Nominal offered load encoded as a fraction.
pub const LOAD_NUMERATOR: u64 = 9;
/// Denominator for [`LOAD_NUMERATOR`].
pub const LOAD_DENOMINATOR: u64 = 10;
/// Prefix used to derive the per-block main workload seeds.
pub const SCHEDULE_SEED: u64 = 27_082_026;
/// Eight balanced four-period treatment templates.
pub const MAIN_TEMPLATES: [&str; 8] = [
    "BAAB", "ABBA", "BAAB", "ABBA", "ABBA", "BAAB", "ABBA", "BAAB",
];
/// Four balanced A/A templates whose labels both map to fixed service.
pub const AA_TEMPLATES: [&str; 4] = ["ABBA", "BAAB", "BAAB", "ABBA"];

/// Offered service-time shape.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Mode {
    /// Every job receives one unit of work.
    Fixed,
    /// Each ten-job group contains nine quarter jobs and one 7.75-unit job.
    Variable,
}

impl Mode {
    /// Returns the spelling accepted by [`Mode::from_str`].
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Fixed => "fixed",
            Self::Variable => "variable",
        }
    }
}

impl FromStr for Mode {
    type Err = ParseModeError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "fixed" => Ok(Self::Fixed),
            "variable" => Ok(Self::Variable),
            _ => Err(ParseModeError),
        }
    }
}

/// Error returned for an unknown [`Mode`] spelling.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ParseModeError;

impl Display for ParseModeError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str("mode must be fixed or variable")
    }
}

impl Error for ParseModeError {}

/// Experiment phase.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Phase {
    /// Fixed-versus-variable treatment comparison.
    Main,
    /// Identical fixed-versus-fixed harness control.
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

/// Schedule label kept separate from the treatment mapping.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Label {
    /// Fixed-service treatment in both phases.
    A,
    /// Variable service in [`Phase::Main`] and fixed service in [`Phase::Aa`].
    B,
}

impl Label {
    /// Returns the one-character receipt spelling.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::A => "A",
            Self::B => "B",
        }
    }
}

/// One fresh-process treatment application returned by [`assignments`].
///
/// The constructor function, rather than this publicly constructible type,
/// enforces the fixed schedule's field relationships.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Assignment {
    /// Main comparison or A/A control in the generated schedule.
    pub phase: Phase,
    /// One-based complete-block number within the generated phase.
    pub block: usize,
    /// One-based period within the generated block.
    pub period: usize,
    /// Four-character restricted-randomization template selected by the generator.
    pub template: &'static str,
    /// Label routed through the generated output and analysis paths.
    pub label: Label,
    /// Service shape assigned by the generator for this process.
    pub mode: Mode,
    /// Deterministic workload seed shared within a generated block.
    pub seed: u64,
}

/// Returns all 32 main assignments followed by all 16 A/A assignments.
#[must_use]
pub fn assignments() -> Vec<Assignment> {
    let mut result = Vec::with_capacity(MAIN_TEMPLATES.len() * 4 + AA_TEMPLATES.len() * 4);
    append_phase(&mut result, Phase::Main, &MAIN_TEMPLATES, SCHEDULE_SEED);
    append_phase(&mut result, Phase::Aa, &AA_TEMPLATES, SCHEDULE_SEED + 1);
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
            let mode = match (phase, label) {
                (Phase::Main, Label::B) => Mode::Variable,
                _ => Mode::Fixed,
            };
            result.push(Assignment {
                phase,
                block,
                period: period_index + 1,
                template,
                label,
                mode,
                seed: seed_prefix * 100 + block as u64,
            });
        }
    }
}

/// Validated configuration accepted by one queue-probe process.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ExperimentConfig {
    requests: usize,
    queue_capacity: usize,
    base_iterations: u64,
    interval_ns: u64,
}

impl ExperimentConfig {
    /// Validates one process configuration.
    ///
    /// # Errors
    ///
    /// - [`ConfigError::Requests`] if `requests` is zero or not divisible by ten.
    /// - [`ConfigError::QueueCapacity`] if `queue_capacity` is zero.
    /// - [`ConfigError::BaseIterations`] if `base_iterations` is zero or not
    ///   divisible by four.
    /// - [`ConfigError::Interval`] if `interval_ns` is zero.
    pub fn new(
        requests: usize,
        queue_capacity: usize,
        base_iterations: u64,
        interval_ns: u64,
    ) -> Result<Self, ConfigError> {
        if requests == 0 || !requests.is_multiple_of(10) {
            return Err(ConfigError::Requests);
        }
        if queue_capacity == 0 {
            return Err(ConfigError::QueueCapacity);
        }
        if base_iterations == 0 || !base_iterations.is_multiple_of(4) {
            return Err(ConfigError::BaseIterations);
        }
        if interval_ns == 0 {
            return Err(ConfigError::Interval);
        }
        Ok(Self {
            requests,
            queue_capacity,
            base_iterations,
            interval_ns,
        })
    }

    /// Returns the offered request count.
    #[must_use]
    pub const fn requests(self) -> usize {
        self.requests
    }

    /// Returns waiting slots, excluding the job in service.
    #[must_use]
    pub const fn queue_capacity(self) -> usize {
        self.queue_capacity
    }

    /// Returns iterations corresponding to one fixed-service job.
    #[must_use]
    pub const fn base_iterations(self) -> u64 {
        self.base_iterations
    }

    /// Returns the deterministic inter-arrival interval.
    #[must_use]
    pub const fn interval_ns(self) -> u64 {
        self.interval_ns
    }
}

/// Invalid [`ExperimentConfig`] field.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ConfigError {
    /// Requests are zero or do not form complete ten-job groups.
    Requests,
    /// The waiting-slot bound is zero.
    QueueCapacity,
    /// Fixed-service iterations are zero or not divisible by four.
    BaseIterations,
    /// The arrival interval is zero.
    Interval,
}

impl Display for ConfigError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::Requests => "requests must be nonzero and divisible by ten",
            Self::QueueCapacity => "queue capacity must be nonzero",
            Self::BaseIterations => "base iterations must be nonzero and divisible by four",
            Self::Interval => "arrival interval must be nonzero",
        };
        formatter.write_str(message)
    }
}

impl Error for ConfigError {}

/// Returns work in quarter units for one offered request.
///
/// Fixed jobs return `4`. Each complete variable group returns nine `1` values
/// and one `31`; `mix64(seed ^ (request_id / 10)) % 10` selects the `31`.
#[must_use]
pub fn service_factor_x4(mode: Mode, request_id: usize, seed: u64) -> u64 {
    if mode == Mode::Fixed {
        return 4;
    }
    let group = request_id / 10;
    let large_position = (mix64(seed ^ group as u64) % 10) as usize;
    if request_id % 10 == large_position {
        31
    } else {
        1
    }
}

/// Returns total offered work in quarter units.
///
/// Returns `None` if summation overflows `u64`.
#[must_use]
pub fn offered_work_x4(mode: Mode, requests: usize, seed: u64) -> Option<u64> {
    (0..requests).try_fold(0_u64, |total, request_id| {
        total.checked_add(service_factor_x4(mode, request_id, seed))
    })
}

/// Converts a quarter-unit factor into calibrated loop iterations.
///
/// Returns `None` if `base_iterations` is not divisible by four or the
/// multiplication overflows.
#[must_use]
pub fn work_iterations(base_iterations: u64, factor_x4: u64) -> Option<u64> {
    if !base_iterations.is_multiple_of(4) {
        return None;
    }
    (base_iterations / 4).checked_mul(factor_x4)
}

/// Returns the theoretical offered service-time squared coefficient of variation.
///
/// [`Mode::Variable`] yields `5.0625` from nine `0.25`-unit jobs and one
/// `7.75`-unit job with mean service time of one unit.
#[must_use]
pub const fn offered_service_cs2(mode: Mode) -> f64 {
    match mode {
        Mode::Fixed => 0.0,
        Mode::Variable => 5.0625,
    }
}

/// Deterministically mixes a workload seed.
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

    #[test]
    fn fixed_and_variable_offer_identical_work_per_complete_group() {
        for seed in [0, 1, SCHEDULE_SEED, u64::MAX] {
            for groups in [1, 2, 800] {
                let requests = groups * 10;
                assert_eq!(
                    offered_work_x4(Mode::Fixed, requests, seed),
                    offered_work_x4(Mode::Variable, requests, seed)
                );
                assert_eq!(
                    offered_work_x4(Mode::Variable, requests, seed),
                    Some((requests * 4) as u64)
                );
            }
        }
    }

    #[test]
    fn variable_group_has_nine_small_jobs_and_one_large_job() {
        for group in 0..32 {
            let factors: Vec<_> = (group * 10..group * 10 + 10)
                .map(|id| service_factor_x4(Mode::Variable, id, 27))
                .collect();
            assert_eq!(factors.iter().filter(|&&factor| factor == 1).count(), 9);
            assert_eq!(factors.iter().filter(|&&factor| factor == 31).count(), 1);
            assert_eq!(factors.iter().sum::<u64>(), 40);
        }
    }

    #[test]
    fn variable_second_moment_matches_declared_cs2() {
        let factors = [1.0_f64 / 4.0; 9]
            .into_iter()
            .chain([31.0 / 4.0])
            .collect::<Vec<_>>();
        let mean = factors.iter().sum::<f64>() / factors.len() as f64;
        let variance = factors
            .iter()
            .map(|value| (value - mean).powi(2))
            .sum::<f64>()
            / factors.len() as f64;
        assert_eq!(mean, 1.0);
        assert_eq!(variance / mean.powi(2), offered_service_cs2(Mode::Variable));
    }

    #[test]
    fn schedule_has_complete_balanced_blocks_and_identical_aa_treatments() {
        let schedule = assignments();
        assert_eq!(schedule.len(), 48);
        assert_eq!(
            schedule.iter().filter(|a| a.phase == Phase::Main).count(),
            32
        );
        assert_eq!(schedule.iter().filter(|a| a.phase == Phase::Aa).count(), 16);

        for phase in [Phase::Main, Phase::Aa] {
            let block_count = if phase == Phase::Main { 8 } else { 4 };
            for block in 1..=block_count {
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
                            .all(|assignment| assignment.mode == Mode::Fixed)
                    );
                }
            }
        }
    }

    #[test]
    fn configuration_rejects_unmatched_or_zero_inputs() {
        assert_eq!(
            ExperimentConfig::new(9, 4, 100, 1),
            Err(ConfigError::Requests)
        );
        assert_eq!(
            ExperimentConfig::new(10, 0, 100, 1),
            Err(ConfigError::QueueCapacity)
        );
        assert_eq!(
            ExperimentConfig::new(10, 4, 101, 1),
            Err(ConfigError::BaseIterations)
        );
        assert_eq!(
            ExperimentConfig::new(10, 4, 100, 0),
            Err(ConfigError::Interval)
        );
    }

    #[test]
    fn quarter_iteration_conversion_is_exact_and_checked() {
        assert_eq!(work_iterations(100, 1), Some(25));
        assert_eq!(work_iterations(100, 31), Some(775));
        assert_eq!(work_iterations(101, 4), None);
        assert_eq!(work_iterations(u64::MAX - 3, 31), None);
    }
}
