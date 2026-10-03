//! Equivalent row, column, and tiled storage for an immutable eight-field table.
//! All sums wrap modulo 2^64. Tiled capacity is never a logical row count.
//!
//! ```
//! use data_layout_transformations::{Columns, Row};
//! let rows = [Row([1, 2, 3, 4, 5, 6, 7, 8])];
//! assert_eq!(Columns::from_rows(&rows).narrow(), 1);
//! ```

/// One record with eight equally sized integer fields.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Row(pub [u64; 8]);

/// Eight columns with a private, equal-length invariant.
pub struct Columns {
    fields: [Vec<u64>; 8],
}

impl Columns {
    /// Copy every field, preserving row identity and order.
    pub fn from_rows(rows: &[Row]) -> Self {
        let mut fields = std::array::from_fn(|_| Vec::with_capacity(rows.len()));
        for row in rows {
            for (column, value) in fields.iter_mut().zip(row.0) {
                column.push(value);
            }
        }
        Self { fields }
    }
    /// Sum the first field modulo 2^64.
    #[inline(never)]
    pub fn narrow(&self) -> u64 {
        self.fields[0].iter().fold(0u64, |a, &v| a.wrapping_add(v))
    }
    /// Sum all fields modulo 2^64 using column-wise traversal.
    #[inline(never)]
    pub fn wide(&self) -> u64 {
        self.fields
            .iter()
            .flatten()
            .fold(0u64, |a, &v| a.wrapping_add(v))
    }
    /// Recover a row. Panics when `i` is outside the logical length.
    pub fn row(&self, i: usize) -> Row {
        Row(std::array::from_fn(|f| self.fields[f][i]))
    }
    /// Read whole rows in caller order and weight them by visit position.
    /// Panics if any index is outside the logical length.
    #[inline(never)]
    pub fn indexed(&self, order: &[usize]) -> u64 {
        order.iter().enumerate().fold(0u64, |a, (j, &i)| {
            a.wrapping_add(row_sum(self.row(i)).wrapping_mul(j as u64 + 1))
        })
    }
}

/// Sixteen adjacent lanes of each field, with an explicit logical row count.
pub struct Tiles {
    blocks: Vec<[[u64; 16]; 8]>,
    len: usize,
}

impl Tiles {
    /// Copy all fields. Unused final lanes are initialized but are not rows.
    pub fn from_rows(rows: &[Row]) -> Self {
        let mut blocks = vec![[[0; 16]; 8]; rows.len().div_ceil(16)];
        for (i, row) in rows.iter().enumerate() {
            for (f, &value) in row.0.iter().enumerate() {
                blocks[i / 16][f][i % 16] = value;
            }
        }
        Self {
            blocks,
            len: rows.len(),
        }
    }
    /// Sum first-field values for logical rows only, modulo 2^64.
    #[inline(never)]
    pub fn narrow(&self) -> u64 {
        let mut sum = 0u64;
        for (b, block) in self.blocks.iter().enumerate() {
            let live = (self.len - b * 16).min(16);
            for &v in &block[0][..live] {
                sum = sum.wrapping_add(v);
            }
        }
        sum
    }
    /// Sum all fields of logical rows, modulo 2^64.
    #[inline(never)]
    pub fn wide(&self) -> u64 {
        let mut sum = 0u64;
        for (b, block) in self.blocks.iter().enumerate() {
            let live = (self.len - b * 16).min(16);
            for field in block {
                for &v in &field[..live] {
                    sum = sum.wrapping_add(v);
                }
            }
        }
        sum
    }
    /// Recover a row. Panics when `i` is outside the logical length.
    pub fn row(&self, i: usize) -> Row {
        assert!(i < self.len);
        Row(std::array::from_fn(|f| self.blocks[i / 16][f][i % 16]))
    }
    /// Read whole rows in caller order and weight them by visit position.
    /// Panics if any index is outside the logical length.
    #[inline(never)]
    pub fn indexed(&self, order: &[usize]) -> u64 {
        order.iter().enumerate().fold(0u64, |a, (j, &i)| {
            a.wrapping_add(row_sum(self.row(i)).wrapping_mul(j as u64 + 1))
        })
    }
}

fn row_sum(row: Row) -> u64 {
    row.0.iter().fold(0u64, |a, &v| a.wrapping_add(v))
}

/// Row-layout baseline for a first-field scan.
#[inline(never)]
pub fn row_narrow(rows: &[Row]) -> u64 {
    rows.iter().fold(0u64, |a, r| a.wrapping_add(r.0[0]))
}
/// Row-layout baseline for an all-field scan.
#[inline(never)]
pub fn row_wide(rows: &[Row]) -> u64 {
    rows.iter().fold(0u64, |a, &r| a.wrapping_add(row_sum(r)))
}
/// Row-layout baseline for weighted, indexed whole-row reads.
/// Panics if any index is outside the row slice.
#[inline(never)]
pub fn row_indexed(rows: &[Row], order: &[usize]) -> u64 {
    order.iter().enumerate().fold(0u64, |a, (j, &i)| {
        a.wrapping_add(row_sum(rows[i]).wrapping_mul(j as u64 + 1))
    })
}

/// Independent element-wise oracle using wider arithmetic and a visit list.
/// `narrow` selects field zero; `weighted` multiplies each visit by its 1-based position.
/// Panics for an out-of-range visit. Intermediate arithmetic wraps modulo 2^128;
/// its low 64 bits equal the required modulo-2^64 answer.
pub fn oracle(rows: &[Row], visits: &[usize], narrow: bool, weighted: bool) -> u64 {
    let mut sum = 0u128;
    for (j, &i) in visits.iter().enumerate() {
        for f in 0..if narrow { 1 } else { 8 } {
            let weight = if weighted { j as u128 + 1 } else { 1 };
            sum = sum.wrapping_add(u128::from(rows[i].0[f]).wrapping_mul(weight));
        }
    }
    sum as u64
}

/// Deterministic input containing a broad range of integer bit patterns.
pub fn input(n: usize) -> Vec<Row> {
    let mut state = 0x726f_7773_7461_626cu64;
    (0..n)
        .map(|_| {
            Row(std::array::from_fn(|_| {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                state
            }))
        })
        .collect()
}

/// Deterministic Fisher-Yates visit order; generated outside timing.
pub fn permutation(n: usize) -> Vec<usize> {
    let mut result: Vec<_> = (0..n).collect();
    let mut state = 0x1234_5678_9abc_def0u64;
    for i in (1..n).rev() {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        result.swap(i, (state % (i as u64 + 1)) as usize);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    fn check(rows: &[Row]) {
        let c = Columns::from_rows(rows);
        let t = Tiles::from_rows(rows);
        let sequential: Vec<_> = (0..rows.len()).collect();
        let shuffled = permutation(rows.len());
        for (i, &row) in rows.iter().enumerate() {
            assert_eq!(c.row(i), row);
            assert_eq!(t.row(i), row);
        }
        let one = oracle(rows, &sequential, true, false);
        let all = oracle(rows, &sequential, false, false);
        let random = oracle(rows, &shuffled, false, true);
        assert_eq!([row_narrow(rows), c.narrow(), t.narrow()], [one; 3]);
        assert_eq!([row_wide(rows), c.wide(), t.wide()], [all; 3]);
        assert_eq!(
            [
                row_indexed(rows, &shuffled),
                c.indexed(&shuffled),
                t.indexed(&shuffled)
            ],
            [random; 3]
        );
    }
    #[test]
    fn boundaries_and_round_trip() {
        for n in [0, 1, 15, 16, 17, 31, 32, 33, 255, 256, 257, 4096] {
            check(&input(n));
        }
    }
    #[test]
    fn extreme_values() {
        for v in [0, 1, u64::MAX, 1 << 63] {
            check(&vec![Row([v; 8]); 33]);
        }
    }
    #[test]
    fn padding_is_not_a_row() {
        // Unused lanes sit in block 0 for n < 16 and in the tail block otherwise.
        for n in [1, 15, 17, 31] {
            let mut t = Tiles::from_rows(&input(n));
            let narrow = t.narrow();
            let wide = t.wide();
            let last = t.blocks.len() - 1;
            for f in 0..8 {
                for lane in n % 16..16 {
                    t.blocks[last][f][lane] = u64::MAX;
                }
            }
            assert_eq!(t.narrow(), narrow, "n={n}");
            assert_eq!(t.wide(), wide, "n={n}");
        }
    }
    #[test]
    fn duplicate_and_reverse_visits() {
        let rows = input(17);
        let order = [16, 0, 16, 4, 1, 0];
        let c = Columns::from_rows(&rows);
        let t = Tiles::from_rows(&rows);
        let expected = oracle(&rows, &order, false, true);
        assert_eq!(
            [
                row_indexed(&rows, &order),
                c.indexed(&order),
                t.indexed(&order)
            ],
            [expected; 3]
        );
    }
    #[test]
    #[should_panic]
    fn tile_capacity_is_not_length() {
        Tiles::from_rows(&input(17)).row(17);
    }
    #[test]
    #[should_panic]
    fn column_bounds() {
        Columns::from_rows(&input(17)).row(17);
    }
    #[test]
    fn pinned_row_geometry() {
        assert_eq!(std::mem::size_of::<Row>(), 64);
        assert_eq!(std::mem::align_of::<Row>(), std::mem::align_of::<u64>());
    }
    #[test]
    fn permutations_preserve_identity() {
        for n in [0, 1, 17, 4096] {
            let mut p = permutation(n);
            p.sort_unstable();
            assert_eq!(p, (0..n).collect::<Vec<_>>());
        }
    }
}
