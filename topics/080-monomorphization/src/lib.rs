//! Compare a type-specialized fingerprint loop with a shared concrete core.
//!
//! Every operation wraps modulo 2^64. This fingerprint has no security contract.
//! Run `python3 topics/080-monomorphization/scripts/campaign.py OUTPUT_DIR` for
//! separate executables, an independent oracle, and paired measurements.
//!
//! ```
//! use monomorphization::{Format, generic, outlined};
//! assert_eq!(generic::<Format<7>>(b"record"), outlined::<Format<7>>(b"record"));
//! assert_eq!(generic::<Format<7>>(b""), 7);
//! ```

/// Supplies the initial state; the per-byte operation is independent of policy.
pub trait Policy {
    /// Initial fingerprint state.
    const SEED: u64;
}

/// A distinct concrete policy type for each seed.
pub struct Format<const N: u64>;
impl<const N: u64> Policy for Format<N> {
    const SEED: u64 = N;
}

/// Fingerprint with a type-specific initial state and a generic loop body.
#[inline(never)]
pub fn generic<P: Policy>(bytes: &[u8]) -> u64 {
    let mut h = P::SEED;
    for &b in bytes {
        h = (h ^ u64::from(b))
            .wrapping_mul(0x100_0000_01b3)
            .rotate_left(7);
    }
    h
}

/// Fingerprint using a runtime seed and one source-level concrete loop.
///
/// Inspect final code to determine whether the compiler retains this boundary.
#[inline(never)]
pub fn shared_core(bytes: &[u8], mut h: u64) -> u64 {
    for &b in bytes {
        h = (h ^ u64::from(b))
            .wrapping_mul(0x100_0000_01b3)
            .rotate_left(7);
    }
    h
}

/// Normalize the policy once, before entering the concrete loop.
#[inline(never)]
pub fn outlined<P: Policy>(bytes: &[u8]) -> u64 {
    shared_core(bytes, P::SEED)
}

/// Input fixture, independent of the selected policy.
pub fn input(len: usize) -> Vec<u8> {
    (0..len)
        .map(|i| (i as u8).wrapping_mul(17).wrapping_add(3))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_returns_seed_including_extremes() {
        assert_eq!(generic::<Format<0>>(&[]), 0);
        assert_eq!(outlined::<Format<{ u64::MAX }>>(&[]), u64::MAX);
    }

    #[test]
    fn zero_byte_has_known_rotation() {
        assert_eq!(generic::<Format<1>>(&[0]), 0x8000_0000_d980);
        assert_eq!(shared_core(&[0], 1), 0x8000_0000_d980);
    }

    #[test]
    fn all_byte_values_and_boundary_lengths_agree() {
        for len in [0, 1, 2, 7, 8, 9, 15, 16, 17, 255, 256, 257, 4096] {
            let bytes = input(len);
            assert_eq!(generic::<Format<1>>(&bytes), outlined::<Format<1>>(&bytes));
            assert_eq!(
                generic::<Format<16>>(&bytes),
                outlined::<Format<16>>(&bytes)
            );
            assert_eq!(
                generic::<Format<{ u64::MAX }>>(&bytes),
                outlined::<Format<{ u64::MAX }>>(&bytes)
            );
        }
    }

    #[test]
    fn fixture_spans_every_byte() {
        let mut bytes = input(256);
        bytes.sort();
        assert_eq!(bytes, (0..=255).collect::<Vec<u8>>());
    }
}
