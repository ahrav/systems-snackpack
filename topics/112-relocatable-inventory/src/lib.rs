//! Resolve an INV1 selection inside a stable segment. Run `cargo test -p topic112-relocatable-inventory`.
//!
//! ```
//! use topic112_relocatable_inventory::selected;
//! let data = b"INV1\x08\0\0\0\x2a\0\0\0\x07\0\0\0";
//! assert_eq!(selected(data), Some((42, 7)));
//! ```

/// Decode the selected (item ID, quantity) from little-endian bytes.
/// The header and every record occupy eight bytes. A selection names a record start.
/// Returns `None` for an invalid header, partial record, or invalid selection.
pub fn selected(segment: &[u8]) -> Option<(u32, u32)> {
    let (header, records) = segment.split_at_checked(8)?;
    if &header[..4] != b"INV1" || !records.len().is_multiple_of(8) {
        return None;
    }
    let offset = usize::try_from(u32::from_le_bytes(header[4..].try_into().ok()?)).ok()?;
    let relative = offset.checked_sub(header.len())?;
    if !relative.is_multiple_of(8) {
        return None;
    }
    let record = records.get(relative..)?.first_chunk::<8>()?;
    let (id, quantity) = record.split_at(4);
    Some((
        u32::from_le_bytes(id.try_into().ok()?),
        u32::from_le_bytes(quantity.try_into().ok()?),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_positions_recorded_by_an_independent_writer() {
        for count in 0..=8 {
            for trailer in 0..8 {
                for offset in (0..=81u32).chain([u32::MAX - 7, u32::MAX]) {
                    let mut segment = b"INV1".to_vec();
                    segment.extend(offset.to_le_bytes());
                    let mut expected = None;
                    for i in 0..count {
                        let values = (0x1234_5600u32 + i, u32::MAX - i);
                        if segment.len() == offset as usize && trailer == 0 {
                            expected = Some(values);
                        }
                        segment.extend(values.0.to_le_bytes());
                        segment.extend(values.1.to_le_bytes());
                    }
                    segment.resize(segment.len() + trailer, 0);
                    assert_eq!(selected(&segment), expected);
                }
            }
        }
    }

    #[test]
    fn rejects_wrong_version_and_every_short_header() {
        let mut segment = *b"INV2\x08\0\0\0\x2a\0\0\0\x07\0\0\0";
        assert_eq!(selected(&segment), None);
        segment[3] = b'1';
        for size in 0..16 {
            assert_eq!(selected(&segment[..size]), None);
        }
    }
}
