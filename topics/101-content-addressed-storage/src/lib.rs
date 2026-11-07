//! Versioned educational chunk boundaries for immutable snapshot storage.
//! The rolling fingerprint selects boundaries; a separate digest identifies bytes.
//!
//! ```
//! use content_addressed_storage::{boundaries, Policy};
//! assert_eq!(boundaries(&[0; 4097], Policy::Fixed), vec![4096, 4097]);
//! ```

/// Version-one chunk policy.
#[derive(Clone, Copy)]
pub enum Policy {
    /// A single chunk for each nonempty file.
    Whole,
    /// Chunks of 4096 bytes, with a possibly shorter tail.
    Fixed,
    /// Polynomial window: 64 bytes, base 257, minimum 2048, maximum 16384.
    Content,
}

/// Exclusive chunk ends. Empty input produces an empty manifest.
///
/// Content mode cuts at low 12 fingerprint bits zero after the minimum,
/// or at the maximum. State resets after every cut. Arithmetic wraps at 64 bits.
#[must_use]
pub fn boundaries(data: &[u8], policy: Policy) -> Vec<usize> {
    match policy {
        Policy::Whole => {
            if data.is_empty() {
                vec![]
            } else {
                vec![data.len()]
            }
        }
        Policy::Fixed => (0..data.len())
            .step_by(4096)
            .map(|s| (s + 4096).min(data.len()))
            .collect(),
        Policy::Content => {
            let mut ends = Vec::new();
            let mut start = 0;
            let mut fp = 0_u64;
            let power = 257_u64.wrapping_pow(64);
            for (i, byte) in data.iter().enumerate() {
                fp = fp.wrapping_mul(257).wrapping_add(u64::from(*byte));
                if i - start >= 64 {
                    fp = fp.wrapping_sub(u64::from(data[i - 64]).wrapping_mul(power));
                }
                let len = i + 1 - start;
                if len >= 16384 || (len >= 2048 && fp & 4095 == 0) {
                    ends.push(i + 1);
                    start = i + 1;
                    fp = 0;
                }
            }
            if start < data.len() {
                ends.push(data.len());
            }
            ends
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn boundaries_and_forcing() {
        assert!(boundaries(&[], Policy::Content).is_empty());
        assert_eq!(
            boundaries(&[0; 4097], Policy::Content),
            vec![2048, 4096, 4097]
        );
        let data = vec![1; 40000];
        let mut prev = 0;
        for end in boundaries(&data, Policy::Content) {
            assert!(end - prev <= 16384);
            assert!(end == data.len() || end - prev >= 2048);
            prev = end;
        }
        assert_eq!(prev, data.len());
    }

    fn window_oracle(data: &[u8]) -> Vec<usize> {
        let (mut ends, mut start) = (Vec::new(), 0);
        for end in 1..=data.len() {
            let fp = data[start.max(end.saturating_sub(64))..end]
                .iter()
                .fold(0_u64, |acc, b| {
                    acc.wrapping_mul(257).wrapping_add(u64::from(*b))
                });
            if end - start >= 16384 || (end - start >= 2048 && fp & 4095 == 0) {
                ends.push(end);
                start = end;
            }
        }
        if start < data.len() {
            ends.push(data.len());
        }
        ends
    }

    #[test]
    fn rolling_window_matches_direct_oracle() {
        let mut state = 0x9E37_79B9_7F4A_7C15_u64;
        let data: Vec<u8> = (0..40000)
            .map(|_| {
                state = state
                    .wrapping_mul(6_364_136_223_846_793_005)
                    .wrapping_add(1_442_695_040_888_963_407);
                (state >> 56) as u8
            })
            .collect();
        let ends = boundaries(&data, Policy::Content);
        assert_eq!(ends, window_oracle(&data));
        assert!(
            ends[0] < 16384,
            "first cut must come from the fingerprint, not the ceiling"
        );
    }

    #[test]
    fn whole_and_fixed_edges() {
        assert!(boundaries(&[], Policy::Whole).is_empty());
        assert_eq!(boundaries(&[7; 3], Policy::Whole), vec![3]);
        assert!(boundaries(&[], Policy::Fixed).is_empty());
        assert_eq!(boundaries(&[0; 4096], Policy::Fixed), vec![4096]);
    }
}
