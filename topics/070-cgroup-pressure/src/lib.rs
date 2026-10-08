//! Independent jobs under CPU bandwidth limits.
//!
//! Run `cargo run --release --example quota -- 4 1024 200000` on Linux.
//! The serial affine-composition oracle checks every output without repeating
//! the timed recurrence. This is a synthetic CPU workload, not a hash function.

const MULTIPLIER: u64 = 6364136223846793005;
const INCREMENT: u64 = 1442695040888963407;

/// Computes one deterministic job using wrapping 64-bit arithmetic.
pub fn job(seed: u64, steps: u32) -> u64 {
    let mut value = seed;
    for _ in 0..steps {
        value = value.wrapping_mul(MULTIPLIER).wrapping_add(INCREMENT);
    }
    value
}

/// Computes the same recurrence by composing affine maps in logarithmic work.
///
/// ```
/// assert_eq!(cgroup_pressure::oracle(7, 123), cgroup_pressure::job(7, 123));
/// ```
pub fn oracle(seed: u64, mut steps: u32) -> u64 {
    let (mut mul, mut add) = (MULTIPLIER, INCREMENT);
    let (mut result_mul, mut result_add) = (1_u64, 0_u64);
    while steps != 0 {
        if steps & 1 != 0 {
            result_add = result_add.wrapping_mul(mul).wrapping_add(add);
            result_mul = result_mul.wrapping_mul(mul);
        }
        add = add.wrapping_mul(mul.wrapping_add(1));
        mul = mul.wrapping_mul(mul);
        steps >>= 1;
    }
    result_mul.wrapping_mul(seed).wrapping_add(result_add)
}

/// Allocates output, starts workers, computes all jobs, and joins every worker.
///
/// Output index `i` is [`job`] with seed `i + 1`. Empty input is valid.
/// Panics when `workers` is zero. Allocation and worker creation are deliberate
/// parts of the measured batch boundary.
pub fn batch(workers: usize, jobs: usize, steps: u32) -> Vec<u64> {
    assert!(workers > 0);
    let mut output = vec![0; jobs];
    if jobs == 0 {
        return output;
    }
    let chunk_size = jobs.div_ceil(workers);
    std::thread::scope(|scope| {
        for (chunk, values) in output.chunks_mut(chunk_size).enumerate() {
            scope.spawn(move || {
                for (offset, value) in values.iter_mut().enumerate() {
                    *value = job((chunk * chunk_size + offset + 1) as u64, steps);
                }
            });
        }
    });
    output
}

/// Returns a nonnegative delta, or None for a decrease.
///
/// The caller must separately reject changed source identities; a reset followed
/// by enough new increments cannot be detected from two values alone.
pub fn delta(before: u64, after: u64) -> Option<u64> {
    after.checked_sub(before)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn oracle_matches_recurrence_edges() {
        for seed in [0, 1, 7, u64::MAX] {
            for steps in [0, 1, 2, 3, 31, 1000, 200000] {
                assert_eq!(job(seed, steps), oracle(seed, steps));
            }
        }
    }
    #[test]
    fn every_output_matches_oracle() {
        for workers in [1, 2, 4, 16] {
            for jobs in [0, 1, 3, 17, 64] {
                let output = batch(workers, jobs, 1031);
                let expected: Vec<_> = (1..=jobs).map(|i| oracle(i as u64, 1031)).collect();
                assert_eq!(output, expected);
            }
        }
    }
    #[test]
    fn resets_are_not_zero() {
        assert_eq!(delta(11, 10), None);
        assert_eq!(delta(10, 10), Some(0));
        assert_eq!(delta(10, 12), Some(2));
    }
    #[test]
    #[should_panic]
    fn reject_zero_workers() {
        batch(0, 1, 1);
    }
}
