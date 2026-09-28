//! Membership and frequency contract models with checked merges.
//!
//! Keys are canonical `u64` values. The deterministic mixer is not a proven
//! independent hash family. This code tests representation and arithmetic
//! contracts; empirical error rates do not establish a probabilistic theorem.
//!
//! ```
//! use topic061_probabilistic_filters::Bloom;
//! let mut filter = Bloom::new(1024, 7, 42);
//! filter.insert(123);
//! assert!(filter.may_contain(123));
//! ```

/// A merge rejected incompatible metadata, or arithmetic would overflow.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// Dimensions or hash seeds differ.
    Incompatible,
    /// A counter or total would exceed `u64::MAX`; no state changed.
    Overflow,
}

fn mix(mut value: u64) -> u64 {
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn position(key: u64, seed: u64, row: usize, width: usize) -> usize {
    (mix(key ^ mix(seed.wrapping_add(row as u64))) % width as u64) as usize
}

/// An insertion-only Bloom model. A positive result needs exact verification.
///
/// No deletion, concurrency, persistence, snapshot publication, or resizing is
/// implemented. Those contracts must be supplied by a real service.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Bloom {
    words: Vec<u64>,
    bits: usize,
    probes: usize,
    seed: u64,
}

impl Bloom {
    /// Creates an empty model. Panics for zero bits or probes.
    pub fn new(bits: usize, probes: usize, seed: u64) -> Self {
        assert!(bits > 0 && probes > 0);
        Self {
            words: vec![0; bits.div_ceil(64)],
            bits,
            probes,
            seed,
        }
    }

    /// Sets the key's bits. Repeated insertion leaves the same state.
    pub fn insert(&mut self, key: u64) {
        for row in 0..self.probes {
            let bit = position(key, self.seed, row, self.bits);
            self.words[bit / 64] |= 1 << (bit % 64);
        }
    }

    /// Returns false only when this model has not received the key.
    #[inline(never)]
    pub fn may_contain(&self, key: u64) -> bool {
        (0..self.probes).all(|row| {
            let bit = position(key, self.seed, row, self.bits);
            self.words[bit / 64] & (1 << (bit % 64)) != 0
        })
    }

    /// Unions compatible state. Rejected merges leave the receiver unchanged.
    pub fn merge(&mut self, other: &Self) -> Result<(), Error> {
        if (self.bits, self.probes, self.seed) != (other.bits, other.probes, other.seed) {
            return Err(Error::Incompatible);
        }
        for (left, right) in self.words.iter_mut().zip(&other.words) {
            *left |= right;
        }
        Ok(())
    }

    /// Counts occupied bits, excluding the unused padding bits.
    pub fn occupied(&self) -> u64 {
        self.words
            .iter()
            .map(|word| u64::from(word.count_ones()))
            .sum()
    }
}

/// An ordinary additive Count-Min model for nonnegative integer updates.
///
/// The upper-bound invariant follows from nonnegative collision contributions,
/// not from the mixer quality. The usual epsilon/delta probability bound is not
/// claimed for this unproved hash family. Merges count event multiplicity.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CountMin {
    counters: Vec<u64>,
    width: usize,
    depth: usize,
    seed: u64,
    total: u64,
}

impl CountMin {
    /// Creates an empty sketch. Panics for zero or overflowing dimensions.
    pub fn new(width: usize, depth: usize, seed: u64) -> Self {
        assert!(width > 0 && depth > 0);
        Self {
            counters: vec![0; width.checked_mul(depth).expect("dimensions")],
            width,
            depth,
            seed,
            total: 0,
        }
    }

    fn index(&self, key: u64, row: usize) -> usize {
        row * self.width + position(key, self.seed, row, self.width)
    }

    /// Adds nonnegative weight. Overflow rejects the entire operation.
    pub fn add(&mut self, key: u64, weight: u64) -> Result<(), Error> {
        let total = self.total.checked_add(weight).ok_or(Error::Overflow)?;
        // Distinct rows never alias a counter. Preflight prevents partial writes.
        for row in 0..self.depth {
            self.counters[self.index(key, row)]
                .checked_add(weight)
                .ok_or(Error::Overflow)?;
        }
        for row in 0..self.depth {
            let index = self.index(key, row);
            self.counters[index] += weight;
        }
        self.total = total;
        Ok(())
    }

    /// Returns an upper bound on this model's ingested frequency for the key.
    #[inline(never)]
    pub fn estimate(&self, key: u64) -> u64 {
        (0..self.depth)
            .map(|row| self.counters[self.index(key, row)])
            .min()
            .unwrap()
    }

    /// Adds compatible event populations, including any overlapping events.
    ///
    /// This operation is not idempotent. Use external snapshot identities or
    /// deltas to prevent duplicate aggregation. Errors leave state unchanged.
    pub fn merge(&mut self, other: &Self) -> Result<(), Error> {
        if (self.width, self.depth, self.seed) != (other.width, other.depth, other.seed) {
            return Err(Error::Incompatible);
        }
        let total = self.total.checked_add(other.total).ok_or(Error::Overflow)?;
        for (left, right) in self.counters.iter().zip(&other.counters) {
            left.checked_add(*right).ok_or(Error::Overflow)?;
        }
        for (left, right) in self.counters.iter_mut().zip(&other.counters) {
            *left += right;
        }
        self.total = total;
        Ok(())
    }

    /// Returns accumulated input weight, including any duplicated merges.
    pub fn total(&self) -> u64 {
        self.total
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inserted_members_survive_and_insert_is_idempotent() {
        let mut filter = Bloom::new(959, 7, 1);
        assert!(!(0..100).any(|key| filter.may_contain(key)));
        for key in 0..100 {
            filter.insert(key);
        }
        let before = filter.clone();
        for key in 0..100 {
            assert!(filter.may_contain(key));
            filter.insert(key);
        }
        assert_eq!(filter, before);
    }

    #[test]
    fn bloom_union_equals_serial_build_and_replay_is_idempotent() {
        let mut a = Bloom::new(959, 7, 2);
        let mut b = a.clone();
        let mut serial = a.clone();
        for key in 0..200 {
            serial.insert(key);
            if key < 100 {
                a.insert(key);
            } else {
                b.insert(key);
            }
        }
        a.merge(&b).unwrap();
        assert_eq!(a, serial);
        a.merge(&b).unwrap();
        assert_eq!(a, serial);
    }

    #[test]
    fn incompatible_bloom_merges_reject_without_mutation() {
        let mut a = Bloom::new(959, 7, 2);
        a.insert(1);
        let before = a.clone();
        for b in [
            Bloom::new(960, 7, 2),
            Bloom::new(959, 8, 2),
            Bloom::new(959, 7, 3),
        ] {
            assert_eq!(a.merge(&b), Err(Error::Incompatible));
            assert_eq!(a, before);
        }
    }

    #[test]
    fn bit_clearing_can_erase_another_key() {
        let mut a = Bloom::new(1, 1, 0);
        a.insert(1);
        a.insert(65);
        a.words[0] = 0;
        assert!(!a.may_contain(65));
    }

    #[test]
    fn count_min_matches_additive_merge_and_never_underestimates() {
        for seed in 0..8 {
            let mut a = CountMin::new(17, 4, seed);
            let mut b = a.clone();
            let mut serial = a.clone();
            for key in 0..200 {
                let weight = key % 7 + 1;
                serial.add(key, weight).unwrap();
                if key % 2 == 0 {
                    a.add(key, weight).unwrap();
                } else {
                    b.add(key, weight).unwrap();
                }
            }
            a.merge(&b).unwrap();
            assert_eq!(a, serial);
            for key in 0..200 {
                let exact = key % 7 + 1;
                assert!(a.estimate(key) >= exact);
            }
        }
    }

    #[test]
    fn snapshot_replay_counts_events_twice() {
        let mut a = CountMin::new(1, 1, 0);
        let mut b = a.clone();
        a.add(1, 3).unwrap();
        b.add(1, 5).unwrap();
        a.merge(&b).unwrap();
        assert_eq!(a.estimate(1), 8);
        a.merge(&b).unwrap();
        assert_eq!(a.estimate(1), 13);
        assert_eq!(a.total(), 13);
    }

    #[test]
    fn incompatible_count_min_merges_reject_without_mutation() {
        let mut a = CountMin::new(17, 4, 2);
        a.add(1, 9).unwrap();
        let before = a.clone();
        for b in [
            CountMin::new(18, 4, 2),
            CountMin::new(17, 5, 2),
            CountMin::new(17, 4, 3),
        ] {
            assert_eq!(a.merge(&b), Err(Error::Incompatible));
            assert_eq!(a, before);
        }
    }

    #[test]
    fn add_and_merge_overflow_are_transactional() {
        let mut a = CountMin::new(2, 3, 0);
        a.add(1, u64::MAX).unwrap();
        let before = a.clone();
        assert_eq!(a.add(2, 1), Err(Error::Overflow));
        assert_eq!(a, before);
        let mut b = CountMin::new(2, 3, 0);
        b.add(2, 1).unwrap();
        assert_eq!(a.merge(&b), Err(Error::Overflow));
        assert_eq!(a, before);
        a.add(2, 0).unwrap();
        assert_eq!(a, before);
    }

    #[test]
    fn arbitrary_negative_counts_and_saturation_break_upper_bounds() {
        let true_a = 5i64;
        let invalid_b = -3i64;
        assert!(true_a + invalid_b < true_a);
        let saturated = 250u8.saturating_add(10);
        assert!(u16::from(saturated) < 260);
    }

    #[test]
    fn max_union_is_idempotent_but_does_not_retain_runner_up() {
        let a = [2u8, 7, 0];
        let b = [4u8, 3, 1];
        let merged = std::array::from_fn::<_, 3, _>(|i| a[i].max(b[i]));
        assert_eq!(merged, [4, 7, 1]);
        assert_eq!(
            std::array::from_fn::<_, 3, _>(|i| merged[i].max(b[i])),
            merged
        );
        // Both histories yield max 7; removing 7 would need different answers.
        let history_a = [7u8, 2];
        let history_b = [7u8, 4];
        assert_eq!(history_a.iter().max(), history_b.iter().max());
        assert_ne!(history_a[1], history_b[1]);
    }
}
