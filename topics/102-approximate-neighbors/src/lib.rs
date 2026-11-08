//! Fixed-centroid IVF with exact integer scoring and stable ID ties.
//!
//! Probing fewer lists can omit the nearest vector. Full probing scans every ID.
//! The Python experiment compares heap-based search configurations and uses an
//! independent SQLite oracle. This Rust companion favors a compact sorted result.
//!
//! ```
//! use approximate_neighbors::Index;
//! let index = Index::new(vec![[0; 4], [51, 0, 0, 0]], vec![[0; 4], [100, 0, 0, 0]]);
//! assert_eq!(index.search([49, 0, 0, 0], 1, 1), vec![(2401, 0)]);
//! assert_eq!(index.search([49, 0, 0, 0], 1, 2), vec![(4, 1)]);
//! ```

/// Immutable four-dimensional integer IVF index.
#[derive(Debug)]
pub struct Index {
    points: Vec<[i32; 4]>,
    centers: Vec<[i32; 4]>,
    lists: Vec<Vec<usize>>,
}

fn distance(a: &[i32; 4], b: &[i32; 4]) -> u128 {
    a.iter()
        .zip(b)
        .map(|(&x, &y)| {
            let delta = i128::from(x) - i128::from(y);
            delta.unsigned_abs().pow(2)
        })
        .sum()
}

impl Index {
    /// Assign every point to its nearest center, breaking center ties by index.
    ///
    /// # Panics
    /// Panics when `centers` is empty.
    pub fn new(points: Vec<[i32; 4]>, centers: Vec<[i32; 4]>) -> Self {
        assert!(!centers.is_empty());
        let mut lists = vec![Vec::new(); centers.len()];
        for (id, point) in points.iter().enumerate() {
            let owner = (0..centers.len())
                .min_by_key(|&c| (distance(point, &centers[c]), c))
                .unwrap();
            lists[owner].push(id);
        }
        Self {
            points,
            centers,
            lists,
        }
    }

    /// Return up to `k` `(squared_distance, ID)` pairs from the selected lists.
    ///
    /// Squared distances use u128 so every possible i32 coordinate is supported.
    /// Empty populations and k=0 return empty results. IDs break distance ties.
    ///
    /// # Panics
    /// Panics unless `probes` is in `1..=centers.len()`.
    pub fn search(&self, query: [i32; 4], k: usize, probes: usize) -> Vec<(u128, usize)> {
        assert!((1..=self.centers.len()).contains(&probes));
        let mut centers: Vec<_> = (0..self.centers.len()).collect();
        centers.sort_unstable_by_key(|&c| (distance(&query, &self.centers[c]), c));
        let mut result: Vec<_> = centers[..probes]
            .iter()
            .flat_map(|&c| self.lists[c].iter())
            .map(|&id| (distance(&query, &self.points[id]), id))
            .collect();
        result.sort_unstable();
        result.truncate(k);
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_ties_and_extreme_coordinates() {
        assert!(
            Index::new(vec![], vec![[0; 4]])
                .search([0; 4], 3, 1)
                .is_empty()
        );
        let index = Index::new(vec![[0; 4]; 3], vec![[0; 4]; 2]);
        assert_eq!(index.search([0; 4], 5, 2), vec![(0, 0), (0, 1), (0, 2)]);
        assert!(index.search([0; 4], 0, 1).is_empty());
        let extreme = Index::new(vec![[i32::MIN; 4]], vec![[0; 4]]);
        assert_eq!(
            extreme.search([i32::MAX; 4], 1, 1),
            vec![(4 * 4_294_967_295_u128.pow(2), 0)]
        );
    }

    #[test]
    fn full_probing_matches_independent_one_dimensional_order() {
        // Absolute distance has the same rank as squared distance. This oracle
        // uses signed i64 subtraction and abs, independently of distance().
        for n in 0..25 {
            let points: Vec<_> = (0..n).map(|i| [i * 7 % 23 - 11, 0, 0, 0]).collect();
            let index = Index::new(points.clone(), vec![[-10, 0, 0, 0], [0; 4], [10, 0, 0, 0]]);
            for q in -15..16 {
                let mut expected: Vec<_> = points
                    .iter()
                    .enumerate()
                    .map(|(id, p)| ((i64::from(p[0]) - i64::from(q)).abs(), id))
                    .collect();
                expected.sort_unstable();
                for k in [0, 1, 5, 30] {
                    let actual = index.search([q, 0, 0, 0], k, 3);
                    assert_eq!(
                        actual.iter().map(|x| x.1).collect::<Vec<_>>(),
                        expected.iter().take(k).map(|x| x.1).collect::<Vec<_>>()
                    );
                }
            }
        }
    }
}
