//! Decide which catalog request the broker can serve from a private copy.
//!
//! The Linux example in `broker.c` tests the kernel delivery operation.
//!
//! ```
//! use topic113_seccomp_broker::select_catalog;
//! let mut target = *b"catalog\0";
//! let selected = select_catalog(&target);
//! target.fill(0);
//! assert!(selected);
//! assert!(!select_catalog(&target));
//! ```

/// Accept a complete eight-byte copy of the service name and terminator.
pub fn select_catalog(copied: &[u8]) -> bool {
    copied == b"catalog\0"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_partial_names_and_single_byte_substitutions() {
        let valid = *b"catalog\0";
        for len in 0..valid.len() {
            assert!(!select_catalog(&valid[..len]));
        }
        for pos in 0..valid.len() {
            for byte in u8::MIN..=u8::MAX {
                let mut request = valid;
                request[pos] = byte;
                assert_eq!(select_catalog(&request), byte == valid[pos]);
            }
        }
        assert!(!select_catalog(b"catalog\0x"));
    }
}
