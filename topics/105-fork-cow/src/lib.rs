//! Count first writes to shared base pages while one snapshot retains them.
//!
//! ```
//! use fork_cow::SharedPages;
//! let mut pages = SharedPages::new(2, 4096);
//! assert!(pages.write(0));
//! assert!(!pages.write(1));
//! assert!(pages.write(4096));
//! assert_eq!(pages.copied_pages(), 2);
//! ```

/// Base-page model with a fixed mapping and one retained snapshot.
pub struct SharedPages {
    private: Vec<bool>,
    page_size: usize,
    copied: usize,
}

impl SharedPages {
    /// Creates populated shared pages. Panics if `page_size` is zero.
    pub fn new(page_count: usize, page_size: usize) -> Self {
        assert!(page_size > 0);
        Self {
            private: vec![false; page_count],
            page_size,
            copied: 0,
        }
    }

    /// Writes a byte, returning whether its page becomes private.
    ///
    /// Panics if `offset` falls outside the mapping.
    pub fn write(&mut self, offset: usize) -> bool {
        let private = &mut self.private[offset / self.page_size];
        let first = !*private;
        *private = true;
        self.copied += usize::from(first);
        first
    }

    /// Returns the number of distinct pages written since the snapshot began.
    pub fn copied_pages(&self) -> usize {
        self.copied
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    #[test]
    fn exhaustive_byte_history_oracle() {
        // Independent oracle enumerates touched bytes, then groups by page.
        for mut code in 0usize..8usize.pow(5) {
            let mut model = SharedPages::new(4, 2);
            let mut bytes = BTreeSet::new();
            for _ in 0..5 {
                let offset = code % 8;
                code /= 8;
                bytes.insert(offset);
                model.write(offset);
                let expected = (0..4)
                    .filter(|p| bytes.range(p * 2..p * 2 + 2).next().is_some())
                    .count();
                assert_eq!(model.copied_pages(), expected);
            }
        }
    }

    #[test]
    fn packed_scattered_and_repeated() {
        for page_size in [4096, 16384, 65536] {
            let mut packed = SharedPages::new(4096, page_size);
            let mut scattered = SharedPages::new(4096, page_size);
            for _ in 0..8 {
                for i in 0..4096 {
                    packed.write(i);
                    scattered.write(i * page_size);
                }
                assert_eq!(packed.copied_pages(), 1);
                assert_eq!(scattered.copied_pages(), 4096);
            }
        }
        assert_eq!(SharedPages::new(0, 4096).copied_pages(), 0);
    }
}
