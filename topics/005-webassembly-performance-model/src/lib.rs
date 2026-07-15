//! Wrapping recurrence used to check the WebAssembly host-boundary experiment.
//!
//! The Wasm guest and C callback apply the same multiply-add modulo `2^64`.
//! [`iterate`] supplies an independent Rust oracle for their final digest.

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

/// Multiply coefficient shared by the Rust oracle, Wasm guest, and C callback.
pub const STEP_MULTIPLIER: u64 = 6_364_136_223_846_793_005;

/// Add coefficient shared by the Rust oracle, Wasm guest, and C callback.
pub const STEP_INCREMENT: u64 = 1_442_695_040_888_963_407;

/// Initial recurrence state shared by the Rust, Wasm, and C implementations.
pub const EXPERIMENT_SEED: u64 = 0x0123_4567_89ab_cdef;

/// Returns the recurrence after `iterations`, reducing each operation modulo `2^64`.
///
/// # Examples
///
/// ```
/// use systems_snackpack_topic_005::{STEP_INCREMENT, STEP_MULTIPLIER, iterate};
///
/// let start = 7_u64;
/// let expected = start
///     .wrapping_mul(STEP_MULTIPLIER)
///     .wrapping_add(STEP_INCREMENT);
/// assert_eq!(iterate(start, 1), expected);
/// ```
pub fn iterate(mut seed: u64, iterations: u64) -> u64 {
    for _ in 0..iterations {
        seed = seed
            .wrapping_mul(STEP_MULTIPLIER)
            .wrapping_add(STEP_INCREMENT);
    }
    seed
}

#[cfg(test)]
mod tests {
    use super::{EXPERIMENT_SEED, STEP_INCREMENT, STEP_MULTIPLIER, iterate};

    #[test]
    fn zero_steps_preserve_the_seed() {
        assert_eq!(iterate(EXPERIMENT_SEED, 0), EXPERIMENT_SEED);
    }

    #[test]
    fn one_step_matches_the_formula() {
        let expected = EXPERIMENT_SEED
            .wrapping_mul(STEP_MULTIPLIER)
            .wrapping_add(STEP_INCREMENT);
        assert_eq!(iterate(EXPERIMENT_SEED, 1), expected);
    }

    #[test]
    fn ten_million_step_digest_matches_the_recorded_experiment() {
        assert_eq!(iterate(EXPERIMENT_SEED, 10_000_000), 0x8546_3ddc_01d7_d46f);
    }
}
