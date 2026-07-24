//! Transpose kernels and experiment-contract helpers for cache-layout comparisons.
//!
//! The kernels operate on the active `n` by `n` region of row-major buffers
//! whose physical row width is `leading_dimension`. Keeping those two values
//! separate makes one-element row padding an explicit experiment variable. Each
//! kernel validates storage for `n * leading_dimension` elements before writing,
//! writes only the active region, and leaves row padding unchanged.
//! The set-cycle helpers model simple modulo indexing; they do not claim that a
//! particular CPU exposes those index bits or uses pure modulo placement.

use core::fmt;

/// Maximum number of matrix elements handled by one recursive leaf.
///
/// This fixed value is independent of any cache probe. It gives the practical
/// recursive kernel a bounded base case while preserving recursive subdivision
/// above the leaf.
pub const RECURSIVE_LEAF_ELEMENTS: usize = 1_024;

/// Tile edge passed to [`transpose_tiled`] by the recorded experiment.
pub const RECORDED_TILE_EDGE: usize = 32;

/// Active matrix edge allocated by the recorded experiment.
pub const RECORDED_MATRIX_EDGE: usize = 2_048;

/// Footprint traversed at cache-line intervals before recorded kernel timing.
pub const RECORDED_CONDITION_BYTES: usize = 128 * 1024 * 1024;

/// Cache-line width used for conditioning strides and virtual-alignment reports.
pub const RECORDED_CACHE_LINE_BYTES: usize = 64;

/// Base-page width used to report source and destination virtual offsets.
pub const RECORDED_BASE_PAGE_BYTES: usize = 4_096;

/// Recorded benchmark modes.
pub const RECORDED_MODES: [&str; 6] = [
    "pow2-naive",
    "pow2-tiled",
    "pow2-recursive",
    "padded-naive",
    "padded-tiled",
    "padded-recursive",
];

/// Errors reported before a transpose kernel writes its destination.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransposeError {
    /// The active edge exceeds the physical row width.
    LeadingDimensionTooSmall {
        /// Active square-matrix edge.
        n: usize,
        /// Physical row width.
        leading_dimension: usize,
    },
    /// `n * leading_dimension` overflowed `usize`.
    RequiredLengthOverflow,
    /// The source is shorter than the declared physical layout.
    SourceTooShort {
        /// Required element count.
        required: usize,
        /// Supplied element count.
        supplied: usize,
    },
    /// The destination is shorter than the declared physical layout.
    DestinationTooShort {
        /// Required element count.
        required: usize,
        /// Supplied element count.
        supplied: usize,
    },
    /// A zero-edge tile cannot make progress.
    ZeroTileEdge,
}

impl fmt::Display for TransposeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match *self {
            Self::LeadingDimensionTooSmall {
                n,
                leading_dimension,
            } => write!(
                formatter,
                "leading dimension {leading_dimension} is smaller than active edge {n}"
            ),
            Self::RequiredLengthOverflow => {
                formatter.write_str("matrix storage length overflowed usize")
            }
            Self::SourceTooShort { required, supplied } => write!(
                formatter,
                "source has {supplied} elements but the layout requires {required}"
            ),
            Self::DestinationTooShort { required, supplied } => write!(
                formatter,
                "destination has {supplied} elements but the layout requires {required}"
            ),
            Self::ZeroTileEdge => formatter.write_str("tile edge must be nonzero"),
        }
    }
}

impl std::error::Error for TransposeError {}

fn validate_buffers(
    source: &[u64],
    destination: &[u64],
    n: usize,
    leading_dimension: usize,
) -> Result<(), TransposeError> {
    if leading_dimension < n {
        return Err(TransposeError::LeadingDimensionTooSmall {
            n,
            leading_dimension,
        });
    }
    let required = n
        .checked_mul(leading_dimension)
        .ok_or(TransposeError::RequiredLengthOverflow)?;
    if source.len() < required {
        return Err(TransposeError::SourceTooShort {
            required,
            supplied: source.len(),
        });
    }
    if destination.len() < required {
        return Err(TransposeError::DestinationTooShort {
            required,
            supplied: destination.len(),
        });
    }
    Ok(())
}

/// Transposes the active square with a row-major source traversal.
///
/// Within each inner loop, consecutive source elements are adjacent and
/// consecutive stores are separated by
/// `leading_dimension * size_of::<u64>()` bytes.
///
/// Validation completes before the first destination write.
///
/// # Errors
///
/// Errors are returned in the order listed:
///
/// - `LeadingDimensionTooSmall` if `leading_dimension < n`.
/// - `RequiredLengthOverflow` if `n * leading_dimension` overflows `usize`.
/// - `SourceTooShort` if `source` has fewer than `n * leading_dimension`
///   elements.
/// - `DestinationTooShort` if `destination` has fewer than
///   `n * leading_dimension` elements.
#[inline(never)]
pub fn transpose_naive(
    source: &[u64],
    destination: &mut [u64],
    n: usize,
    leading_dimension: usize,
) -> Result<(), TransposeError> {
    validate_buffers(source, destination, n, leading_dimension)?;
    for row in 0..n {
        let source_row = row * leading_dimension;
        for column in 0..n {
            destination[column * leading_dimension + row] = source[source_row + column];
        }
    }
    Ok(())
}

/// Transposes the active square in explicit square tiles.
///
/// The tile edge is the cache-aware control. Boundary tiles are truncated, so
/// neither the matrix edge nor the leading dimension must be a multiple of it.
///
/// Validation completes before the first destination write.
///
/// # Errors
///
/// Errors are returned in the order listed:
///
/// - `ZeroTileEdge` if `tile_edge == 0`.
/// - `LeadingDimensionTooSmall` if `leading_dimension < n`.
/// - `RequiredLengthOverflow` if `n * leading_dimension` overflows `usize`.
/// - `SourceTooShort` if `source` has fewer than `n * leading_dimension`
///   elements.
/// - `DestinationTooShort` if `destination` has fewer than
///   `n * leading_dimension` elements.
#[inline(never)]
pub fn transpose_tiled(
    source: &[u64],
    destination: &mut [u64],
    n: usize,
    leading_dimension: usize,
    tile_edge: usize,
) -> Result<(), TransposeError> {
    if tile_edge == 0 {
        return Err(TransposeError::ZeroTileEdge);
    }
    validate_buffers(source, destination, n, leading_dimension)?;
    for row_start in (0..n).step_by(tile_edge) {
        let row_end = row_start.saturating_add(tile_edge).min(n);
        for column_start in (0..n).step_by(tile_edge) {
            let column_end = column_start.saturating_add(tile_edge).min(n);
            for row in row_start..row_end {
                let source_row = row * leading_dimension;
                for column in column_start..column_end {
                    destination[column * leading_dimension + row] = source[source_row + column];
                }
            }
        }
    }
    Ok(())
}

/// Transposes the active square by recursively splitting its longer dimension.
///
/// Subdivision stops when a rectangle contains at most
/// [`RECURSIVE_LEAF_ELEMENTS`] elements. That cutoff is fixed in the source and
/// is not derived from a cache-size or line-size probe. This is therefore a
/// practical fixed-cutoff recursive layout traversal, not a proof that the
/// machine satisfies the ideal-cache assumptions used in cache-oblivious
/// analysis.
///
/// Validation completes before the first destination write.
///
/// # Errors
///
/// Errors are returned in the order listed:
///
/// - `LeadingDimensionTooSmall` if `leading_dimension < n`.
/// - `RequiredLengthOverflow` if `n * leading_dimension` overflows `usize`.
/// - `SourceTooShort` if `source` has fewer than `n * leading_dimension`
///   elements.
/// - `DestinationTooShort` if `destination` has fewer than
///   `n * leading_dimension` elements.
#[inline(never)]
pub fn transpose_recursive(
    source: &[u64],
    destination: &mut [u64],
    n: usize,
    leading_dimension: usize,
) -> Result<(), TransposeError> {
    validate_buffers(source, destination, n, leading_dimension)?;
    transpose_recursive_region(source, destination, leading_dimension, 0, n, 0, n);
    Ok(())
}

#[inline(never)]
fn transpose_recursive_region(
    source: &[u64],
    destination: &mut [u64],
    leading_dimension: usize,
    row_start: usize,
    row_end: usize,
    column_start: usize,
    column_end: usize,
) {
    let rows = row_end - row_start;
    let columns = column_end - column_start;
    if rows == 0 || columns == 0 {
        return;
    }
    if rows.saturating_mul(columns) <= RECURSIVE_LEAF_ELEMENTS {
        for row in row_start..row_end {
            let source_row = row * leading_dimension;
            for column in column_start..column_end {
                destination[column * leading_dimension + row] = source[source_row + column];
            }
        }
        return;
    }
    if rows >= columns {
        let middle = row_start + rows / 2;
        transpose_recursive_region(
            source,
            destination,
            leading_dimension,
            row_start,
            middle,
            column_start,
            column_end,
        );
        transpose_recursive_region(
            source,
            destination,
            leading_dimension,
            middle,
            row_end,
            column_start,
            column_end,
        );
    } else {
        let middle = column_start + columns / 2;
        transpose_recursive_region(
            source,
            destination,
            leading_dimension,
            row_start,
            row_end,
            column_start,
            middle,
        );
        transpose_recursive_region(
            source,
            destination,
            leading_dimension,
            row_start,
            row_end,
            middle,
            column_end,
        );
    }
}

const fn greatest_common_divisor(mut left: usize, mut right: usize) -> usize {
    while right != 0 {
        let remainder = left % right;
        left = right;
        right = remainder;
    }
    left
}

/// Returns the set-cycle length for simple modulo cache indexing.
///
/// For `set = line_address mod set_count`, a stream that advances by
/// `stride_lines` visits `set_count / gcd(set_count, stride_lines)` sets before
/// repeating. Returns `None` when `set_count` or `stride_lines` is zero.
///
/// Real caches may hash index bits, use physical bits unavailable to the
/// process, or apply replacement and prefetch policies that this model does not
/// represent.
pub const fn modulo_sets_visited(set_count: usize, stride_lines: usize) -> Option<usize> {
    if set_count == 0 || stride_lines == 0 {
        return None;
    }
    Some(set_count / greatest_common_divisor(set_count, stride_lines))
}

/// Returns the ceiling-average lines per visited set in the modulo model.
///
/// This is a pressure screen, not a miss-rate predictor. It omits alignment,
/// associativity transients, replacement, prefetching, and sharing with other
/// data. Returns `None` when `set_count` or `stride_lines` is zero.
pub const fn average_lines_per_visited_set(
    access_count: usize,
    set_count: usize,
    stride_lines: usize,
) -> Option<usize> {
    let visited = match modulo_sets_visited(set_count, stride_lines) {
        Some(value) => value,
        None => return None,
    };
    Some(access_count.div_ceil(visited))
}

/// Returns the twelve-block process schedule used by the recorded experiment.
///
/// Every block contains each recorded mode once, and every mode occupies each
/// ordinal position exactly twice across the schedule.
pub const fn balanced_schedule() -> [[&'static str; 6]; 12] {
    [
        [
            "pow2-naive",
            "pow2-tiled",
            "pow2-recursive",
            "padded-naive",
            "padded-tiled",
            "padded-recursive",
        ],
        [
            "pow2-tiled",
            "pow2-recursive",
            "padded-naive",
            "padded-tiled",
            "padded-recursive",
            "pow2-naive",
        ],
        [
            "pow2-recursive",
            "padded-naive",
            "padded-tiled",
            "padded-recursive",
            "pow2-naive",
            "pow2-tiled",
        ],
        [
            "padded-naive",
            "padded-tiled",
            "padded-recursive",
            "pow2-naive",
            "pow2-tiled",
            "pow2-recursive",
        ],
        [
            "padded-tiled",
            "padded-recursive",
            "pow2-naive",
            "pow2-tiled",
            "pow2-recursive",
            "padded-naive",
        ],
        [
            "padded-recursive",
            "pow2-naive",
            "pow2-tiled",
            "pow2-recursive",
            "padded-naive",
            "padded-tiled",
        ],
        [
            "padded-recursive",
            "padded-tiled",
            "padded-naive",
            "pow2-recursive",
            "pow2-tiled",
            "pow2-naive",
        ],
        [
            "padded-tiled",
            "padded-naive",
            "pow2-recursive",
            "pow2-tiled",
            "pow2-naive",
            "padded-recursive",
        ],
        [
            "padded-naive",
            "pow2-recursive",
            "pow2-tiled",
            "pow2-naive",
            "padded-recursive",
            "padded-tiled",
        ],
        [
            "pow2-recursive",
            "pow2-tiled",
            "pow2-naive",
            "padded-recursive",
            "padded-tiled",
            "padded-naive",
        ],
        [
            "pow2-tiled",
            "pow2-naive",
            "padded-recursive",
            "padded-tiled",
            "padded-naive",
            "pow2-recursive",
        ],
        [
            "pow2-naive",
            "padded-recursive",
            "padded-tiled",
            "padded-naive",
            "pow2-recursive",
            "pow2-tiled",
        ],
    ]
}

/// Reports whether a schedule contains each recorded mode once per block and
/// twice at every ordinal position.
///
/// Unknown mode names and duplicate or missing modes make the schedule invalid.
pub fn schedule_is_order_balanced(schedule: &[[&str; 6]; 12]) -> bool {
    for mode in RECORDED_MODES {
        for position in 0..6 {
            let count = schedule
                .iter()
                .filter(|block| block[position] == mode)
                .count();
            if count != 2 {
                return false;
            }
        }
        if schedule
            .iter()
            .any(|block| block.iter().filter(|candidate| **candidate == mode).count() != 1)
        {
            return false;
        }
    }
    schedule
        .iter()
        .all(|block| block.iter().all(|mode| RECORDED_MODES.contains(mode)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(n: usize, leading_dimension: usize) -> (Vec<u64>, Vec<u64>) {
        let mut source = vec![u64::MAX; n * leading_dimension];
        for row in 0..n {
            for column in 0..n {
                source[row * leading_dimension + column] =
                    (row as u64) * 131 + (column as u64) * 17 + 7;
            }
        }
        (source, vec![u64::MAX; n * leading_dimension])
    }

    fn assert_transposed(source: &[u64], destination: &[u64], n: usize, ld: usize) {
        for row in 0..n {
            for column in 0..n {
                assert_eq!(
                    destination[column * ld + row],
                    source[row * ld + column],
                    "mismatch at source ({row}, {column})"
                );
            }
        }
        for row in 0..n {
            for column in n..ld {
                assert_eq!(
                    destination[row * ld + column],
                    u64::MAX,
                    "padding overwritten at destination ({row}, {column})"
                );
            }
        }
    }

    #[test]
    fn all_kernels_handle_odd_padded_edges() {
        let n = 257;
        let leading_dimension = 263;
        let (source, mut destination) = fixture(n, leading_dimension);

        transpose_naive(&source, &mut destination, n, leading_dimension).unwrap();
        assert_transposed(&source, &destination, n, leading_dimension);

        destination.fill(u64::MAX);
        transpose_tiled(&source, &mut destination, n, leading_dimension, 31).unwrap();
        assert_transposed(&source, &destination, n, leading_dimension);

        destination.fill(u64::MAX);
        transpose_recursive(&source, &mut destination, n, leading_dimension).unwrap();
        assert_transposed(&source, &destination, n, leading_dimension);
    }

    #[test]
    fn empty_matrix_is_valid() {
        assert_eq!(transpose_naive(&[], &mut [], 0, 0), Ok(()));
        assert_eq!(transpose_tiled(&[], &mut [], 0, 0, 1), Ok(()));
        assert_eq!(transpose_recursive(&[], &mut [], 0, 0), Ok(()));
    }

    #[test]
    fn validation_precedes_destination_writes() {
        let source = vec![1; 8];
        let mut destination = vec![9; 8];
        assert_eq!(
            transpose_naive(&source, &mut destination, 3, 2),
            Err(TransposeError::LeadingDimensionTooSmall {
                n: 3,
                leading_dimension: 2,
            })
        );
        assert_eq!(destination, vec![9; 8]);

        assert_eq!(
            transpose_tiled(&source, &mut destination, 2, 2, 0),
            Err(TransposeError::ZeroTileEdge)
        );
        assert_eq!(destination, vec![9; 8]);
    }

    #[test]
    fn validation_distinguishes_short_buffers() {
        let mut destination = vec![0; 12];
        assert_eq!(
            transpose_recursive(&[0; 11], &mut destination, 3, 4),
            Err(TransposeError::SourceTooShort {
                required: 12,
                supplied: 11,
            })
        );
        assert_eq!(
            transpose_recursive(&[0; 12], &mut destination[..11], 3, 4),
            Err(TransposeError::DestinationTooShort {
                required: 12,
                supplied: 11,
            })
        );
    }

    #[test]
    fn modulo_cycle_exposes_power_of_two_collapse() {
        assert_eq!(modulo_sets_visited(64, 64), Some(1));
        assert_eq!(modulo_sets_visited(64, 65), Some(64));
        assert_eq!(modulo_sets_visited(96, 18), Some(16));
        assert_eq!(modulo_sets_visited(0, 1), None);
        assert_eq!(modulo_sets_visited(64, 0), None);
        assert_eq!(average_lines_per_visited_set(31, 64, 64), Some(31));
        assert_eq!(average_lines_per_visited_set(31, 64, 65), Some(1));
    }

    #[test]
    fn recorded_schedule_is_complete_and_balanced() {
        assert!(schedule_is_order_balanced(&balanced_schedule()));
    }

    #[test]
    fn schedule_validator_rejects_duplicate_mode() {
        let mut schedule = balanced_schedule();
        schedule[0][0] = schedule[0][1];
        assert!(!schedule_is_order_balanced(&schedule));
    }
}
