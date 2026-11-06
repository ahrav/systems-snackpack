//! Maintain the bag-join count `sum(A[k] * B[k])` across atomic batches.
//!
//! Counts are bounded by one billion. With at most `usize::MAX` keys on a
//! 64-bit target, the total fits in i128. Updates are consolidated and validated
//! before mutation. Epochs are synchronous; this model has no timestamp history.
//!
//! ```
//! use incremental_computation::{View, Method};
//! let mut v = View::new(vec![2], vec![3]).unwrap();
//! assert_eq!(v.apply(&[(0, 1, -1)], Method::Delta), Ok(6));
//! ```
use std::collections::BTreeMap;

/// Per-key multiplicity limit, checked before any batch takes effect.
pub const MAX_COUNT: i64 = 1_000_000_000;

/// Evaluation method for the same completed snapshot.
#[derive(Clone, Copy, Debug)]
pub enum Method {
    /// Update only keys mentioned by the batch.
    Delta,
    /// Scan both input count arrays after applying the batch.
    Recompute,
}

/// Two bag inputs and their materialized join count.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct View {
    a: Vec<i64>,
    b: Vec<i64>,
    total: i128,
}

impl View {
    /// Construct a view from equal-length count arrays in `0..=MAX_COUNT`.
    pub fn new(a: Vec<i64>, b: Vec<i64>) -> Result<Self, &'static str> {
        if a.len() != b.len() || a.iter().chain(&b).any(|v| !(0..=MAX_COUNT).contains(v)) {
            return Err("invalid counts");
        }
        let total = a
            .iter()
            .zip(&b)
            .map(|(&x, &y)| i128::from(x) * i128::from(y))
            .sum();
        Ok(Self { a, b, total })
    }

    /// Return the completed snapshot's join count.
    pub fn total(&self) -> i128 {
        self.total
    }

    /// Apply `(key, delta_a, delta_b)` updates atomically and return the count.
    ///
    /// Duplicate keys consolidate with checked i64 arithmetic. Invalid keys,
    /// overflow, or completed counts outside `0..=MAX_COUNT` leave state intact.
    /// Within a batch, individual deltas may temporarily imply negative counts.
    pub fn apply(
        &mut self,
        updates: &[(usize, i64, i64)],
        method: Method,
    ) -> Result<i128, &'static str> {
        let mut changes = BTreeMap::<usize, (i64, i64)>::new();
        for &(k, da, db) in updates {
            if k >= self.a.len() {
                return Err("invalid key");
            }
            let entry = changes.entry(k).or_default();
            entry.0 = entry.0.checked_add(da).ok_or("delta overflow")?;
            entry.1 = entry.1.checked_add(db).ok_or("delta overflow")?;
        }
        for (&k, (da, db)) in &mut changes {
            *da = self.a[k].checked_add(*da).ok_or("count overflow")?;
            *db = self.b[k].checked_add(*db).ok_or("count overflow")?;
            if !(0..=MAX_COUNT).contains(da) || !(0..=MAX_COUNT).contains(db) {
                return Err("invalid completed count");
            }
        }
        for (k, (a, b)) in changes {
            if matches!(method, Method::Delta) {
                self.total +=
                    i128::from(a) * i128::from(b) - i128::from(self.a[k]) * i128::from(self.b[k]);
            }
            self.a[k] = a;
            self.b[k] = b;
        }
        if matches!(method, Method::Recompute) {
            self.total = self
                .a
                .iter()
                .zip(&self.b)
                .map(|(&a, &b)| i128::from(a) * i128::from(b))
                .sum();
        }
        Ok(self.total)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn interactions_duplicates_and_cancellation() {
        for m in [Method::Delta, Method::Recompute] {
            let mut v = View::new(vec![2, 0], vec![3, 0]).unwrap();
            assert_eq!(v.apply(&[(0, 1, -1)], m), Ok(6));
            assert_eq!(v.apply(&[(1, -2, 1), (1, 3, 1)], m), Ok(8));
            assert_eq!(v.apply(&[(0, -3, -2), (1, -1, -2)], m), Ok(0));
        }
    }
    #[test]
    fn rejects_without_mutation() {
        for m in [Method::Delta, Method::Recompute] {
            for batch in [
                vec![(0, 1, 0), (1, -1, 0)],
                vec![(2, 1, 1)],
                vec![(0, i64::MAX, 0), (0, 1, 0)],
                vec![(0, MAX_COUNT, 0)],
            ] {
                let mut v = View::new(vec![1, 0], vec![1, 0]).unwrap();
                let old = v.clone();
                assert!(v.apply(&batch, m).is_err());
                assert_eq!(v, old);
            }
        }
    }
    #[test]
    fn empty_and_large_counts() {
        assert_eq!(
            View::new(vec![], vec![]).unwrap().apply(&[], Method::Delta),
            Ok(0)
        );
        let mut v = View::new(vec![MAX_COUNT; 10], vec![MAX_COUNT; 10]).unwrap();
        assert_eq!(v.total(), 10_000_000_000_000_000_000);
        assert_eq!(
            v.apply(&[(0, -1, -1)], Method::Delta),
            Ok(9_999_999_998_000_000_001)
        );
    }
}
