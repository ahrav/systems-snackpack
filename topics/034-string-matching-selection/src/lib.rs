//! Exact byte matchers with opposing progress rules and periodic-input traps.
//!
//! Every matcher returns the first byte offset, treats an empty needle as a
//! match at offset zero, and accepts arbitrary byte values. The
//! `string-match-probe` binary keeps preparation reuse separate from one-shot
//! construction so setup cost is not silently amortized.

/// Returns the first exact byte match using the differential test oracle.
///
/// This implementation shares the public contract but no prepared state or
/// progress table with the three matchers under test.
#[must_use]
pub fn oracle_find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() {
        return Some(0);
    }
    if needle.len() > haystack.len() {
        return None;
    }

    for start in 0..=haystack.len() - needle.len() {
        let mut matched = true;
        for offset in 0..needle.len() {
            if haystack[start + offset] != needle[offset] {
                matched = false;
                break;
            }
        }
        if matched {
            return Some(start);
        }
    }
    None
}

/// Returns the first exact byte match by testing candidate starts in order.
///
/// This matcher has no preparation step. Repeated prefixes can make it compare
/// almost the full needle at every alignment.
#[must_use]
pub fn left_to_right_find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() {
        return Some(0);
    }
    if needle.len() > haystack.len() {
        return None;
    }

    let last_start = haystack.len() - needle.len();
    let first = needle[0];
    let mut start = 0;
    while start <= last_start {
        if haystack[start] == first && haystack[start..start + needle.len()] == *needle {
            return Some(start);
        }
        start += 1;
    }
    None
}

/// A prepared Knuth-Morris-Pratt matcher.
///
/// At position `i`, `prefix[i]` records the longest proper prefix of the needle
/// that equals a suffix ending at `i`. Mismatch fallback changes only the
/// matched-prefix length; search never moves the haystack cursor backward.
#[derive(Debug, Clone)]
pub struct KmpPlan<'a> {
    needle: &'a [u8],
    prefix: Vec<usize>,
}

impl<'a> KmpPlan<'a> {
    /// Build a prefix table for `needle` in time and storage proportional to
    /// its length.
    #[must_use]
    pub fn new(needle: &'a [u8]) -> Self {
        let mut prefix = vec![0; needle.len()];
        let mut matched = 0;
        for index in 1..needle.len() {
            while matched > 0 && needle[index] != needle[matched] {
                matched = prefix[matched - 1];
            }
            if needle[index] == needle[matched] {
                matched += 1;
            }
            prefix[index] = matched;
        }
        Self { needle, prefix }
    }

    /// Returns the first exact byte match without moving the haystack cursor
    /// backward after a mismatch.
    #[must_use]
    pub fn find(&self, haystack: &[u8]) -> Option<usize> {
        if self.needle.is_empty() {
            return Some(0);
        }

        let mut matched = 0;
        for (index, &byte) in haystack.iter().enumerate() {
            while matched > 0 && byte != self.needle[matched] {
                matched = self.prefix[matched - 1];
            }
            if byte == self.needle[matched] {
                matched += 1;
                if matched == self.needle.len() {
                    return Some(index + 1 - self.needle.len());
                }
            }
        }
        None
    }
}

/// A prepared Boyer-Moore-Horspool byte matcher.
///
/// The fixed table maps an aligned window's final byte to its next candidate
/// displacement. Repeated bytes use their rightmost occurrence before the
/// needle's final byte, which yields the smallest safe shift.
#[derive(Debug, Clone)]
pub struct HorspoolPlan<'a> {
    needle: &'a [u8],
    shift: [usize; 256],
}

impl<'a> HorspoolPlan<'a> {
    /// Builds a shift table that excludes the needle's final byte from
    /// occurrence updates.
    #[must_use]
    pub fn new(needle: &'a [u8]) -> Self {
        let default_shift = needle.len().max(1);
        let mut shift = [default_shift; 256];
        if needle.len() > 1 {
            for (index, &byte) in needle[..needle.len() - 1].iter().enumerate() {
                shift[usize::from(byte)] = needle.len() - 1 - index;
            }
        }
        Self { needle, shift }
    }

    /// Returns the first exact byte match after right-to-left window checks.
    ///
    /// A one-byte shift after a near-complete mismatch permits multiplicative
    /// worst-case work.
    #[must_use]
    pub fn find(&self, haystack: &[u8]) -> Option<usize> {
        let needle_len = self.needle.len();
        if needle_len == 0 {
            return Some(0);
        }
        if needle_len > haystack.len() {
            return None;
        }

        let mut end = needle_len - 1;
        while end < haystack.len() {
            let start = end + 1 - needle_len;
            let mut offset = needle_len;
            while offset > 0 && self.needle[offset - 1] == haystack[start + offset - 1] {
                offset -= 1;
            }
            if offset == 0 {
                return Some(start);
            }
            end = end.saturating_add(self.shift[usize::from(haystack[end])]);
        }
        None
    }
}

/// Runs fixed, exhaustive binary-alphabet, and deterministic full-byte
/// differential checks.
///
/// The returned count includes every input pair passed to all three matchers.
///
/// # Panics
///
/// Panics when any source-defined matcher disagrees with the oracle.
#[must_use]
pub fn verify_contract() -> usize {
    let fixtures: &[(&[u8], &[u8])] = &[
        (b"", b""),
        (b"", b"x"),
        (b"abc", b""),
        (b"abc", b"abcd"),
        (b"abc", b"a"),
        (b"abc", b"c"),
        (b"ababa", b"aba"),
        (b"abc", b"z"),
        (&[0, 1, 0, 2], &[0, 2]),
        (&[0xff, 0, 0xff], &[0, 0xff]),
    ];
    let mut checked = 0;
    for &(haystack, needle) in fixtures {
        check_one(haystack, needle);
        checked += 1;
    }

    for haystack_len in 0..=8 {
        for haystack_bits in 0..(1_usize << haystack_len) {
            let haystack = bit_string(haystack_bits, haystack_len);
            for needle_len in 0..=5 {
                for needle_bits in 0..(1_usize << needle_len) {
                    let needle = bit_string(needle_bits, needle_len);
                    check_one(&haystack, &needle);
                    checked += 1;
                }
            }
        }
    }

    let mut state = 0x34f0_19ac_d572_6b81_u64;
    for _ in 0..10_000 {
        let haystack_len = usize::try_from(next_random(&mut state) % 129).unwrap();
        let needle_len = usize::try_from(next_random(&mut state) % 41).unwrap();
        let mut haystack = vec![0; haystack_len];
        let mut needle = vec![0; needle_len];
        for byte in &mut haystack {
            *byte = next_random(&mut state).to_le_bytes()[0];
        }
        for byte in &mut needle {
            *byte = next_random(&mut state).to_le_bytes()[0];
        }
        check_one(&haystack, &needle);
        checked += 1;
    }
    checked
}

fn check_one(haystack: &[u8], needle: &[u8]) {
    let expected = oracle_find(haystack, needle);
    assert_eq!(left_to_right_find(haystack, needle), expected);
    assert_eq!(KmpPlan::new(needle).find(haystack), expected);
    assert_eq!(HorspoolPlan::new(needle).find(haystack), expected);
}

fn bit_string(bits: usize, len: usize) -> Vec<u8> {
    (0..len)
        .map(|shift| u8::from(((bits >> shift) & 1) != 0))
        .collect()
}

fn next_random(state: &mut u64) -> u64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    *state
}

/// Linked-code inspection hook for the left-to-right matcher.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic034_left_to_right_find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    left_to_right_find(haystack, needle)
}

/// Linked-code inspection hook for Knuth-Morris-Pratt, including preparation.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic034_kmp_find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    KmpPlan::new(needle).find(haystack)
}

/// Linked-code inspection hook for Boyer-Moore-Horspool, including preparation.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic034_horspool_find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    HorspoolPlan::new(needle).find(haystack)
}

#[cfg(test)]
mod tests {
    use super::verify_contract;

    #[test]
    fn matchers_agree_with_oracle() {
        assert_eq!(verify_contract(), 42_203);
    }
}
