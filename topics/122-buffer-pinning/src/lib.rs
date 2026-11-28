//! A single reusable frame with two logical pages. Each pin preserves identity.
//! Each read or write takes its own content latch.
//!
//! ```
//! use topic122_buffer_pinning::{Page, Pool};
//! let pool = Pool::default();
//! let pin = pool.pin(Page::A).unwrap();
//! assert!(pool.pin(Page::B).is_none());
//! drop(pin);
//! assert_eq!(pool.pin(Page::B).unwrap().read(), 90);
//! ```
use std::sync::{Mutex, RwLock};

/// Logical identities in the example backing store.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Page {
    /// Account page, initially 41.
    A,
    /// Second page, initially 90.
    B,
}

struct Metadata {
    resident: Page,
    pins: usize,
    backing: [u32; 2],
}

/// One frame. Metadata serializes lookup, pin acquisition and reassignment.
pub struct Pool {
    meta: Mutex<Metadata>,
    value: RwLock<u32>,
}

impl Default for Pool {
    fn default() -> Self {
        Self {
            meta: Mutex::new(Metadata {
                resident: Page::A,
                pins: 0,
                backing: [41, 90],
            }),
            value: RwLock::new(41),
        }
    }
}

impl Pool {
    /// Returns a guard or reports that the other page holds the only frame.
    pub fn pin(&self, page: Page) -> Option<Pin<'_>> {
        let mut meta = self.meta.lock().unwrap();
        if page != meta.resident {
            if meta.pins != 0 {
                return None;
            }
            let mut frame = self.value.write().unwrap();
            let old = meta.resident as usize;
            meta.backing[old] = *frame;
            *frame = meta.backing[page as usize];
            meta.resident = page;
        }
        meta.pins += 1;
        Some(Pin { pool: self })
    }
}

/// A non-clonable residency guard. Accessors return owned values.
pub struct Pin<'a> {
    pool: &'a Pool,
}

impl Pin<'_> {
    /// Copies the current value under a shared content latch.
    pub fn read(&self) -> u32 {
        *self.pool.value.read().unwrap()
    }

    /// Replaces the current value under the exclusive content latch.
    pub fn write(&self, value: u32) {
        *self.pool.value.write().unwrap() = value;
    }
}

impl Drop for Pin<'_> {
    fn drop(&mut self) {
        self.pool.meta.lock().unwrap().pins -= 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn another_worker_can_update_a_pinned_page() {
        let pool = Pool::default();
        let reader = pool.pin(Page::A).unwrap();
        assert_eq!(reader.read(), 41);
        std::thread::scope(|s| {
            s.spawn(|| {
                assert!(pool.pin(Page::B).is_none());
                pool.pin(Page::A).unwrap().write(42);
            });
        });
        assert_eq!(reader.read(), 42);
        drop(reader);
        assert_eq!(pool.pin(Page::B).unwrap().read(), 90);
        assert_eq!(pool.pin(Page::A).unwrap().read(), 42);
    }

    #[test]
    fn two_clients_agree_with_logical_page_oracle() {
        // The oracle stores logical pages permanently. Conflicts depend only on
        // the clients' claims. It has no frame, refcount, latch or writeback path.
        for history in 0..100_000_u32 {
            let pool = Pool::default();
            let mut guards = [None, None];
            let mut claims = [None, None];
            let mut values = [41, 90];
            let mut digits = history;
            for step in 0..5 {
                let event = (digits % 10) as usize;
                digits /= 10;
                let who = event / 5;
                match event % 5 {
                    op @ (0 | 1) => {
                        // Each client owns at most one pin.
                        if claims[who].is_none() {
                            let page = [Page::A, Page::B][op];
                            let allowed = claims[1 - who].is_none_or(|other| other == page);
                            let acquired = pool.pin(page);
                            assert_eq!(
                                acquired.is_some(),
                                allowed,
                                "history {history}, step {step}"
                            );
                            guards[who] = acquired;
                            claims[who] = allowed.then_some(page);
                        }
                    }
                    2 => {
                        guards[who] = None;
                        claims[who] = None;
                    }
                    3 => {
                        if let Some(page) = claims[who] {
                            let value = 100 + step;
                            guards[who].as_ref().unwrap().write(value);
                            values[page as usize] = value;
                        }
                    }
                    _ => {
                        let observed = guards[who].as_ref().map(Pin::read);
                        assert_eq!(observed, claims[who].map(|page| values[page as usize]));
                    }
                }
            }
            drop(guards);
            for page in [Page::A, Page::B] {
                assert_eq!(
                    pool.pin(page).unwrap().read(),
                    values[page as usize],
                    "history {history}"
                );
            }
        }
    }
}
