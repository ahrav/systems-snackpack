//! An in-memory page-mapped flash model. No device I/O or durability claim.
//! Each block has an append frontier: invalidation does not make a page writable.
//! One erased block is reserved for copying live pages before erasing a victim.
//!
//! ```
//! use ssd_gc::{Flash, Policy};
//! let mut f = Flash::new(8, 4, 12, Policy::Greedy, 7);
//! for value in 0..100 { f.write(0, value); }
//! assert_eq!(f.read(0), Some(99));
//! f.check();
//! ```

/// Victim selection policy. All policies exclude blocks with no invalid pages.
#[derive(Clone, Copy, Debug)]
pub enum Policy {
    /// First reclaimable block encountered from a rotating block cursor.
    RoundRobin,
    /// Scan every block and select the smallest live-page count.
    Greedy,
    /// Best of four random block probes, with round-robin fallback if none is eligible.
    Sample4,
}

/// Measured model work; excludes allocation, initial fill and warmup after reset.
#[derive(Default, Clone, Copy, Debug)]
pub struct Stats {
    /// Host page writes.
    pub host: u64,
    /// Copied live pages.
    pub copies: u64,
    /// Erased victim blocks.
    pub erases: u64,
    /// Block metadata probes during victim selection.
    pub probes: u64,
}

#[derive(Clone)]
struct Block {
    pages: Vec<Option<(usize, u64)>>,
    used: usize,
    live: usize,
}

/// Single-threaded teaching model with volatile mappings and fixed-size pages.
/// No power-failure recovery, metadata writes, channels, caches or wear leveling.
pub struct Flash {
    blocks: Vec<Block>,
    map: Vec<Option<(usize, usize)>>,
    free: Vec<usize>,
    active: usize,
    cursor: usize,
    policy: Policy,
    random: u64,
    stats: Stats,
}

/// Deterministic generator for replay, not for security or unbiased sampling.
pub fn next_random(state: &mut u64) -> u64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    *state
}

impl Flash {
    /// Allocate a model with at least one reserve block beyond logical capacity.
    /// Panics for zero seed, pages, logical capacity or insufficient reserve.
    pub fn new(blocks: usize, pages: usize, logical: usize, policy: Policy, seed: u64) -> Self {
        assert!(blocks >= 3 && pages > 0 && seed != 0);
        assert!(logical > 0 && logical < (blocks - 1).checked_mul(pages).unwrap());
        Self {
            blocks: vec![
                Block {
                    pages: vec![None; pages],
                    used: 0,
                    live: 0
                };
                blocks
            ],
            map: vec![None; logical],
            free: (1..blocks).rev().collect(),
            active: 0,
            cursor: 0,
            policy,
            random: seed,
            stats: Stats::default(),
        }
    }

    /// Return the last value written to a logical page, or None before its first write.
    pub fn read(&self, logical: usize) -> Option<u64> {
        self.map[logical].map(|(b, p)| self.blocks[b].pages[p].unwrap().1)
    }

    fn eligible(&mut self, b: usize) -> bool {
        self.stats.probes += 1;
        self.blocks[b].used == self.blocks[b].pages.len()
            && self.blocks[b].live < self.blocks[b].used
    }

    fn round_robin(&mut self) -> usize {
        for offset in 0..self.blocks.len() {
            let b = (self.cursor + offset) % self.blocks.len();
            if self.eligible(b) {
                return b;
            }
        }
        panic!("reserve invariant violated");
    }

    fn victim(&mut self) -> usize {
        let mut best = None;
        let attempts = match self.policy {
            Policy::RoundRobin => 0,
            Policy::Greedy => self.blocks.len(),
            Policy::Sample4 => 4,
        };
        for i in 0..attempts {
            let b = match self.policy {
                Policy::Sample4 => {
                    (next_random(&mut self.random) % self.blocks.len() as u64) as usize
                }
                _ => i,
            };
            if self.eligible(b)
                && best.is_none_or(|old: usize| self.blocks[b].live < self.blocks[old].live)
            {
                best = Some(b);
            }
        }
        let b = best.unwrap_or_else(|| self.round_robin());
        self.cursor = (b + 1) % self.blocks.len();
        b
    }

    fn append(&mut self, logical: usize, value: u64) {
        let b = &mut self.blocks[self.active];
        let p = b.used;
        assert!(p < b.pages.len() && b.pages[p].is_none());
        b.pages[p] = Some((logical, value));
        b.used += 1;
        b.live += 1;
        self.map[logical] = Some((self.active, p));
    }

    fn make_room(&mut self) {
        if self.blocks[self.active].used < self.blocks[self.active].pages.len() {
            return;
        }
        if self.free.len() > 1 {
            self.active = self.free.pop().unwrap();
            return;
        }
        let victim = self.victim();
        self.active = self.free.pop().expect("erased reserve");
        for page in 0..self.blocks[victim].used {
            if let Some((logical, value)) = self.blocks[victim].pages[page].take() {
                self.append(logical, value);
                self.stats.copies += 1;
            }
        }
        self.blocks[victim].used = 0;
        self.blocks[victim].live = 0;
        self.free.push(victim);
        self.stats.erases += 1;
    }

    /// Replace one logical page. The old physical slot stays consumed until erase.
    /// Invalidates first only because this volatile model cannot crash mid-write.
    pub fn write(&mut self, logical: usize, value: u64) {
        if let Some((b, p)) = self.map[logical].take() {
            assert_eq!(self.blocks[b].pages[p].take().unwrap().0, logical);
            self.blocks[b].live -= 1;
        }
        self.make_room();
        self.append(logical, value);
        self.stats.host += 1;
    }

    /// Count still-programmable slots, including erased reserves and open frontiers.
    pub fn writable_pages(&self) -> usize {
        self.blocks.iter().map(|b| b.pages.len() - b.used).sum()
    }

    /// Return operation counters.
    pub fn stats(&self) -> Stats {
        self.stats
    }

    /// Reset counters without changing the model state or random generator.
    pub fn reset_stats(&mut self) {
        self.stats = Stats::default();
    }

    /// Check mapping bijection, live counts, frontiers, erased reserves and capacity.
    pub fn check(&self) {
        let mut seen = vec![false; self.map.len()];
        for (b, block) in self.blocks.iter().enumerate() {
            assert!(block.used <= block.pages.len());
            assert_eq!(block.live, block.pages.iter().flatten().count());
            for (p, value) in block.pages.iter().enumerate() {
                if let Some((logical, _)) = value {
                    assert!(p < block.used && !seen[*logical]);
                    seen[*logical] = true;
                    assert_eq!(self.map[*logical], Some((b, p)));
                }
                if p >= block.used {
                    assert!(value.is_none());
                }
            }
        }
        for (logical, location) in self.map.iter().enumerate() {
            assert_eq!(seen[logical], location.is_some());
        }
        assert!(!self.free.is_empty());
        for (i, &b) in self.free.iter().enumerate() {
            assert_ne!(b, self.active);
            assert!(!self.free[..i].contains(&b));
            assert_eq!(self.blocks[b].used, 0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const POLICIES: [Policy; 3] = [Policy::RoundRobin, Policy::Greedy, Policy::Sample4];
    #[test]
    fn exhaustive_short_histories() {
        for policy in POLICIES {
            for mut code in 0..6561usize {
                let mut f = Flash::new(4, 2, 3, policy, 11);
                let mut oracle = [None; 3];
                for value in 0..8 {
                    let key = code % 3;
                    code /= 3;
                    f.write(key, value);
                    oracle[key] = Some(value);
                    f.check();
                    for (key, expected) in oracle.iter().enumerate() {
                        assert_eq!(f.read(key), *expected);
                    }
                }
            }
        }
    }
    #[test]
    fn near_full_repeated_overwrites() {
        for policy in POLICIES {
            let mut f = Flash::new(8, 4, 27, policy, 19);
            let mut oracle = [None; 27];
            for value in 0..5000 {
                let key = if value % 5 == 0 {
                    value as usize % 27
                } else {
                    0
                };
                f.write(key, value);
                oracle[key] = Some(value);
                f.check();
            }
            for (key, expected) in oracle.iter().enumerate() {
                assert_eq!(f.read(key), *expected);
            }
            assert!(f.stats().erases > 0);
        }
    }
    #[test]
    fn invalidation_does_not_reopen_frontier() {
        let mut f = Flash::new(4, 4, 3, Policy::RoundRobin, 1);
        for value in 0..4 {
            f.write(0, value);
        }
        assert_eq!(f.blocks[0].used, 4);
        assert_eq!(f.blocks[0].live, 1);
        f.write(0, 4);
        assert_ne!(f.active, 0);
        f.check();
    }
    #[test]
    #[should_panic]
    fn reserve_is_required() {
        Flash::new(3, 4, 8, Policy::Greedy, 1);
    }
}
