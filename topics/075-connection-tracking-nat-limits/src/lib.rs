//! Deterministic translated-port allocation model, not a Linux NAT implementation.
//!
//! Each destination is a distinct (remote address, remote port, protocol) domain.
//! One public address and identical port ranges are assumed. Expiry is an explicit
//! release event; there is no packet processing, timeout engine, or concurrency.
//!
//! ```
//! use connection_tracking_nat_limits::{Allocator, Kind};
//! let mut ports = Allocator::new(Kind::Bitmap, 2, 2, 3);
//! assert_eq!(ports.allocate(0), Some(0));
//! assert_eq!(ports.allocate(1), Some(0)); // same port, different destination
//! assert_eq!(ports.allocate(0), Some(1));
//! assert_eq!(ports.allocate(1), None); // global flow limit
//! assert!(ports.release(0, 0));
//! assert_eq!(ports.allocate(1), Some(1));
//! ```
use std::collections::BTreeSet;

/// Candidate representation of free translated ports.
#[derive(Clone, Copy, Debug)]
pub enum Kind {
    /// Scan one byte per port from the beginning.
    Scan,
    /// Scan 64-bit free-bit words, then find the lowest free bit.
    Bitmap,
    /// Maintain an ordered tree of free port numbers.
    Tree,
}
enum Pool {
    Scan(Vec<u8>),
    Bitmap(Vec<u64>),
    Tree(BTreeSet<usize>),
}
/// Single-threaded state with one independent pool per destination.
pub struct Allocator {
    pools: Vec<Pool>,
    ports: usize,
    limit: usize,
    live: usize,
}
impl Allocator {
    /// Build empty pools. Panics for zero destinations/ports or ports above 65536.
    /// A zero global flow limit is valid and rejects all allocations.
    pub fn new(kind: Kind, destinations: usize, ports: usize, limit: usize) -> Self {
        assert!(destinations > 0 && (1..=65536).contains(&ports));
        let pools = (0..destinations)
            .map(|_| match kind {
                Kind::Scan => Pool::Scan(vec![1; ports]),
                Kind::Bitmap => {
                    let mut bits = vec![u64::MAX; ports.div_ceil(64)];
                    if !ports.is_multiple_of(64) {
                        *bits.last_mut().unwrap() = (1u64 << (ports % 64)) - 1;
                    }
                    Pool::Bitmap(bits)
                }
                Kind::Tree => Pool::Tree((0..ports).collect()),
            })
            .collect();
        Self {
            pools,
            ports,
            limit,
            live: 0,
        }
    }
    /// Allocate the lowest free port. Returns None for an invalid destination,
    /// exhausted destination pool, or full global connection table.
    pub fn allocate(&mut self, destination: usize) -> Option<usize> {
        if self.live >= self.limit {
            return None;
        }
        let port = match self.pools.get_mut(destination)? {
            Pool::Scan(free) => {
                let port = free.iter().position(|&x| x != 0)?;
                free[port] = 0;
                port
            }
            Pool::Bitmap(words) => {
                let (word, bits) = words.iter_mut().enumerate().find(|(_, x)| **x != 0)?;
                let bit = bits.trailing_zeros() as usize;
                *bits &= *bits - 1;
                word * 64 + bit
            }
            Pool::Tree(free) => free.pop_first()?,
        };
        self.live += 1;
        Some(port)
    }
    /// Release a live port. Invalid or duplicate releases return false.
    pub fn release(&mut self, destination: usize, port: usize) -> bool {
        if port >= self.ports {
            return false;
        }
        let Some(pool) = self.pools.get_mut(destination) else {
            return false;
        };
        let was_live = match pool {
            Pool::Scan(free) => {
                let used = free[port] == 0;
                free[port] = 1;
                used
            }
            Pool::Bitmap(words) => {
                let mask = 1u64 << (port % 64);
                let used = words[port / 64] & mask == 0;
                words[port / 64] |= mask;
                used
            }
            Pool::Tree(free) => free.insert(port),
        };
        if was_live {
            self.live -= 1;
        }
        was_live
    }
    /// Number of live mappings across all destination pools.
    pub fn live(&self) -> usize {
        self.live
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;
    fn check(ports: usize, limit: usize, actions: &[usize]) {
        let mut expected = HashSet::new();
        let mut candidates =
            [Kind::Scan, Kind::Bitmap, Kind::Tree].map(|k| Allocator::new(k, 2, ports, limit));
        for &action in actions {
            let d = action % 2;
            if action < 2 {
                let p = if expected.len() >= limit {
                    None
                } else {
                    (0..ports).find(|p| !expected.contains(&(d, *p)))
                };
                if let Some(p) = p {
                    expected.insert((d, p));
                }
                for candidate in &mut candidates {
                    assert_eq!(candidate.allocate(d), p);
                }
            } else {
                let p = (action - 2) / 2;
                let existed = expected.remove(&(d, p));
                for candidate in &mut candidates {
                    assert_eq!(candidate.release(d, p), existed);
                }
            }
            for candidate in &candidates {
                assert_eq!(candidate.live(), expected.len());
            }
        }
    }
    #[test]
    fn exhaustive_event_streams() {
        for limit in [0, 1, 3, 4] {
            for mut code in 0usize..6usize.pow(6) {
                let actions = std::array::from_fn::<_, 6, _>(|_| {
                    let a = code % 6;
                    code /= 6;
                    a
                });
                check(2, limit, &actions);
            }
        }
    }
    #[test]
    fn word_edges_and_exhaustion() {
        for ports in [1, 63, 64, 65, 4096] {
            for kind in [Kind::Scan, Kind::Bitmap, Kind::Tree] {
                let mut a = Allocator::new(kind, 2, ports, ports * 2);
                for d in 0..2 {
                    for p in 0..ports {
                        assert_eq!(a.allocate(d), Some(p));
                    }
                    assert_eq!(a.allocate(d), None);
                }
                assert!(!a.release(2, 0));
                assert!(!a.release(0, ports));
                assert!(a.release(0, ports - 1));
                assert!(!a.release(0, ports - 1));
                assert_eq!(a.allocate(0), Some(ports - 1));
                assert_eq!(a.allocate(2), None);
            }
        }
    }
    #[test]
    fn global_capacity_is_separate() {
        check(65, 2, &[0, 1, 0, 1, 2, 1, 1]);
    }
}
