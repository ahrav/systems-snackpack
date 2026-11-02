//! Compose two translation stages while preserving permissions and fault identity.
//!
//! Each table describes disjoint, aligned toy pages. This model excludes caches,
//! concurrent invalidations, architectural faults, and host residency.
//!
//! ```
//! use topic096_virtualization::cold_reads;
//! assert_eq!(cold_reads(4, 4), 24);
//! ```

/// Translation failure at a named stage.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fault {
    /// Guest page is absent or denies the requested access.
    Guest,
    /// Host stage is absent or denies the requested access.
    Host,
}

/// One present leaf, represented by its output page and write permission.
#[derive(Debug, Clone, Copy)]
pub struct Leaf {
    /// Output page number in this stage's page size.
    pub frame: usize,
    /// Whether writes are permitted.
    pub writable: bool,
}

/// A dense toy page table. A missing leaf faults for reads and writes.
#[derive(Debug)]
pub struct Table {
    /// Log2 of this stage's page size. Must be below usize::BITS.
    pub shift: u32,
    /// Leaves indexed by input page number.
    pub leaves: Vec<Option<Leaf>>,
}

impl Table {
    fn resolve(&self, addr: usize, write: bool) -> Option<usize> {
        let size = 1usize.checked_shl(self.shift)?;
        let leaf = self.leaves.get(addr / size)?.as_ref()?;
        if write && !leaf.writable {
            return None;
        }
        leaf.frame.checked_mul(size)?.checked_add(addr % size)
    }
}

/// Translate an address through the guest and host tables, checking both permissions.
///
/// Invalid table geometry and output overflow are treated as faults at that stage.
pub fn translate(guest: &Table, host: &Table, addr: usize, write: bool) -> Result<usize, Fault> {
    let physical = guest.resolve(addr, write).ok_or(Fault::Guest)?;
    host.resolve(physical, write).ok_or(Fault::Host)
}

/// Count cold translation-entry reads, excluding the final data access.
///
/// Assumes uniform depths, cache misses, resident entries and no interrupted walk.
/// Inputs are bounded to eight-bit depths so the result fits u32.
pub fn cold_reads(guest: u8, host: u8) -> u32 {
    u32::from(guest) * (u32::from(host) + 1) + u32::from(host)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Expanding each page into byte entries gives a separate lookup oracle.
    fn expand(t: &Table, write: bool) -> Vec<Option<usize>> {
        let size = 1 << t.shift;
        let mut bytes = Vec::new();
        for leaf in &t.leaves {
            for offset in 0..size {
                bytes.push(leaf.and_then(|l| {
                    if write && !l.writable {
                        None
                    } else {
                        Some(l.frame * size + offset)
                    }
                }));
            }
        }
        bytes
    }

    #[test]
    fn byte_oracle() {
        let mut comparisons = 0;
        for gs in 0..5 {
            for hs in 0..5 {
                for seed in 0usize..64 {
                    let table = |shift, salt: usize| Table {
                        shift,
                        leaves: (0..16)
                            .map(|i| {
                                let v = i * 13 + seed * 7 + salt;
                                if v.is_multiple_of(5) {
                                    None
                                } else {
                                    Some(Leaf {
                                        frame: v % 16,
                                        writable: !v.is_multiple_of(3),
                                    })
                                }
                            })
                            .collect(),
                    };
                    let guest = table(gs, 0);
                    let host = table(hs, 3);
                    for write in [false, true] {
                        let g = expand(&guest, write);
                        let h = expand(&host, write);
                        for addr in 0..=g.len() + 1 {
                            let expected = g
                                .get(addr)
                                .copied()
                                .flatten()
                                .ok_or(Fault::Guest)
                                .and_then(|a| h.get(a).copied().flatten().ok_or(Fault::Host));
                            assert_eq!(translate(&guest, &host, addr, write), expected);
                            comparisons += 1;
                        }
                    }
                }
            }
        }
        println!("independent byte-oracle comparisons: {comparisons}");
    }

    #[test]
    fn cold_walk_enumeration() {
        for g in 0..=5 {
            for h in 0..=5 {
                let mut accesses = Vec::new();
                for guest_entry in 0..g {
                    for host_entry in 0..h {
                        accesses.push((guest_entry, host_entry));
                    }
                    accesses.push((guest_entry, h));
                }
                for host_entry in 0..h {
                    accesses.push((g, host_entry));
                }
                assert_eq!(cold_reads(g, h) as usize, accesses.len());
            }
        }
    }

    #[test]
    fn malformed_geometry_faults() {
        let bad = Table {
            shift: usize::BITS,
            leaves: vec![Some(Leaf {
                frame: 0,
                writable: true,
            })],
        };
        assert_eq!(translate(&bad, &bad, 0, false), Err(Fault::Guest));
        let overflow = Table {
            shift: 1,
            leaves: vec![Some(Leaf {
                frame: usize::MAX,
                writable: true,
            })],
        };
        assert_eq!(translate(&overflow, &overflow, 0, false), Err(Fault::Guest));
    }
}
