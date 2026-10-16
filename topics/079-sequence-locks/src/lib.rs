//! Atomic snapshots for a two-field invariant, with measured retry policies.
//!
//! All shared fields use SeqCst to keep the proof in one total order. This is a
//! conservative teaching implementation, not a generic seqlock over arbitrary T.
//! No pointers escape; writers serialize and sequence numbers never wrap.
//!
//! ```
//! use sequence_locks::Snapshot;
//! use std::time::Duration;
//! let s = Snapshot::new();
//! s.publish(7, Duration::ZERO).unwrap();
//! assert_eq!(s.read(Some(8)).value, (7, 14));
//! ```
use std::sync::Mutex;
use std::sync::atomic::{AtomicU64, Ordering::SeqCst};
use std::time::{Duration, Instant};

/// Why one optimistic attempt failed.
#[derive(Debug, PartialEq, Eq)]
pub enum Retry {
    /// A writer was active at the initial sequence load.
    Odd,
    /// The generation changed during the payload copy.
    Changed,
}

/// One completed read, including work discarded before success.
#[derive(Debug, Default)]
pub struct Read {
    /// A coherent count and twice that count.
    pub value: (u64, u64),
    /// Attempts rejected before copying the payload.
    pub odd: u64,
    /// Copies rejected by final sequence validation.
    pub changed: u64,
    /// Whether this operation took the writer mutex.
    pub fallback: bool,
}

/// A flat atomic record; a mutex serializes writers and fallback readers.
pub struct Snapshot {
    writer: Mutex<()>,
    seq: AtomicU64,
    count: AtomicU64,
    total: AtomicU64,
}

impl Default for Snapshot {
    fn default() -> Self {
        Self::new()
    }
}

impl Snapshot {
    /// Start with the stable pair (0, 0).
    pub fn new() -> Self {
        Self {
            writer: Mutex::new(()),
            seq: AtomicU64::new(0),
            count: AtomicU64::new(0),
            total: AtomicU64::new(0),
        }
    }

    /// Publish (count, 2 * count). Reject overflow before making the state odd.
    ///
    /// `hold` injects busy work between stores for the scheduling experiment.
    /// A real update should keep this interval short and contain no callbacks.
    /// Mutex poisoning is surfaced as a panic before starting an update.
    pub fn publish(&self, count: u64, hold: Duration) -> Result<(), &'static str> {
        let total = count.checked_mul(2).ok_or("payload overflow")?;
        let _guard = self.writer.lock().unwrap();
        let even = self.seq.load(SeqCst);
        let next = even.checked_add(2).ok_or("sequence exhausted")?;
        self.seq.store(even + 1, SeqCst);
        self.count.store(count, SeqCst);
        busy_for(hold);
        self.total.store(total, SeqCst);
        self.seq.store(next, SeqCst);
        Ok(())
    }

    /// Copy once. The caller must discard a rejected snapshot without effects.
    pub fn try_read(&self) -> Result<(u64, u64), Retry> {
        let before = self.seq.load(SeqCst);
        if before & 1 != 0 {
            return Err(Retry::Odd);
        }
        let value = (self.count.load(SeqCst), self.total.load(SeqCst));
        if before == self.seq.load(SeqCst) {
            Ok(value)
        } else {
            Err(Retry::Changed)
        }
    }

    /// Retry at most `budget` times, then take the writer mutex.
    ///
    /// `None` retries without a bound. A stopped writer in the odd state can
    /// prevent that call from completing. A finite budget bounds speculation,
    /// not mutex waiting; zero forces the locking path.
    pub fn read(&self, budget: Option<u64>) -> Read {
        let mut out = Read::default();
        while budget.is_none_or(|limit| out.odd + out.changed < limit) {
            match self.try_read() {
                Ok(value) => {
                    out.value = value;
                    return out;
                }
                Err(Retry::Odd) => out.odd += 1,
                Err(Retry::Changed) => out.changed += 1,
            }
            std::hint::spin_loop();
        }
        let _guard = self.writer.lock().unwrap();
        out.value = (self.count.load(SeqCst), self.total.load(SeqCst));
        out.fallback = true;
        out
    }
}

/// Spend at least the requested wall time doing synthetic work.
///
/// Zero skips clock reads. Descheduling can extend a nonzero interval.
pub fn busy_for(duration: Duration) {
    if !duration.is_zero() {
        let start = Instant::now();
        while start.elapsed() < duration {
            std::hint::spin_loop();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sequential_matches_independent_pair_oracle() {
        let s = Snapshot::new();
        for count in 0..100_000 {
            s.publish(count, Duration::ZERO).unwrap();
            assert_eq!(s.try_read(), Ok((count, count + count)));
        }
    }

    #[test]
    fn zero_budget_uses_lock() {
        let s = Snapshot::new();
        s.publish(17, Duration::ZERO).unwrap();
        let r = s.read(Some(0));
        assert!(r.fallback);
        assert_eq!(r.value, (17, 34));
        assert_eq!(r.odd + r.changed, 0);
    }

    #[test]
    fn odd_generation_is_rejected() {
        let s = Snapshot::new();
        s.seq.store(1, SeqCst);
        assert_eq!(s.try_read(), Err(Retry::Odd));
    }

    #[test]
    fn overflow_leaves_previous_snapshot_readable() {
        let s = Snapshot::new();
        assert_eq!(s.publish(u64::MAX, Duration::ZERO), Err("payload overflow"));
        s.seq.store(u64::MAX - 1, SeqCst);
        assert_eq!(s.publish(1, Duration::ZERO), Err("sequence exhausted"));
        assert_eq!(s.read(Some(8)).value, (0, 0));
        assert!(!s.writer.is_poisoned());
    }

    #[test]
    fn concurrent_writers_preserve_invariant() {
        let s = Snapshot::new();
        std::thread::scope(|scope| {
            for parity in 0..2 {
                let s = &s;
                scope.spawn(move || {
                    for n in 0..10_000 {
                        s.publish(n * 2 + parity, Duration::ZERO).unwrap();
                    }
                });
            }
            for budget in [None, Some(8), Some(0)] {
                let s = &s;
                scope.spawn(move || {
                    for _ in 0..20_000 {
                        let r = s.read(budget);
                        assert_eq!(r.value.1, r.value.0 + r.value.0);
                        if let Some(limit) = budget {
                            assert!(r.odd + r.changed <= limit);
                        }
                    }
                });
            }
        });
        assert_eq!(s.seq.load(SeqCst), 40_000);
    }

    #[test]
    fn fallback_waits_for_same_writer_mutex() {
        let s = Snapshot::new();
        let guard = s.writer.lock().unwrap();
        s.seq.store(1, SeqCst);
        let (tx, rx) = std::sync::mpsc::channel();
        std::thread::scope(|scope| {
            let reader = scope.spawn(|| {
                tx.send(()).unwrap();
                s.read(Some(0))
            });
            rx.recv().unwrap();
            s.count.store(9, SeqCst);
            s.total.store(18, SeqCst);
            s.seq.store(2, SeqCst);
            drop(guard);
            let r = reader.join().unwrap();
            assert!(r.fallback);
            assert_eq!(r.value, (9, 18));
        });
    }
}
