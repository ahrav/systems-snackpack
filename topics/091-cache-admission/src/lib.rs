//! Bounded integer-key cache policy experiment with exact frequency history.
//!
//! ```
//! use cache_admission::{Cache, Policy};
//! let mut cache = Cache::new(2, 4, Policy::Lru, 8);
//! assert!(!cache.access(0));
//! assert!(cache.access(0));
//! assert_eq!(cache.residents(), vec![0]);
//! ```

const NONE: usize = usize::MAX;

/// Admission and resident-order combinations used in the experiment.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Policy {
    /// Admit every miss; hits preserve insertion order.
    Fifo,
    /// Admit every miss; hits update access order.
    Lru,
    /// Admit only when the candidate count exceeds the LRU victim count.
    Frequency,
    /// Frequency admission with periodic integer halving of all counts.
    Aged,
}

impl Policy {
    /// Parse a command-line policy name.
    pub fn parse(name: &str) -> Self {
        match name {
            "fifo" => Self::Fifo,
            "lru" => Self::Lru,
            "frequency" => Self::Frequency,
            "aged" => Self::Aged,
            _ => panic!("unknown policy: {name}"),
        }
    }
}

/// One owner, fixed key universe, hard entry capacity, no stored payloads.
pub struct Cache {
    capacity: usize,
    policy: Policy,
    interval: usize,
    epoch_requests: usize,
    present: Vec<bool>,
    previous: Vec<usize>,
    next: Vec<usize>,
    frequency: Vec<u16>,
    head: usize,
    tail: usize,
    len: usize,
}

impl Cache {
    /// Allocate policy state. Keys must be below `universe`; interval is positive.
    pub fn new(capacity: usize, universe: usize, policy: Policy, interval: usize) -> Self {
        assert!(capacity <= universe && interval > 0);
        Self {
            capacity,
            policy,
            interval,
            epoch_requests: 0,
            present: vec![false; universe],
            previous: vec![NONE; universe],
            next: vec![NONE; universe],
            frequency: if matches!(policy, Policy::Frequency | Policy::Aged) {
                vec![0; universe]
            } else {
                Vec::new()
            },
            head: NONE,
            tail: NONE,
            len: 0,
        }
    }

    fn unlink(&mut self, key: usize) {
        let (before, after) = (self.previous[key], self.next[key]);
        if before == NONE {
            self.head = after;
        } else {
            self.next[before] = after;
        }
        if after == NONE {
            self.tail = before;
        } else {
            self.previous[after] = before;
        }
    }

    fn append(&mut self, key: usize) {
        self.previous[key] = self.tail;
        self.next[key] = NONE;
        if self.tail == NONE {
            self.head = key;
        } else {
            self.next[self.tail] = key;
        }
        self.tail = key;
    }

    /// Process one request and return its hit status.
    ///
    /// Every reference, including rejection, increments a saturating count.
    /// Aging occurs before requests W+1, 2W+1, ...; ties retain the resident.
    pub fn access(&mut self, key: usize) -> bool {
        assert!(key < self.present.len());
        if !self.frequency.is_empty() {
            if self.policy == Policy::Aged {
                if self.epoch_requests == self.interval {
                    for count in &mut self.frequency {
                        *count /= 2;
                    }
                    self.epoch_requests = 0;
                }
                self.epoch_requests += 1;
            }
            self.frequency[key] = self.frequency[key].saturating_add(1);
        }
        if self.present[key] {
            if self.policy != Policy::Fifo && self.tail != key {
                self.unlink(key);
                self.append(key);
            }
            return true;
        }
        if self.capacity == 0 {
            return false;
        }
        if self.len == self.capacity {
            let victim = self.head;
            if !self.frequency.is_empty() && self.frequency[key] <= self.frequency[victim] {
                return false;
            }
            self.unlink(victim);
            self.present[victim] = false;
            self.len -= 1;
        }
        self.append(key);
        self.present[key] = true;
        self.len += 1;
        false
    }

    /// Return keys from oldest eviction candidate to newest resident.
    pub fn residents(&self) -> Vec<usize> {
        let mut result = Vec::new();
        let mut key = self.head;
        while key != NONE {
            assert!(result.len() < self.len, "cycle in resident list");
            result.push(key);
            key = self.next[key];
        }
        assert_eq!(result.len(), self.len);
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    // Independent representation: timestamps select victims, no linked state.
    fn oracle(
        trace: &[usize],
        cap: usize,
        policy: Policy,
        interval: usize,
    ) -> (Vec<bool>, Vec<usize>) {
        let mut resident = BTreeMap::new();
        let mut counts = [0_u16; 4];
        let mut hits = Vec::new();
        for (time, &key) in trace.iter().enumerate() {
            if policy == Policy::Aged && time > 0 && time % interval == 0 {
                counts.iter_mut().for_each(|n| *n >>= 1);
            }
            counts[key] = counts[key].saturating_add(1);
            let hit = resident.contains_key(&key);
            hits.push(hit);
            if hit {
                if policy != Policy::Fifo {
                    resident.insert(key, time);
                }
            } else if cap > 0 {
                if resident.len() == cap {
                    let victim = *resident.iter().min_by_key(|(_, t)| *t).unwrap().0;
                    if matches!(policy, Policy::Frequency | Policy::Aged)
                        && counts[key] <= counts[victim]
                    {
                        continue;
                    }
                    resident.remove(&victim);
                }
                resident.insert(key, time);
            }
        }
        let mut order: Vec<_> = resident.into_iter().collect();
        order.sort_by_key(|&(_, time)| time);
        (hits, order.into_iter().map(|(key, _)| key).collect())
    }

    #[test]
    fn exhaustive_sequences_against_timestamp_oracle() {
        for encoded in 0..4_usize.pow(7) {
            let mut n = encoded;
            let trace: Vec<_> = (0..7)
                .map(|_| {
                    let k = n % 4;
                    n /= 4;
                    k
                })
                .collect();
            for cap in 0..=4 {
                for policy in [Policy::Fifo, Policy::Lru, Policy::Frequency, Policy::Aged] {
                    let mut cache = Cache::new(cap, 4, policy, 3);
                    let mut hits = Vec::new();
                    for (i, &key) in trace.iter().enumerate() {
                        hits.push(cache.access(key));
                        let (want_hits, want_order) = oracle(&trace[..=i], cap, policy, 3);
                        assert_eq!(hits, want_hits);
                        assert_eq!(cache.residents(), want_order);
                        assert_eq!(cache.present.iter().filter(|&&v| v).count(), cache.len);
                    }
                }
            }
        }
    }

    #[test]
    fn persistent_counts_saturate_and_rejections_count() {
        let mut cache = Cache::new(1, 2, Policy::Frequency, 4);
        for _ in 0..70_000 {
            cache.access(0);
        }
        for _ in 0..70_000 {
            assert!(!cache.access(1));
        }
        assert_eq!(cache.frequency, vec![u16::MAX; 2]);
        assert_eq!(cache.residents(), vec![0]);
    }

    #[test]
    fn aging_adapts_after_popularity_shift() {
        let mut cache = Cache::new(1, 2, Policy::Aged, 4);
        for _ in 0..64 {
            cache.access(0);
        }
        for _ in 0..64 {
            cache.access(1);
        }
        assert_eq!(cache.residents(), vec![1]);
    }

    #[test]
    #[should_panic]
    fn invalid_key_is_rejected() {
        Cache::new(1, 2, Policy::Lru, 4).access(2);
    }
}
