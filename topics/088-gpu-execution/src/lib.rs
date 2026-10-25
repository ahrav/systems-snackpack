//! Address and ownership models for a CUDA matrix transpose.
//!
//! These CPU models verify mappings, not GPU synchronization or runtime cost.
//! Run `cargo run -p gpu-execution-mechanics --example model` for derived counts.
use std::collections::BTreeSet;

/// Counts aligned 32-byte sectors touched by byte ranges of `width` bytes.
///
/// Each address represents one active lane. Zero-width accesses touch nothing.
/// Panics when an access extends beyond `u64::MAX`.
///
/// ```
/// use gpu_execution_mechanics::sectors;
/// assert_eq!(sectors(&(0..32).map(|x| x * 4).collect::<Vec<_>>(), 4), 4);
/// ```
pub fn sectors(addresses: &[u64], width: u64) -> usize {
    if width == 0 {
        return 0;
    }
    let mut ranges: Vec<(u64, u64)> = addresses
        .iter()
        .map(|&address| {
            let end = address.checked_add(width - 1).expect("address overflow");
            (address / 32, end / 32)
        })
        .collect();
    ranges.sort_unstable();
    let mut count: usize = 0;
    let mut next_uncounted = 0;
    for (first, last) in ranges {
        let first = first.max(next_uncounted);
        if first <= last {
            let run = usize::try_from(last - first + 1).ok();
            count = run
                .and_then(|run| count.checked_add(run))
                .expect("sector count overflow");
            next_uncounted = last + 1;
        }
    }
    count
}

/// Maximum distinct 32-bit words read from any of 32 shared-memory banks.
///
/// Same-word reads broadcast in this scalar model. An empty request returns zero.
/// The result describes address conflicts, not cycles or wider instructions.
pub fn bank_depth(words: &[u64]) -> usize {
    let mut banks: [BTreeSet<u64>; 32] = std::array::from_fn(|_| BTreeSet::new());
    for &word in words {
        banks[(word % 32) as usize].insert(word);
    }
    banks.iter().map(BTreeSet::len).max().unwrap_or(0)
}

fn check_shape(input: &[u32], rows: usize, cols: usize) {
    assert_eq!(rows.checked_mul(cols), Some(input.len()));
}

/// Direct input-major transpose into a separate output buffer.
/// Panics when the dimensions do not match `input.len()` or overflow.
pub fn direct(input: &[u32], rows: usize, cols: usize) -> Vec<u32> {
    check_shape(input, rows, cols);
    if input.is_empty() {
        return Vec::new();
    }
    let mut out = vec![0; input.len()];
    for row in 0..rows {
        for col in 0..cols {
            out[col * rows + row] = input[row * cols + col];
        }
    }
    out
}

/// Simulates the load/barrier/store phases of 32-by-8 CUDA thread blocks.
///
/// `padded` selects a shared pitch of 33 instead of 32. Every valid output
/// must have one owner and consume an initialized shared element. Sequential
/// phases model a completed barrier; they do not test actual CUDA ordering.
/// Panics on a shape mismatch, overflow, missing producer, or duplicate writer.
pub fn tiled(input: &[u32], rows: usize, cols: usize, padded: bool) -> Vec<u32> {
    check_shape(input, rows, cols);
    if input.is_empty() {
        return Vec::new();
    }
    let pitch = 32 + usize::from(padded);
    let mut out = vec![None; input.len()];
    for by in (0..rows).step_by(32) {
        for bx in (0..cols).step_by(32) {
            let mut tile = vec![None; 32 * pitch];
            for ty in 0..8 {
                for tx in 0..32 {
                    for j in (0..32).step_by(8) {
                        if by + ty + j < rows && bx + tx < cols {
                            tile[(ty + j) * pitch + tx] =
                                Some(input[(by + ty + j) * cols + bx + tx]);
                        }
                    }
                }
            }
            for ty in 0..8 {
                for tx in 0..32 {
                    for j in (0..32).step_by(8) {
                        if bx + ty + j < cols && by + tx < rows {
                            let value = tile[tx * pitch + ty + j].expect("missing producer");
                            let dst = &mut out[(bx + ty + j) * rows + by + tx];
                            assert!(dst.replace(value).is_none(), "duplicate writer");
                        }
                    }
                }
            }
        }
    }
    out.into_iter()
        .map(|x| x.expect("missing writer"))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rectangular_oracle() {
        for rows in 0..66 {
            for cols in 0..66 {
                let input: Vec<u32> = (0..rows * cols).map(|i| i as u32 ^ 0xdeadbeef).collect();
                // Output-major indexing is independent of block and tile mapping.
                let expected: Vec<u32> = (0..input.len())
                    .map(|i| input[(i % rows) * cols + i / rows])
                    .collect();
                assert_eq!(direct(&input, rows, cols), expected);
                assert_eq!(tiled(&input, rows, cols, false), expected);
                assert_eq!(tiled(&input, rows, cols, true), expected);
            }
        }
    }

    #[test]
    fn byte_enumeration_oracle() {
        for offset in 0..64 {
            for stride in [0, 1, 4, 8, 16, 33, 4096] {
                for active in [0, 1, 7, 31, 32] {
                    for width in [0, 1, 4, 8, 16] {
                        let addresses: Vec<u64> =
                            (0..active).map(|t| offset + t * stride).collect();
                        let oracle: BTreeSet<u64> = addresses
                            .iter()
                            .flat_map(|a| (0..width).map(move |b| (a + b) / 32))
                            .collect();
                        assert_eq!(sectors(&addresses, width), oracle.len());
                    }
                }
            }
        }
    }

    #[test]
    fn documented_counts() {
        assert_eq!(sectors(&(0..32).map(|t| 4 * t).collect::<Vec<_>>(), 4), 4);
        assert_eq!(
            sectors(&(0..32).map(|t| 4 * (t + 1)).collect::<Vec<_>>(), 4),
            5
        );
        assert_eq!(
            sectors(&(0..32).map(|t| 4096 * t).collect::<Vec<_>>(), 4),
            32
        );
        assert_eq!(bank_depth(&(0..32).map(|t| 32 * t).collect::<Vec<_>>()), 32);
        assert_eq!(bank_depth(&(0..32).map(|t| 33 * t).collect::<Vec<_>>()), 1);
    }

    #[test]
    fn broadcast_and_empty() {
        assert_eq!(bank_depth(&[7; 32]), 1);
        assert_eq!(bank_depth(&[]), 0);
        assert_eq!(bank_depth(&[0, 0, 32, 64, 1]), 3);
        assert_eq!(sectors(&[0; 32], 4), 1);
    }

    #[test]
    fn wide_access_counts_without_enumerating_sectors() {
        // Two disjoint 1 TiB ranges cover 2^36 sectors; memory use stays
        // proportional to the number of addresses.
        assert_eq!(sectors(&[0, 1 << 40], 1 << 40), 1 << 36);
        assert_eq!(sectors(&[1 << 39, 0], 1 << 40), 3 << 34);
    }

    #[test]
    fn zero_dimension_shapes_finish() {
        for (rows, cols) in [(usize::MAX, 0), (0, usize::MAX)] {
            assert!(direct(&[], rows, cols).is_empty());
            assert!(tiled(&[], rows, cols, false).is_empty());
            assert!(tiled(&[], rows, cols, true).is_empty());
        }
    }

    #[test]
    #[should_panic(expected = "address overflow")]
    fn overflow_is_rejected() {
        sectors(&[u64::MAX], 4);
    }

    #[test]
    #[should_panic]
    fn shape_is_checked() {
        tiled(&[1, 2], 2, 2, true);
    }
}
