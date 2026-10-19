//! A single-owner ready queue for budgeted edge-triggered service.
//!
//! A budget yield retains readiness. Only EAGAIN or retirement removes it.
//! Poll new kernel events after bounded service, even while this queue is busy.
//! Tokens here are fixed indices; a server that recycles slots needs generations.
//!
//! ```
//! use topic082_linux_runtime::{ReadyQueue, Stop};
//! let mut q = ReadyQueue::new(2);
//! q.notify(0);
//! q.notify(0);
//! let token = q.pop().unwrap();
//! q.finish(token, Stop::Budget);
//! assert!(!q.may_block());
//! ```

use std::collections::VecDeque;

/// Why one bounded service visit stopped.
#[derive(Clone, Copy, Debug)]
pub enum Stop {
    /// The work budget expired before EAGAIN; retain the scheduling obligation.
    Budget,
    /// Nonblocking I/O returned EAGAIN; wait for future readiness.
    WouldBlock,
    /// EOF or a terminal error ended this registration.
    Retired,
}

/// Deduplicated FIFO tokens, owned by one event-loop thread.
#[derive(Debug)]
pub struct ReadyQueue {
    fifo: VecDeque<usize>,
    queued: Vec<bool>,
    in_flight: Option<usize>,
}

impl ReadyQueue {
    /// Reserve a fixed token namespace. Notifications must name a valid index.
    pub fn new(tokens: usize) -> Self {
        Self {
            fifo: VecDeque::new(),
            queued: vec![false; tokens],
            in_flight: None,
        }
    }

    /// Merge an event between service visits; duplicate events do not add turns.
    ///
    /// Panics on an invalid token or while a service visit is in flight.
    pub fn notify(&mut self, token: usize) {
        assert!(self.in_flight.is_none());
        if !self.queued[token] {
            self.queued[token] = true;
            self.fifo.push_back(token);
        }
    }

    /// Begin one service visit. Finish it before polling or popping again.
    pub fn pop(&mut self) -> Option<usize> {
        assert!(self.in_flight.is_none());
        let token = self.fifo.pop_front()?;
        self.queued[token] = false;
        self.in_flight = Some(token);
        Some(token)
    }

    /// End the active visit, preserving readiness on a budget yield.
    pub fn finish(&mut self, token: usize, stop: Stop) {
        assert_eq!(self.in_flight, Some(token));
        self.in_flight = None;
        if matches!(stop, Stop::Budget) {
            self.notify(token);
        }
    }

    /// Whether the queue permits a blocking kernel wait.
    ///
    /// The caller must also check deadlines, shutdown, and other local work.
    pub fn may_block(&self) -> bool {
        self.fifo.is_empty() && self.in_flight.is_none()
    }
}

/// Model fixed pipe backlogs with one initial event per nonempty pipe.
///
/// Returns `(token, bytes)` visits. An extra zero-byte visit models EAGAIN.
/// A nonzero budget is required. Byte counts cannot grow during this model.
pub fn drain(mut bytes: Vec<usize>, budget: usize) -> Vec<(usize, usize)> {
    assert!(budget > 0);
    let mut q = ReadyQueue::new(bytes.len());
    for (id, &n) in bytes.iter().enumerate() {
        if n > 0 {
            q.notify(id);
        }
    }
    let mut visits = Vec::new();
    while let Some(id) = q.pop() {
        let n = bytes[id].min(budget);
        bytes[id] -= n;
        visits.push((id, n));
        q.finish(
            id,
            if n == 0 {
                Stop::WouldBlock
            } else {
                Stop::Budget
            },
        );
    }
    visits
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn duplicate_notifications_do_not_add_turns() {
        let mut q = ReadyQueue::new(2);
        q.notify(0);
        q.notify(0);
        q.notify(1);
        assert_eq!(q.pop(), Some(0));
        q.finish(0, Stop::WouldBlock);
        assert_eq!(q.pop(), Some(1));
        q.finish(1, Stop::Retired);
        assert!(q.may_block());
    }

    #[test]
    fn hot_connection_yields_to_cold_and_late_arrival() {
        let mut q = ReadyQueue::new(3);
        q.notify(0);
        q.notify(1);
        assert_eq!(q.pop(), Some(0));
        assert!(!q.may_block());
        q.finish(0, Stop::Budget);
        q.notify(2);
        for expected in [1, 0, 2] {
            assert_eq!(q.pop(), Some(expected));
            q.finish(expected, Stop::WouldBlock);
        }
        assert!(q.may_block());
    }

    #[test]
    fn exact_budget_still_needs_eagain() {
        assert_eq!(drain(vec![4], 4), vec![(0, 4), (0, 0)]);
    }

    #[test]
    fn empty_input_has_no_visits() {
        assert!(drain(vec![0, 0], 1).is_empty());
    }

    #[test]
    #[should_panic]
    fn zero_budget_is_rejected() {
        drain(vec![1], 0);
    }

    #[test]
    #[should_panic]
    fn cannot_block_or_pop_over_active_visit() {
        let mut q = ReadyQueue::new(1);
        q.notify(0);
        q.pop();
        q.pop();
    }
}
