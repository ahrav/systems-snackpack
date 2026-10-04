//! Compare synchronous native call shapes with identical unsigned arithmetic.
//!
//! C only borrows input during a call. Rust owns and releases all allocations.
//! Run `cargo run --release --example compare -- batch 4096 0`.
//!
//! ```
//! use topic_067_abi_ffi_performance_boundaries::{Candidate, run, oracle};
//! let input = [0, 1, u64::MAX];
//! assert_eq!(run(Candidate::Batch, &input, 16), oracle(&input, 16));
//! ```

unsafe extern "C" {
    fn topic67_one(value: u64, rounds: u32) -> u64;
    fn topic67_batch(values: *const u64, len: usize, rounds: u32) -> u64;
}

/// Implemented call shapes. All return the same sum modulo 2^64.
#[derive(Clone, Copy, Debug)]
pub enum Candidate {
    /// Same-language loop; the optimizer sees each transform.
    Rust,
    /// One native C call per element.
    Scalar,
    /// Borrowed C batches of at most 256 elements.
    Chunk256,
    /// One borrowed C batch for the entire input, including an empty input.
    Batch,
    /// Allocate, copy, call once, and release the temporary on every request.
    Copy,
}
impl Candidate {
    /// Parse the command-line spelling.
    pub fn parse(name: &str) -> Option<Self> {
        match name {
            "rust" => Some(Self::Rust),
            "scalar" => Some(Self::Scalar),
            "chunk256" => Some(Self::Chunk256),
            "batch" => Some(Self::Batch),
            "copy" => Some(Self::Copy),
            _ => None,
        }
    }
}

#[inline]
fn transform(mut x: u64, rounds: u32) -> u64 {
    for _ in 0..rounds {
        x = x
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        x ^= x >> 29;
    }
    x
}

fn borrowed(values: &[u64], rounds: u32) -> u64 {
    // SAFETY: a Rust slice supplies initialized, aligned, readable storage for
    // len elements. C neither writes nor retains it, and returns synchronously.
    // Its n==0 branch performs no access even for an empty slice's sentinel.
    unsafe { topic67_batch(values.as_ptr(), values.len(), rounds) }
}

/// Execute one complete request. Copy includes allocation, copy and deallocation.
pub fn run(candidate: Candidate, values: &[u64], rounds: u32) -> u64 {
    match candidate {
        Candidate::Rust => values
            .iter()
            .fold(0_u64, |s, &x| s.wrapping_add(transform(x, rounds))),
        Candidate::Scalar => values.iter().fold(0_u64, |s, &x| {
            // SAFETY: C accepts every u64 and u32 and has no pointer arguments.
            s.wrapping_add(unsafe { topic67_one(x, rounds) })
        }),
        Candidate::Chunk256 => values
            .chunks(256)
            .fold(0_u64, |s, xs| s.wrapping_add(borrowed(xs, rounds))),
        Candidate::Batch => borrowed(values, rounds),
        Candidate::Copy => {
            let owned = values.to_vec();
            borrowed(&owned, rounds)
        }
    }
}

/// Independent wider-integer oracle, outside every timing boundary.
/// Reduces the arithmetic explicitly before each xor, rather than using wrapping u64 operations.
pub fn oracle(values: &[u64], rounds: u32) -> u64 {
    let modulus = 1_u128 << 64;
    let mut total = 0_u128;
    for &value in values {
        let mut x = u128::from(value);
        for _ in 0..rounds {
            x = (x * 6_364_136_223_846_793_005_u128 + 1_442_695_040_888_963_407_u128) % modulus;
            x ^= x >> 29;
        }
        total = (total + x) % modulus;
    }
    total as u64
}

/// Deterministic full-width input, including values whose arithmetic overflows.
pub fn input(len: usize) -> Vec<u64> {
    (0..len)
        .map(|i| (i as u64).wrapping_mul(0x9e3779b97f4a7c15) ^ u64::MAX)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    const ALL: [Candidate; 5] = [
        Candidate::Rust,
        Candidate::Scalar,
        Candidate::Chunk256,
        Candidate::Batch,
        Candidate::Copy,
    ];
    #[test]
    fn tails_and_work_sweep() {
        for len in [0, 1, 2, 31, 255, 256, 257, 4096] {
            for rounds in [0, 1, 2, 16, 31] {
                let xs = input(len);
                for c in ALL {
                    assert_eq!(run(c, &xs, rounds), oracle(&xs, rounds));
                }
            }
        }
    }
    #[test]
    fn adversarial_values_and_immutability() {
        for xs in [
            vec![0; 257],
            vec![u64::MAX; 257],
            vec![0, 1, u64::MAX, 1 << 63, (1 << 63) - 1],
        ] {
            let before = xs.clone();
            for c in ALL {
                assert_eq!(run(c, &xs, 32), oracle(&xs, 32));
                assert_eq!(xs, before);
            }
        }
    }
    #[test]
    fn c_accepts_null_only_for_zero_length() {
        // SAFETY: the documented C contract permits null for an empty input.
        assert_eq!(unsafe { topic67_batch(std::ptr::null(), 0, 16) }, 0);
    }
    #[test]
    fn partition_sum_matches_full_sum() {
        let xs = input(4097);
        for split in [0, 1, 256, 4096, 4097] {
            let a = run(Candidate::Batch, &xs[..split], 16);
            let b = run(Candidate::Batch, &xs[split..], 16);
            assert_eq!(a.wrapping_add(b), oracle(&xs, 16));
        }
    }
}
