//! Provides a deterministic phase workload for Linux PMU experiments.
//!
//! The workload alternates two equal-iteration phases. [`branch_phase`] adds an
//! data-dependent conditional branch to every loop iteration. [`arithmetic_phase`]
//! uses a branch-free dependency chain apart from loop control. Inspect the
//! optimized machine code before using those labels as measurement facts.
//!
//! # Example
//!
//! ```
//! use systems_snackpack_topic_003::{PhaseConfig, run_alternating};
//!
//! let result = run_alternating(PhaseConfig::new(4, 1_000, 7));
//! assert_eq!(result.completed_iterations, 8_000);
//! assert_ne!(result.checksum, 0);
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

/// Configuration for an alternating two-phase workload.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhaseConfig {
    /// Number of branch/arithmetic phase pairs.
    pub rounds: u32,
    /// Loop iterations in each phase.
    pub iterations_per_phase: u64,
    /// Initial state for the deterministic recurrence.
    pub seed: u64,
}

impl PhaseConfig {
    /// Creates a workload configuration.
    #[must_use]
    pub const fn new(rounds: u32, iterations_per_phase: u64, seed: u64) -> Self {
        Self {
            rounds,
            iterations_per_phase,
            seed,
        }
    }
}

/// Result of one alternating workload run.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhaseResult {
    /// Final state, used to keep every phase observable.
    pub checksum: u64,
    /// Number of inner-loop iterations completed across both phase types.
    pub completed_iterations: u128,
}

/// Runs equal-iteration branch-heavy and arithmetic phases in alternation.
///
/// The function returns a checksum instead of claiming that the two phases do
/// equal CPU work. Their instruction mix and latency differ by design.
#[inline(never)]
#[must_use]
pub fn run_alternating(config: PhaseConfig) -> PhaseResult {
    let mut state = config.seed;
    for _ in 0..config.rounds {
        state = branch_phase(config.iterations_per_phase, state);
        state = arithmetic_phase(config.iterations_per_phase, state);
    }

    PhaseResult {
        checksum: state,
        completed_iterations: u128::from(config.rounds)
            * u128::from(config.iterations_per_phase)
            * 2,
    }
}

/// Runs a deterministic loop with one data-dependent branch per iteration.
///
/// The two branch targets are separate non-inlined functions. This structure
/// discourages if-conversion, but only generated assembly can establish the
/// control flow for a specific compiler and target.
#[inline(never)]
#[must_use]
pub fn branch_phase(iterations: u64, mut state: u64) -> u64 {
    for _ in 0..iterations {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        state = if state & 1 == 0 {
            branch_even(state)
        } else {
            branch_odd(state)
        };
    }
    state
}

/// Runs a deterministic wrapping-arithmetic dependency chain.
///
/// The source contains no data-dependent control flow. The optimized loop still
/// has loop-control instructions unless the compiler fully unrolls it.
#[inline(never)]
#[must_use]
pub fn arithmetic_phase(iterations: u64, mut state: u64) -> u64 {
    for _ in 0..iterations {
        state = state
            .wrapping_mul(0xd134_2543_de82_ef95)
            .wrapping_add(0x9e37_79b9_7f4a_7c15);
        state ^= state.rotate_left(29);
    }
    state
}

#[inline(never)]
fn branch_even(state: u64) -> u64 {
    state.rotate_left(11).wrapping_add(0xa076_1d64_78bd_642f)
}

#[inline(never)]
fn branch_odd(state: u64) -> u64 {
    state.rotate_right(7).wrapping_mul(0xe703_7ed1_a0b4_28db)
}

#[cfg(test)]
mod tests {
    use super::{PhaseConfig, arithmetic_phase, branch_phase, run_alternating};

    #[test]
    fn alternating_run_is_deterministic() {
        let config = PhaseConfig::new(5, 1_000, 0x1234_5678_9abc_def0);
        assert_eq!(run_alternating(config), run_alternating(config));
    }

    #[test]
    fn completed_iterations_count_both_phases() {
        let result = run_alternating(PhaseConfig::new(7, 11, 1));
        assert_eq!(result.completed_iterations, 154);
    }

    #[test]
    fn phase_kernels_transform_state() {
        let seed = 0x1234_5678_9abc_def0;
        assert_ne!(branch_phase(100, seed), seed);
        assert_ne!(arithmetic_phase(100, seed), seed);
        assert_ne!(branch_phase(100, seed), arithmetic_phase(100, seed));
    }

    #[test]
    fn zero_rounds_preserve_the_seed() {
        let result = run_alternating(PhaseConfig::new(0, 100, 42));
        assert_eq!(result.checksum, 42);
        assert_eq!(result.completed_iterations, 0);
    }
}
