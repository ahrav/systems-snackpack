//! Deterministic placement and movement accounting, not a migration protocol.
//!
//! ```
//! use consistent_hashing_movement::{Map, mix};
//! let old = Map::new("hrw", &[0, 1, 2]);
//! let new = Map::new("hrw", &[0, 1, 2, 3]);
//! for key in 0..1000 {
//!     let h = mix(key);
//!     assert!(old.owner(h) == new.owner(h) || new.owner(h) == 3);
//! }
//! ```

/// Fixed noncryptographic permutation for this experiment. Not hostile-input protection.
pub fn mix(mut x: u64) -> u64 {
    x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

/// Immutable map. Node IDs, seed, algorithm, and token count form its identity.
pub struct Map {
    kind: String,
    nodes: Vec<u64>,
    salts: Vec<u64>,
    tokens: Vec<(u64, u64)>,
}

impl Map {
    /// Build a nonempty map with unique IDs. Panics for invalid input.
    /// `mod` uses list positions; the other schemes preserve stable node IDs.
    pub fn new(kind: &str, nodes: &[u64]) -> Self {
        assert!(!nodes.is_empty());
        assert!(matches!(kind, "mod" | "hrw" | "ring1" | "ring64"));
        let mut unique = nodes.to_vec();
        unique.sort_unstable();
        unique.dedup();
        assert_eq!(unique.len(), nodes.len());
        let salts = nodes
            .iter()
            .map(|n| mix(n.wrapping_add(0x9e3779b97f4a7c15)))
            .collect();
        let mut tokens = Vec::new();
        let v = if kind == "ring64" {
            64
        } else if kind == "ring1" {
            1
        } else {
            0
        };
        for &node in nodes {
            for token in 0..v {
                tokens.push((
                    mix(node.wrapping_mul(0xd6e8feb86659fd93) ^ mix(token + 1)),
                    node,
                ));
            }
        }
        tokens.sort_unstable(); // Equal positions choose the smallest stable node ID.
        Self {
            kind: kind.into(),
            nodes: nodes.to_vec(),
            salts,
            tokens,
        }
    }

    /// Select an owner from an already hashed key. Setup and key hashing are separate.
    pub fn owner(&self, key: u64) -> u64 {
        match self.kind.as_str() {
            "mod" => self.nodes[(key % self.nodes.len() as u64) as usize],
            "hrw" => {
                let mut best = (0, 0);
                for (&node, &salt) in self.nodes.iter().zip(&self.salts) {
                    best = best.max((mix(key ^ salt), node));
                }
                best.1
            }
            _ => {
                let i = self.tokens.partition_point(|p| p.0 < key);
                self.tokens[if i == self.tokens.len() { 0 } else { i }].1
            }
        }
    }

    /// Independently structured oracle: remainder identity, sorting scores, linear successor.
    pub fn oracle(&self, key: u64) -> u64 {
        match self.kind.as_str() {
            "mod" => {
                let n = self.nodes.len() as u64;
                self.nodes[(key - (key / n) * n) as usize]
            }
            "hrw" => {
                let mut scores: Vec<_> = self
                    .nodes
                    .iter()
                    .map(|&n| (mix(key ^ mix(n.wrapping_add(0x9e3779b97f4a7c15))), n))
                    .collect();
                scores.sort_unstable();
                scores.last().unwrap().1
            }
            _ => {
                self.tokens
                    .iter()
                    .filter(|p| p.0 >= key)
                    .min()
                    .unwrap_or_else(|| self.tokens.iter().min().unwrap())
                    .1
            }
        }
    }

    /// Payload capacity in heap vectors, excluding allocator overhead and struct storage.
    pub fn bytes(&self) -> usize {
        self.nodes.capacity() * 8 + self.salts.capacity() * 8 + self.tokens.capacity() * 16
    }
}

/// Check oracles, identity permutation, and strict add/remove movement contracts.
pub fn check() {
    for n in [1, 2, 8, 64, 256] {
        let ids: Vec<_> = (0..n).collect();
        for kind in ["mod", "hrw", "ring1", "ring64"] {
            let a = Map::new(kind, &ids);
            let add = Map::new(kind, &(0..=n).collect::<Vec<_>>());
            let rev = Map::new(kind, &ids.iter().copied().rev().collect::<Vec<_>>());
            let removed = n / 2;
            let del = if n > 1 {
                Some(Map::new(
                    kind,
                    &ids.iter()
                        .copied()
                        .filter(|&x| x != removed)
                        .collect::<Vec<_>>(),
                ))
            } else {
                None
            };
            for h in [0, u64::MAX].into_iter().chain((0..300).map(mix)).chain(
                a.tokens
                    .iter()
                    .step_by((a.tokens.len() / 32).max(1))
                    .map(|p| p.0),
            ) {
                assert_eq!(a.owner(h), a.oracle(h));
                if kind != "mod" {
                    assert_eq!(a.owner(h), rev.owner(h));
                    assert!(a.owner(h) == add.owner(h) || add.owner(h) == n);
                    if let Some(ref d) = del {
                        assert!(a.owner(h) == removed || a.owner(h) == d.owner(h));
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn oracle_and_movement_contracts() {
        check();
    }
    #[test]
    #[should_panic]
    fn empty_is_rejected() {
        Map::new("hrw", &[]);
    }
    #[test]
    #[should_panic]
    fn duplicate_is_rejected() {
        Map::new("ring64", &[1, 1]);
    }
    #[test]
    fn collision_and_wrap_policy() {
        let map = Map {
            kind: "ring1".into(),
            nodes: vec![1, 2, 3],
            salts: vec![],
            tokens: vec![(10, 1), (10, 2), (20, 3)],
        };
        for (key, owner) in [(0, 1), (10, 1), (11, 3), (20, 3), (21, 1), (u64::MAX, 1)] {
            assert_eq!(map.owner(key), owner);
            assert_eq!(map.oracle(key), owner);
        }
        let tied = Map {
            kind: "hrw".into(),
            nodes: vec![1, 2],
            salts: vec![0, 0],
            tokens: vec![],
        };
        assert_eq!(tied.owner(7), 2);
    }
    #[test]
    fn exact_modulo_periods() {
        for n in 1..50_u64 {
            let same = (0..n * (n + 1)).filter(|h| h % n == h % (n + 1)).count();
            assert_eq!(same, n as usize);
        }
    }
}
