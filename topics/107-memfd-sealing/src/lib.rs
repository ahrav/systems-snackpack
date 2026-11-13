//! Validate a fixed shared-buffer envelope after the caller queries Linux seals.
//!
//! This pure policy check performs no syscalls. Query seals before obtaining the
//! length; retain the same backing object through parsing and use.
//!
//! ```
//! use memfd_sealing::{checked_range, immutable};
//! assert!(immutable(0x0e));
//! assert_eq!(checked_range(32, 24, 8), Some(24..32));
//! ```

/// Whether WRITE, SHRINK, and GROW seals are all present in a Linux seal mask.
pub fn immutable(seals: u32) -> bool {
    seals & 0x0e == 0x0e
}

/// Validate a byte range without overflowing offset plus count.
pub fn checked_range(length: usize, offset: usize, count: usize) -> Option<std::ops::Range<usize>> {
    if offset <= length && count <= length - offset {
        Some(offset..offset + count)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn immutable_requires_each_restriction() {
        assert!(immutable(0x0e));
        assert!(immutable(0x1f));
        for missing in [2, 4, 8] {
            assert!(!immutable(0x0e & !missing));
        }
        assert!(!immutable(0x16)); // FUTURE_WRITE, SHRINK, GROW.
    }

    #[test]
    fn ranges_match_enumerated_membership() {
        for length in 0..32 {
            let bytes: Vec<_> = (0..length).collect();
            for offset in 0..40 {
                for count in 0..40 {
                    let expected = bytes.get(offset..offset + count).is_some();
                    assert_eq!(checked_range(length, offset, count).is_some(), expected);
                }
            }
        }
        assert_eq!(checked_range(usize::MAX, usize::MAX, 1), None);
        assert_eq!(checked_range(10, usize::MAX, 2), None);
    }
}
