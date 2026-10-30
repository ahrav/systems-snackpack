//! Checked borrowed and owned decoding of a flat binary record batch.
//! Payloads are contiguous, ordered and fully cover the suffix after the directory.
//!
//! ```
//! use topic093_wire_format::{encode, View};
//! let bytes = encode(&[(7, b"abc".to_vec())]);
//! let view = View::parse(&bytes).unwrap();
//! assert_eq!(view.record(0), Some((7, &b"abc"[..])));
//! ```

/// A malformed header, directory or payload extent.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Invalid;

fn word(bytes: &[u8], at: usize) -> u32 {
    u32::from_le_bytes(bytes[at..at + 4].try_into().unwrap())
}

/// A validated immutable view that borrows its input.
#[derive(Clone, Copy, Debug)]
pub struct View<'a> {
    bytes: &'a [u8],
    count: usize,
}

impl<'a> View<'a> {
    /// Validate the complete directory before exposing any record.
    pub fn parse(bytes: &'a [u8]) -> Result<Self, Invalid> {
        if bytes.len() < 8 || &bytes[..4] != b"W093" {
            return Err(Invalid);
        }
        let count = word(bytes, 4) as usize;
        if count > (bytes.len() - 8) / 12 {
            return Err(Invalid);
        }
        let mut end = 8 + count * 12;
        for i in 0..count {
            let at = 8 + i * 12;
            let off = word(bytes, at + 4) as usize;
            let len = word(bytes, at + 8) as usize;
            if off != end || off > bytes.len() || len > bytes.len() - off {
                return Err(Invalid);
            }
            end = off + len;
        }
        if end != bytes.len() {
            return Err(Invalid);
        }
        Ok(Self { bytes, count })
    }

    /// Number of validated records.
    pub fn len(&self) -> usize {
        self.count
    }

    /// Whether the batch contains no records.
    pub fn is_empty(&self) -> bool {
        self.count == 0
    }

    /// Read an ID and borrow its binary payload; out-of-range indices return `None`.
    pub fn record(&self, index: usize) -> Option<(u32, &'a [u8])> {
        if index >= self.count {
            return None;
        }
        let at = 8 + index * 12;
        let off = word(self.bytes, at + 4) as usize;
        let len = word(self.bytes, at + 8) as usize;
        Some((word(self.bytes, at), &self.bytes[off..off + len]))
    }
}

/// Independently owned payloads and native IDs.
pub type Owned = Vec<(u32, Vec<u8>)>;

/// Validate with the same contract, then allocate and copy all payloads.
pub fn decode_owned(bytes: &[u8]) -> Result<Owned, Invalid> {
    let view = View::parse(bytes)?;
    Ok((0..view.len())
        .map(|i| {
            let (id, payload) = view.record(i).unwrap();
            (id, payload.to_vec())
        })
        .collect())
}

/// Encode records with absolute offsets. Panics if the message exceeds `u32::MAX` bytes.
pub fn encode(records: &[(u32, Vec<u8>)]) -> Vec<u8> {
    let mut out = b"W093".to_vec();
    out.extend_from_slice(&u32::try_from(records.len()).unwrap().to_le_bytes());
    let mut off = 8usize
        .checked_add(records.len().checked_mul(12).unwrap())
        .unwrap();
    for (id, payload) in records {
        out.extend_from_slice(&id.to_le_bytes());
        out.extend_from_slice(&u32::try_from(off).unwrap().to_le_bytes());
        out.extend_from_slice(&u32::try_from(payload.len()).unwrap().to_le_bytes());
        off = off.checked_add(payload.len()).unwrap();
        u32::try_from(off).unwrap();
    }
    for (_, payload) in records {
        out.extend_from_slice(payload);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_and_borrow_identity() {
        let rows = vec![(7, b"abc".to_vec()), (u32::MAX, vec![])];
        let bytes = encode(&rows);
        let view = View::parse(&bytes).unwrap();
        assert_eq!(decode_owned(&bytes).unwrap(), rows);
        assert_eq!(view.record(0).unwrap().1.as_ptr(), bytes[32..].as_ptr());
        assert_eq!(view.record(2), None);
        assert_eq!(view.record(usize::MAX), None);
        assert!(View::parse(&encode(&[])).unwrap().is_empty());
    }

    #[test]
    fn unaligned_input() {
        let bytes = encode(&[(9, vec![0, 255, 128])]);
        let mut shifted = vec![0];
        shifted.extend(&bytes);
        assert_eq!(decode_owned(&shifted[1..]), decode_owned(&bytes));
    }

    #[test]
    fn malformed_extents() {
        let valid = encode(&[(3, b"abc".to_vec()), (4, b"de".to_vec())]);
        for end in 0..valid.len() {
            assert!(View::parse(&valid[..end]).is_err());
        }
        let mut extra = valid.clone();
        extra.push(0);
        assert!(View::parse(&extra).is_err());
        for at in [0, 4, 12, 16, 24, 28] {
            for value in [0, 1, 8, 31, 33, u32::MAX] {
                let mut bad = valid.clone();
                bad[at..at + 4].copy_from_slice(&value.to_le_bytes());
                assert!(View::parse(&bad).is_err(), "{at} {value}");
            }
        }
    }
}
