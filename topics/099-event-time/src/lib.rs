//! Event-time windows with exclusive frontiers, retained corrections and idle inputs.
//!
//! Integer timestamps are nonnegative. Width is 10 and allowed lateness is configurable.
//! The frontier never decreases; all-idle holds progress. Input commands are serialized.
//! This model assumes unique events, ordered sink replacement and bounded i64 arithmetic.
//!
//! ```
//! use topic099_event_time::Windows;
//! let mut w = Windows::new(5);
//! w.event(0, 2, 5);
//! w.progress(0, 10);
//! w.progress(1, 10);
//! assert_eq!(w.sink.get(&0), Some(&5));
//! ```
use std::collections::BTreeMap;

/// Two-partition, single-key window operator. Public state supports independent checking.
#[derive(Debug)]
pub struct Windows {
    /// Exclusive lower bound on expected future timestamps.
    pub frontier: i64,
    /// Retained sums, keyed by window start.
    pub live: BTreeMap<i64, i64>,
    /// Last emitted replacement total per window.
    pub sink: BTreeMap<i64, i64>,
    /// Number of records routed to the late-data output.
    pub dropped: usize,
    /// Number of replacement writes, including corrections.
    pub writes: usize,
    progress: [i64; 2],
    active: [bool; 2],
    lateness: i64,
}
impl Windows {
    /// Create an operator with two active inputs and nonnegative lateness.
    pub fn new(lateness: i64) -> Self {
        assert!(lateness >= 0);
        Self {
            frontier: -1,
            live: BTreeMap::new(),
            sink: BTreeMap::new(),
            dropped: 0,
            writes: 0,
            progress: [-1; 2],
            active: [true; 2],
            lateness,
        }
    }
    /// Accept a unique sale; arrival resumes its input before classifying lateness.
    /// Panics for an invalid partition, negative timestamp, or overflowing arithmetic.
    pub fn event(&mut self, input: usize, time: i64, amount: i64) {
        assert!(input < 2 && time >= 0);
        self.active[input] = true;
        let start = time / 10 * 10;
        let end = start.checked_add(10).unwrap();
        if self.frontier >= end.checked_add(self.lateness).unwrap() {
            self.dropped += 1;
            return;
        }
        let total = self.live.entry(start).or_default();
        *total = total.checked_add(amount).unwrap();
        if self.frontier >= end {
            self.sink.insert(start, *total);
            self.writes += 1;
        }
    }
    /// Advance an input's exclusive frontier. Stale announcements are ignored.
    pub fn progress(&mut self, input: usize, value: i64) {
        self.progress[input] = self.progress[input].max(value);
        self.active[input] = true;
        self.advance();
    }
    /// Exclude or resume an input; all-idle holds the operator frontier.
    pub fn idle(&mut self, input: usize, idle: bool) {
        self.active[input] = !idle;
        self.advance();
    }
    fn advance(&mut self) {
        let next = (0..2)
            .filter(|&i| self.active[i])
            .map(|i| self.progress[i])
            .min();
        self.frontier = self.frontier.max(next.unwrap_or(self.frontier));
        for (&start, &total) in &self.live {
            let end = start.checked_add(10).unwrap();
            if self.frontier >= end && !self.sink.contains_key(&start) {
                self.sink.insert(start, total);
                self.writes += 1;
            }
        }
        self.live.retain(|&start, _| {
            self.frontier
                < start
                    .checked_add(10)
                    .unwrap()
                    .checked_add(self.lateness)
                    .unwrap()
        });
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn correction_and_cleanup_equality() {
        let mut w = Windows::new(5);
        w.event(0, 2, 5);
        w.event(1, 7, 7);
        w.progress(0, 14);
        w.progress(1, 10);
        assert_eq!(w.sink[&0], 12);
        w.event(1, 8, 3);
        assert_eq!(w.sink[&0], 15);
        w.progress(0, 15);
        w.progress(1, 15);
        assert!(w.live.is_empty());
        w.event(1, 9, 4);
        assert_eq!(w.dropped, 1);
        assert_eq!(w.writes, 2);
    }
    #[test]
    fn idle_resume_and_zero_lateness() {
        let mut w = Windows::new(0);
        w.event(0, 0, 1);
        w.progress(0, 10);
        assert_eq!(w.frontier, -1);
        w.idle(1, true);
        assert_eq!(w.sink[&0], 1);
        assert!(w.live.is_empty());
        w.idle(0, true);
        assert_eq!(w.frontier, 10);
        w.event(1, 1, 9);
        assert_eq!(w.dropped, 1);
        w.progress(1, 2);
        assert_eq!(w.frontier, 10);
    }
}
