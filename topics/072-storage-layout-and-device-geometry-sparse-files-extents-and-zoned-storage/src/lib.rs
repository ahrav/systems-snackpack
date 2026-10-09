//! File-layout contracts and a checked sequential-zone cursor.
//! Run `cargo run --release --example layout -- DIR sparse 65536 scattered` on Linux.

/// Size of one data write in the file experiment, in bytes.
pub const BLOCK: u64 = 4096;

/// Which blocks receive nonzero bytes.
#[derive(Clone, Copy, Debug)]
pub enum Pattern {
    /// No data writes.
    Empty,
    /// Every block receives data.
    Dense,
    /// One block in each group of 64 receives data.
    Scattered,
    /// The same count as scattered, at the start of the file.
    Clustered,
}

impl Pattern {
    /// Parse the experiment's fixed pattern names.
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "empty" => Some(Self::Empty),
            "dense" => Some(Self::Dense),
            "scattered" => Some(Self::Scattered),
            "clustered" => Some(Self::Clustered),
            _ => None,
        }
    }
}

/// Generate block starts to write; a final partial block is allowed.
pub fn offsets(len: u64, pattern: Pattern) -> Vec<u64> {
    let blocks = len.div_ceil(BLOCK);
    let indices: Box<dyn Iterator<Item = u64>> = match pattern {
        Pattern::Empty => Box::new(0..0),
        Pattern::Dense => Box::new(0..blocks),
        Pattern::Scattered => Box::new((0..blocks).step_by(64)),
        Pattern::Clustered => Box::new(0..blocks.div_ceil(64)),
    };
    indices.map(|i| i * BLOCK).collect()
}

/// Independent byte oracle, expressed as a predicate rather than a write list.
pub fn expected_byte(pos: u64, len: u64, pattern: Pattern, value: u8) -> u8 {
    assert!(pos < len);
    let block = pos / BLOCK;
    let selected = match pattern {
        Pattern::Empty => false,
        Pattern::Dense => true,
        Pattern::Scattered => block.is_multiple_of(64),
        Pattern::Clustered => block < len.div_ceil(BLOCK).div_ceil(64),
    };
    if selected { value } else { 0 }
}

/// An in-memory sequential-zone cursor, in bytes, for one serialized owner.
///
/// Exclusive ownership of the device range is an external assumption, not enforced.
/// This checks geometry and write placement. It does not submit I/O, model
/// open/active resource limits, or implement recovery after an unknown outcome.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Zone {
    start: u64,
    capacity: u64,
    granularity: u64,
    used: u64,
}

impl Zone {
    /// Construct a zone whose usable capacity can be smaller than its size.
    /// Invalid alignment, geometry or address overflow returns `None`.
    ///
    /// ```
    /// use topic_072_storage_layout::Zone;
    /// let mut z = Zone::new(0, 256, 240, 4).unwrap();
    /// assert_eq!(z.append(236), Some(0));
    /// assert_eq!(z.append(8), None);
    /// assert_eq!(z.append(4), Some(236));
    /// ```
    pub fn new(start: u64, size: u64, capacity: u64, granularity: u64) -> Option<Self> {
        if granularity == 0
            || capacity == 0
            || capacity > size
            || !start.is_multiple_of(granularity)
            || !size.is_multiple_of(granularity)
            || !capacity.is_multiple_of(granularity)
        {
            return None;
        }
        start.checked_add(size)?;
        Some(Self {
            start,
            capacity,
            granularity,
            used: 0,
        })
    }

    /// Reserve one aligned, nonempty sequential write and return its byte offset.
    /// Failure leaves the cursor unchanged. This models a successful operation;
    /// real submission failure must reconcile device state before another write.
    pub fn append(&mut self, bytes: u64) -> Option<u64> {
        if bytes == 0 || !bytes.is_multiple_of(self.granularity) {
            return None;
        }
        let next = self.used.checked_add(bytes)?;
        if next > self.capacity {
            return None;
        }
        let result = self.start + self.used;
        self.used = next;
        Some(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn write_list_matches_byte_oracle() {
        for len in [0, 1, 4095, 4096, 4097, 65553, 270337] {
            for pattern in [
                Pattern::Empty,
                Pattern::Dense,
                Pattern::Scattered,
                Pattern::Clustered,
            ] {
                let mut bytes = vec![0; len as usize];
                for off in offsets(len, pattern) {
                    bytes[off as usize..(off + BLOCK).min(len) as usize].fill(91);
                }
                for (pos, &byte) in bytes.iter().enumerate() {
                    assert_eq!(byte, expected_byte(pos as u64, len, pattern, 91));
                }
            }
        }
    }
    #[test]
    fn capacity_tail_is_not_writable() {
        let mut zone = Zone::new(256, 256, 240, 4).unwrap();
        assert_eq!(zone.append(236), Some(256));
        let before = zone;
        assert_eq!(zone.append(8), None);
        assert_eq!(zone, before);
        assert_eq!(zone.append(4), Some(492));
        assert_eq!(zone.append(4), None);
    }
    #[test]
    fn invalid_geometry_and_writes() {
        for args in [
            (0, 256, 240, 0),
            (0, 240, 256, 4),
            (1, 256, 240, 4),
            (0, 256, 239, 4),
            (u64::MAX - 3, 8, 4, 4),
        ] {
            assert!(Zone::new(args.0, args.1, args.2, args.3).is_none());
        }
        let mut zone = Zone::new(0, 256, 240, 4).unwrap();
        assert_eq!(zone.append(0), None);
        assert_eq!(zone.append(3), None);
        assert_eq!(zone.append(u64::MAX), None);
        assert_eq!(zone.append(4), Some(0));
    }
}
