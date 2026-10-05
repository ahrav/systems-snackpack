//! Compare equality semantics and timing shapes. This is not a cryptographic certification.
//!
//! Lengths are public. Only the final equality result is deliberately released.
//! `early` is an insecure timing control; `xor` is a compiler-dependent teaching loop.
//! `reviewed` uses subtle 2.6.1, whose constant-time protection is best effort.
//!
//! ```
//! use constant_time_systems::{early, xor, reviewed};
//! for compare in [early, xor, reviewed] {
//!     assert!(compare(b"tag", b"tag"));
//!     assert!(!compare(b"tag", b"tap"));
//! }
//! ```
use subtle::ConstantTimeEq;

/// Return at the first mismatch. Correct equality, unsuitable for secret comparison.
#[inline(never)]
pub fn early(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    for (&x, &y) in a.iter().zip(b) {
        if x != y {
            return false;
        }
    }
    true
}

/// Full XOR/OR reduction. Source shape is not a constant-time compiler guarantee.
#[inline(never)]
pub fn xor(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.iter().zip(b).fold(0u8, |acc, (&x, &y)| acc | (x ^ y)) == 0
}

/// Use subtle 2.6.1's slice comparison, releasing only the final equality result.
///
/// Different public lengths return false immediately. Preserve `Choice` instead of
/// converting to bool if this result must remain secret in a larger computation.
#[inline(never)]
pub fn reviewed(a: &[u8], b: &[u8]) -> bool {
    bool::from(a.ct_eq(b))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn check(a: &[u8], b: &[u8]) {
        let oracle = a == b;
        for f in [early, xor, reviewed] {
            assert_eq!(f(a, b), oracle);
        }
    }
    #[test]
    fn exhaustive_single_bytes() {
        for a in 0..=255u8 {
            for b in 0..=255u8 {
                check(&[a], &[b]);
            }
        }
    }
    #[test]
    fn lengths_positions_and_unaligned_slices() {
        for n in [
            0, 1, 2, 7, 15, 16, 17, 31, 32, 33, 63, 64, 65, 255, 256, 257, 4096,
        ] {
            let a: Vec<u8> = (0..n + 3).map(|i| (i * 17) as u8).collect();
            let a = &a[1..n + 1];
            check(a, a);
            for position in 0..n {
                let mut b = a.to_vec();
                b[position] ^= 0x80;
                check(a, &b);
            }
            let mut longer = a.to_vec();
            longer.push(0);
            check(a, &longer);
            check(&longer, a);
        }
    }
    #[test]
    fn deterministic_random_multi_mismatch() {
        let mut seed = 0x1731u64;
        for n in 0..257 {
            let mut a = vec![0; n];
            let mut b = vec![0; n];
            for x in a.iter_mut().chain(b.iter_mut()) {
                seed ^= seed << 13;
                seed ^= seed >> 7;
                seed ^= seed << 17;
                *x = seed as u8;
            }
            check(&a, &b);
        }
    }
}
