//! Cardinality estimates and duplicate-preserving equality-join counts.
//!
//! Run `cargo run --release -p topic097-query-optimization --example query_probe -- correlated nested 100`.
use std::collections::HashMap;

/// Count every equal pair. Keys are non-null integers; duplicates multiply.
/// The total must fit in `u64`.
///
/// ```
/// use topic097_query_optimization::{nested_count, hash_count};
/// assert_eq!(nested_count(&[1, 1], &[1, 1, 1]), 6);
/// assert_eq!(hash_count(&[1, 1], &[1, 1, 1]), 6);
/// ```
pub fn nested_count(left: &[u32], right: &[u32]) -> u64 {
    left.iter()
        .map(|a| right.iter().filter(|b| a == *b).count() as u64)
        .sum()
}

/// Count equal pairs using a fresh right-side frequency table.
/// Includes allocation, build and table destruction in each call.
/// The total must fit in `u64`; storage is proportional to distinct right keys.
pub fn hash_count(left: &[u32], right: &[u32]) -> u64 {
    if left.is_empty() || right.is_empty() {
        return 0;
    }
    let mut counts = HashMap::<u32, u64>::new();
    for key in right {
        *counts.entry(*key).or_default() += 1;
    }
    left.iter()
        .map(|key| counts.get(key).copied().unwrap_or(0))
        .sum()
}

/// Estimate the count of rows satisfying both equality predicates.
/// Returns (independence estimate, exact joint count), with zero for empty input.
pub fn estimate(rows: &[(u32, u32)]) -> (f64, usize) {
    if rows.is_empty() {
        return (0.0, 0);
    }
    let a = rows.iter().filter(|r| r.0 == 1).count();
    let b = rows.iter().filter(|r| r.1 == 1).count();
    let joint = rows.iter().filter(|r| r.0 == 1 && r.1 == 1).count();
    (a as f64 * b as f64 / rows.len() as f64, joint)
}

/// Choose between two toy cost formulas for finite nonnegative cardinalities.
/// Hash cost is 10*(outer+inner); nested cost is outer*inner.
/// This coefficient is illustrative and is not fitted to the measurements.
pub fn choose(outer: f64, inner: f64) -> &'static str {
    assert!(outer.is_finite() && outer >= 0.0 && inner.is_finite() && inner >= 0.0);
    if outer * inner <= 10.0 * (outer + inner) {
        "nested"
    } else {
        "hash"
    }
}

/// Generate (selected keys, order keys, estimate, actual selected rows).
/// Named datasets share 10,000 customers and 4,096 orders.
/// Independent/correlated/exclusive share uniform marginal distributions.
pub fn workload(mode: &str) -> (Vec<u32>, Vec<u32>, f64, usize) {
    let rows: Vec<_> = (0..10_000_u32)
        .map(|i| {
            let a = if mode == "dense" { i % 2 } else { i % 100 };
            let b = match mode {
                "independent" => i / 100 % 100,
                "correlated" | "dense" => a,
                "exclusive" => (a + 1) % 100,
                _ => panic!("unknown workload"),
            };
            (a, b)
        })
        .collect();
    let (estimated, actual) = estimate(&rows);
    let left = rows
        .iter()
        .enumerate()
        .filter(|(_, r)| r.0 == 1 && r.1 == 1)
        .map(|(i, _)| (i % 1024) as u32)
        .collect();
    let right = (0..4096).map(|i| i % 1024).collect();
    (left, right, estimated, actual)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn correlation_changes_decision() {
        for (mode, count) in [("independent", 1), ("correlated", 100), ("exclusive", 0)] {
            let (_, _, estimate, actual) = workload(mode);
            assert_eq!(estimate, 1.0);
            assert_eq!(actual, count);
            assert_eq!(choose(estimate, 4096.0), "nested");
            assert_eq!(
                choose(actual as f64, 4096.0),
                if count == 100 { "hash" } else { "nested" }
            );
        }
    }
    #[test]
    fn empty_disjoint_duplicates_and_extreme_keys() {
        for (a, b, count) in [
            (vec![], vec![1], 0),
            (vec![1], vec![], 0),
            (vec![1], vec![2], 0),
            (vec![1, 1], vec![1, 1, 1], 6),
            (vec![0, u32::MAX], vec![u32::MAX, 0, 0], 3),
        ] {
            assert_eq!(nested_count(&a, &b), count);
            assert_eq!(hash_count(&a, &b), count);
        }
        assert_eq!(estimate(&[]), (0.0, 0));
    }
}
