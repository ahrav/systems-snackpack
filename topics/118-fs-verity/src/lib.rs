//! Logical hash-block addresses for the 4 KiB, SHA-256 fs-verity layout.
//! The level number starts at zero above the data. See the Python example
//! for authenticated content reads and the expected digest.

/// Return the hash blocks from the leaf to the top for a valid data index.
///
/// Empty files and out-of-range indices have no readable data block.
/// A one-block file has a valid data index and an empty proof path.
///
/// ```
/// use topic118_fs_verity::proof_path;
/// assert_eq!(proof_path(64 << 20, 129), Some(vec![(0, 1), (1, 0)]));
/// ```
pub fn proof_path(file_size: u64, index: u64) -> Option<Vec<(u32, u64)>> {
    let mut count = file_size.div_ceil(4096);
    if index >= count {
        return None;
    }
    let mut path = Vec::new();
    let mut node = index;
    while count > 1 {
        node /= 128;
        path.push((path.len() as u32, node));
        count = count.div_ceil(128);
    }
    Some(path)
}

#[cfg(test)]
mod tests {
    use super::proof_path;

    #[test]
    fn covers_empty_partial_and_exact_levels() {
        assert_eq!(proof_path(0, 0), None);
        assert_eq!(proof_path(1, 0), Some(vec![]));
        assert_eq!(proof_path(4096, 1), None);
        assert_eq!(proof_path(128 * 4096, 127), Some(vec![(0, 0)]));
        assert_eq!(proof_path(128 * 4096 + 1, 128), Some(vec![(0, 1), (1, 0)]));
    }

    #[test]
    fn largest_length_has_a_top_block() {
        let last = (u64::MAX - 1) / 4096;
        let path = proof_path(u64::MAX, last).unwrap();
        assert_eq!(path.last(), Some(&(7, 0)));
        assert_eq!(proof_path(u64::MAX, last + 1), None);
    }
}
