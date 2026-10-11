//! TLS 1.3 record budgeting, not encryption or a transport simulator.
//!
//! ```
//! use tls_record_sizing::{budget, content_limit};
//! assert_eq!(content_limit(16384, 4096, 31), Some(4064));
//! assert_eq!(budget(&[65536], 16384, 16385, 0), Some((4, 65624)));
//! ```
#![deny(missing_docs)]

/// Maximum content for one record under local cap, peer's negotiated receive
/// limit (inner plaintext bytes), and zero-padding length. `None` means an
/// invalid limit or no room for positive content. Protocol content cap is 16384.
/// A peer limit is not a directive to wait for a full record.
pub fn content_limit(local_cap: usize, peer_limit: usize, padding: usize) -> Option<usize> {
    if !(1..=16384).contains(&local_cap) || !(64..=16385).contains(&peer_limit) {
        return None;
    }
    let room = peer_limit.checked_sub(padding.checked_add(1)?)?;
    let content = local_cap.min(room);
    (content > 0).then_some(content)
}

/// Count records and TLS bytes for writes flushed individually, with a fixed
/// 16-byte AEAD tag and padding on every nonempty record. Empty writes generate
/// no application record in this model. Checked arithmetic rejects overflow.
/// Returns `(records, bytes)`; excludes TCP/IP, handshakes, alerts, and tickets.
pub fn budget(
    writes: &[usize],
    local_cap: usize,
    peer_limit: usize,
    padding: usize,
) -> Option<(usize, usize)> {
    let cap = content_limit(local_cap, peer_limit, padding)?;
    let overhead = padding.checked_add(22)?;
    let mut records = 0usize;
    let mut bytes = 0usize;
    for &len in writes {
        let n = len.div_ceil(cap);
        records = records.checked_add(n)?;
        bytes = bytes.checked_add(len.checked_add(n.checked_mul(overhead)?)?)?;
    }
    Some((records, bytes))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn receive_limit_counts_inner_type_and_padding() {
        assert_eq!(content_limit(16384, 64, 0), Some(63));
        assert_eq!(content_limit(16384, 4096, 31), Some(4064));
        assert_eq!(content_limit(16384, 16385, 0), Some(16384));
        for (cap, peer, padding) in [
            (0, 64, 0),
            (16385, 64, 0),
            (1, 63, 0),
            (1, 16386, 0),
            (1, 64, 63),
            (1, 64, usize::MAX),
        ] {
            assert_eq!(content_limit(cap, peer, padding), None);
        }
    }

    #[test]
    fn independent_fragmentation_oracle() {
        // Independently consume one record at a time, including cap boundaries.
        for cap in [1, 63, 1024, 4096, 16384] {
            for padding in [0, 7, 31] {
                for len in [0, 1, 63, 1023, 1024, 1025, 4095, 4096, 4097, 16384, 65536] {
                    let usable = cap.min(16384 - padding);
                    let mut left = len;
                    let (mut count, mut bytes) = (0, 0);
                    while left > 0 {
                        let take = left.min(usable);
                        left -= take;
                        count += 1;
                        bytes += take + 22 + padding;
                    }
                    assert_eq!(budget(&[len], cap, 16385, padding), Some((count, bytes)));
                }
            }
        }
    }

    #[test]
    fn flushes_prevent_coalescing() {
        assert_eq!(budget(&[128; 128], 16384, 16385, 0), Some((128, 19200)));
        assert_eq!(budget(&[16384], 16384, 16385, 0), Some((1, 16406)));
        assert_eq!(budget(&[0, 0], 4096, 16385, 0), Some((0, 0)));
    }

    #[test]
    fn arithmetic_overflow_is_rejected() {
        assert_eq!(budget(&[usize::MAX], 1, 16385, 0), None);
        assert_eq!(budget(&[usize::MAX, usize::MAX], 16384, 16385, 0), None);
    }
}
