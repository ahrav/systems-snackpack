//! Compare bounded integer-job handoff with an array queue and a mutex deque.
//!
//! Both variants preserve rejected values and retry by yielding. Consumers take
//! fixed quotas; the caller joins all participants before destroying the queue.
//! Allocation and thread creation precede the start barrier. Timing includes
//! barrier release, transfer, consumer vector writes, and joins. Exact delivery
//! and single-consumer per-producer order are checked after timing.
//!
//! ```
//! use bounded_mpmc_queue::{Mode, transfer};
//! let result = transfer(Mode::Array, 4, 2, 2, 100);
//! assert_eq!(result.jobs, 200);
//! ```

use crossbeam_queue::ArrayQueue;
use std::collections::VecDeque;
use std::sync::{Barrier, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// Queue implementation, with a shared reject-on-full capacity contract.
#[derive(Clone, Copy, Debug)]
pub enum Mode {
    /// Crossbeam 0.3.12's fixed-capacity array implementation.
    Array,
    /// Standard mutex around a deque with an explicit logical capacity.
    Mutex,
}

enum Queue {
    Array(Box<ArrayQueue<usize>>),
    Mutex {
        values: Mutex<VecDeque<usize>>,
        capacity: usize,
    },
}
impl Queue {
    fn new(mode: Mode, capacity: usize) -> Self {
        assert!(capacity > 0);
        match mode {
            Mode::Array => Self::Array(Box::new(ArrayQueue::new(capacity))),
            Mode::Mutex => Self::Mutex {
                values: Mutex::new(VecDeque::with_capacity(capacity)),
                capacity,
            },
        }
    }
    fn push(&self, value: usize) -> Result<(), usize> {
        match self {
            Self::Array(q) => q.push(value),
            Self::Mutex { values, capacity } => {
                let mut q = values.lock().unwrap();
                if q.len() == *capacity {
                    Err(value)
                } else {
                    q.push_back(value);
                    Ok(())
                }
            }
        }
    }
    fn pop(&self) -> Option<usize> {
        match self {
            Self::Array(q) => q.pop(),
            Self::Mutex { values, .. } => values.lock().unwrap().pop_front(),
        }
    }
}

/// Observations from one process. Retry counts exclude library-internal retries.
#[derive(Debug)]
pub struct Report {
    /// Wall time from start-barrier release through participant joins.
    pub elapsed: Duration,
    /// Number of integer jobs verified against the exact expected ID sequence.
    pub jobs: usize,
    /// Returned full or empty observations, each followed by an outer yield.
    pub retries: usize,
}

fn exact_delivery(mut values: Vec<usize>, total: usize) -> bool {
    values.sort_unstable();
    values.len() == total && values.into_iter().eq(0..total)
}

/// Transfer disjoint producer ID ranges, then verify every expected ID once.
///
/// `per_producer * producers` must divide evenly among nonzero consumers.
/// Fixed consumer quotas avoid a shared completion counter in the timed loop.
/// Each consumer preallocates its result buffer before either barrier.
/// This finite saturated batch has no deadlines, parking wrapper, or cancellation.
///
/// # Panics
/// Panics for zero counts/capacity, count overflow, indivisible quotas, a worker
/// panic, or incorrect delivery. An implementation stall needs an external timeout.
pub fn transfer(
    mode: Mode,
    capacity: usize,
    producers: usize,
    consumers: usize,
    per_producer: usize,
) -> Report {
    assert!(producers > 0 && consumers > 0 && per_producer > 0);
    let total = producers.checked_mul(per_producer).unwrap();
    assert_eq!(total % consumers, 0);
    let quota = total / consumers;
    let q = Queue::new(mode, capacity);
    let participants = producers
        .checked_add(consumers)
        .and_then(|workers| workers.checked_add(1))
        .unwrap();
    let ready = Barrier::new(participants);
    let start = Barrier::new(participants);
    let (elapsed, retries, received) = thread::scope(|scope| {
        let mut senders = Vec::new();
        let mut receivers = Vec::new();
        for producer in 0..producers {
            let (q, ready, start) = (&q, &ready, &start);
            senders.push(scope.spawn(move || {
                ready.wait();
                start.wait();
                let mut retries = 0;
                for id in producer * per_producer..(producer + 1) * per_producer {
                    while q.push(id).is_err() {
                        retries += 1;
                        thread::yield_now();
                    }
                }
                retries
            }));
        }
        for _ in 0..consumers {
            let (q, ready, start) = (&q, &ready, &start);
            receivers.push(scope.spawn(move || {
                let mut received = Vec::with_capacity(quota);
                ready.wait();
                start.wait();
                let mut retries = 0;
                while received.len() < quota {
                    if let Some(id) = q.pop() {
                        received.push(id);
                    } else {
                        retries += 1;
                        thread::yield_now();
                    }
                }
                (retries, received)
            }));
        }
        ready.wait();
        let begin = Instant::now();
        start.wait();
        let retries: usize = senders.into_iter().map(|h| h.join().unwrap()).sum();
        let received: Vec<_> = receivers.into_iter().map(|h| h.join().unwrap()).collect();
        (begin.elapsed(), retries, received)
    });
    let retries = retries + received.iter().map(|x| x.0).sum::<usize>();
    let received: Vec<_> = received.into_iter().flat_map(|x| x.1).collect();
    if consumers == 1 {
        let mut next = vec![0; producers];
        for &id in &received {
            let producer = id / per_producer;
            assert_eq!(id % per_producer, next[producer]);
            next[producer] += 1;
        }
    }
    assert!(exact_delivery(received, total));
    assert_eq!(q.pop(), None);
    Report {
        elapsed,
        jobs: total,
        retries,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_returns_ownership_and_fifo_wraps() {
        for mode in [Mode::Array, Mode::Mutex] {
            for capacity in [1, 2, 3, 4, 17] {
                let q = Queue::new(mode, capacity);
                for lap in 0..100 {
                    for i in 0..capacity {
                        assert_eq!(q.push(lap * capacity + i), Ok(()));
                    }
                    assert_eq!(q.push(usize::MAX), Err(usize::MAX));
                    for i in 0..capacity {
                        assert_eq!(q.pop(), Some(lap * capacity + i));
                    }
                    assert_eq!(q.pop(), None);
                }
            }
        }
    }

    #[test]
    fn generated_operations_match_deque_oracle() {
        for mode in [Mode::Array, Mode::Mutex] {
            for capacity in [1, 2, 3, 4, 31] {
                let q = Queue::new(mode, capacity);
                let mut oracle = VecDeque::new();
                let mut state = 7_u64;
                for id in 0..20000 {
                    state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
                    if state >> 63 == 0 {
                        let expected = if oracle.len() == capacity {
                            Err(id)
                        } else {
                            oracle.push_back(id);
                            Ok(())
                        };
                        assert_eq!(q.push(id), expected);
                    } else {
                        assert_eq!(q.pop(), oracle.pop_front());
                    }
                }
                while let Some(value) = oracle.pop_front() {
                    assert_eq!(q.pop(), Some(value));
                }
                assert_eq!(q.pop(), None);
            }
        }
    }

    #[test]
    fn concurrent_exact_delivery() {
        for mode in [Mode::Array, Mode::Mutex] {
            for capacity in [1, 4, 1024] {
                assert_eq!(transfer(mode, capacity, 4, 4, 2000).jobs, 8000);
            }
        }
    }

    #[test]
    fn single_consumer_preserves_each_producer_order() {
        for mode in [Mode::Array, Mode::Mutex] {
            transfer(mode, 3, 4, 1, 1000);
        }
    }

    #[test]
    fn oracle_rejects_duplicate_missing_and_out_of_range() {
        assert!(exact_delivery(vec![2, 0, 1], 3));
        assert!(!exact_delivery(vec![0, 0, 2], 3));
        assert!(!exact_delivery(vec![0, 1], 3));
        assert!(!exact_delivery(vec![0, 1, 3], 3));
    }

    #[test]
    #[should_panic]
    fn zero_capacity_rejected() {
        Queue::new(Mode::Mutex, 0);
    }

    #[test]
    #[should_panic]
    fn participant_count_overflow_panics_before_spawning() {
        // producers * per_producer fits in usize; producers + consumers + 1 overflows usize.
        transfer(Mode::Mutex, 1, usize::MAX, 1, 1);
    }
}
