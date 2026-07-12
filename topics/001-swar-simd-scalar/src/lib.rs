//! Counts byte equality with scalar, SWAR, and AArch64 NEON implementations.
//!
//! The three functions return the same count. The SWAR path uses a word-level
//! zero-byte test as a prefilter; it still counts candidate bytes exactly. The
//! NEON path processes 16 bytes at a time when the current CPU supports NEON.
//!
//! # Examples
//!
//! ```
//! use systems_snackpack_topic_001::{count_eq_neon, count_eq_scalar};
//!
//! let input = b"bananas";
//! assert_eq!(count_eq_scalar(input, b'a'), 3);
//! assert_eq!(count_eq_neon(input, b'a'), 3);
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

const ONES: u64 = 0x0101_0101_0101_0101;
const HIGHS: u64 = 0x8080_8080_8080_8080;

/// Counts bytes equal to `needle` with one comparison per input byte.
pub fn count_eq_scalar(input: &[u8], needle: u8) -> usize {
    input.iter().filter(|&&byte| byte == needle).count()
}

/// Counts bytes equal to `needle` with an eight-byte candidate prefilter.
///
/// The prefilter detects whether a word contains at least one matching byte.
/// It does not derive the count from the bit trick because borrows can mark a
/// neighboring byte. Candidate words use exact byte comparisons.
pub fn count_eq_swar_prefilter(input: &[u8], needle: u8) -> usize {
    let repeated = u64::from_ne_bytes([needle; 8]);
    let mut count = 0;
    let mut chunks = input.chunks_exact(8);

    for bytes in &mut chunks {
        let word = u64::from_ne_bytes(bytes.try_into().expect("eight-byte chunk"));
        if has_zero_byte(word ^ repeated) {
            count += bytes.iter().filter(|&&byte| byte == needle).count();
        }
    }

    count + count_eq_scalar(chunks.remainder(), needle)
}

/// Counts bytes equal to `needle` with AArch64 NEON when it is available.
///
/// Other targets, or AArch64 CPUs without NEON, use [`count_eq_scalar`].
pub fn count_eq_neon(input: &[u8], needle: u8) -> usize {
    #[cfg(target_arch = "aarch64")]
    {
        if std::arch::is_aarch64_feature_detected!("neon") {
            // SAFETY: runtime detection proves that the specialized function can execute.
            return unsafe { count_eq_neon_impl(input, needle) };
        }
    }

    count_eq_scalar(input, needle)
}

fn has_zero_byte(word: u64) -> bool {
    word.wrapping_sub(ONES) & !word & HIGHS != 0
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "neon")]
unsafe fn count_eq_neon_impl(input: &[u8], needle: u8) -> usize {
    use core::arch::aarch64::{vaddlvq_u8, vceqzq_u8, vdupq_n_u8, veorq_u8, vld1q_u8};

    let target = vdupq_n_u8(needle);
    let mut count = 0;
    let mut offset = 0;

    while offset + 16 <= input.len() {
        // SAFETY: the loop condition proves that 16 bytes start at `offset`.
        let bytes = unsafe { vld1q_u8(input.as_ptr().add(offset)) };
        let matches = vceqzq_u8(veorq_u8(bytes, target));
        count += usize::from(vaddlvq_u8(matches)) / 255;
        offset += 16;
    }

    count + count_eq_scalar(&input[offset..], needle)
}

#[cfg(test)]
mod tests {
    use super::{count_eq_neon, count_eq_scalar, count_eq_swar_prefilter};

    #[test]
    fn variants_match_for_empty_and_short_inputs() {
        for input in [b"".as_slice(), b"a", b"bananas", b"abcdefgh"] {
            for needle in [0, b'a', b'n', 255] {
                let expected = count_eq_scalar(input, needle);
                assert_eq!(count_eq_swar_prefilter(input, needle), expected);
                assert_eq!(count_eq_neon(input, needle), expected);
            }
        }
    }

    #[test]
    fn variants_match_for_deterministic_data() {
        let input: Vec<u8> = (0..4099).map(|index| (index * 37 % 251) as u8).collect();
        for needle in [0, 1, 17, 250, 255] {
            let expected = count_eq_scalar(&input, needle);
            assert_eq!(count_eq_swar_prefilter(&input, needle), expected);
            assert_eq!(count_eq_neon(&input, needle), expected);
        }
    }
}
