//! Model a fixed-range snapshot with serialized copy-before-write operations.
//!
//! ```
//! use userfaultfd_snapshot::Snapshot;
//! let mut s = Snapshot::new(vec![10, 20]);
//! s.write(1, 99);
//! assert_eq!(s.finish(), vec![10, 20]);
//! ```

/// One value per populated page; methods represent page-lock critical sections.
pub struct Snapshot {
    live: Vec<u64>,
    saved: Vec<Option<u64>>,
}

impl Snapshot {
    /// Establishes an epoch while application writers are paused.
    pub fn new(live: Vec<u64>) -> Self {
        Self {
            saved: vec![None; live.len()],
            live,
        }
    }

    /// Preserves a page once, then permits writes. Panics for an invalid page.
    pub fn save(&mut self, page: usize) {
        self.saved[page].get_or_insert(self.live[page]);
    }

    /// Models a store after synchronous fault resolution. Panics for an invalid page.
    pub fn write(&mut self, page: usize, value: u64) {
        self.save(page);
        self.live[page] = value;
    }

    /// Copies remaining pages and returns the epoch image.
    pub fn finish(mut self) -> Vec<u64> {
        for page in 0..self.live.len() {
            self.save(page);
        }
        self.saved.into_iter().map(Option::unwrap).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn histories_match_eager_copy_oracle() {
        // The oracle copies the entire image at the epoch, before any operation.
        for mut code in 0usize..6usize.pow(7) {
            let initial = vec![10, 20, 30];
            let oracle = initial.clone();
            let mut s = Snapshot::new(initial);
            for step in 0..7 {
                let op = code % 6;
                code /= 6;
                if op < 3 {
                    s.save(op);
                } else {
                    s.write(op - 3, 100 + step);
                }
            }
            assert_eq!(s.finish(), oracle);
        }
    }

    #[test]
    fn empty_snapshot() {
        assert!(Snapshot::new(vec![]).finish().is_empty());
    }
}
