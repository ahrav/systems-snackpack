//! Exhaustive trace search and strict replay for a two-worker lost-update model.
//!
//! This models sequentially consistent transitions, not native threads or weak
//! memory. Each unfinished worker is enabled. There are no crashes or retries.
//! No visited-state reduction is used, so distinct schedules remain distinct.
//!
//! ```
//! use topic060_deterministic_simulation::{search, Mode, Status};
//! let broken = search(Mode::Split, 4);
//! assert_eq!(broken.status, Status::Exhausted);
//! assert_eq!((broken.terminal, broken.failures), (6, 4));
//! let fixed = search(Mode::Atomic, 2);
//! assert_eq!((fixed.terminal, fixed.failures), (2, 0));
//! ```

/// The granularity of one worker transition.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// Read and write are separate transitions, permitting a lost update.
    Split,
    /// One indivisible increment represents a serialized implementation.
    Atomic,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct State {
    value: u8,
    pc: [u8; 2],
    saved: [u8; 2],
}

impl State {
    fn done(self) -> bool {
        self.pc == [2, 2]
    }

    fn step(mut self, mode: Mode, worker: usize) -> Result<Self, &'static str> {
        if worker >= 2 {
            return Err("worker index out of range");
        }
        if self.pc[worker] == 2 {
            return Err("worker already finished");
        }
        match mode {
            Mode::Atomic => {
                self.value += 1;
                self.pc[worker] = 2;
            }
            Mode::Split if self.pc[worker] == 0 => {
                self.saved[worker] = self.value;
                self.pc[worker] = 1;
            }
            Mode::Split => {
                self.value = self.saved[worker] + 1;
                self.pc[worker] = 2;
            }
        }
        Ok(self)
    }
}

/// Whether the finite search finished exploring every schedule.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    /// Every enabled successor was explored through termination.
    Exhausted,
    /// At least one unfinished execution reached the depth limit.
    Cutoff,
}

/// Counts concern schedules and trace-tree edges, not unique model states.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Report {
    /// Search completion status, independent of whether a failure was found.
    pub status: Status,
    /// Number of completed schedules inspected.
    pub terminal: u64,
    /// Number of completed schedules violating the terminal oracle.
    pub failures: u64,
    /// Number of transitions followed in the trace tree.
    pub transitions: u64,
    /// Number of unfinished prefixes stopped by the depth limit.
    pub cutoffs: u64,
    /// First failing schedule in deterministic worker-index search order.
    pub witness: Option<Vec<usize>>,
}

/// Exhaust all two-worker schedules unless `max_depth` cuts off a prefix.
///
/// The bound is the number of model transitions, not elapsed time. A terminal
/// state exactly at the bound is checked before considering a cutoff. Finding
/// a counterexample does not stop this search; all other prefixes are explored.
pub fn search(mode: Mode, max_depth: usize) -> Report {
    fn visit(s: State, mode: Mode, limit: usize, trace: &mut Vec<usize>, r: &mut Report) {
        if s.done() {
            r.terminal += 1;
            if s.value != 2 {
                r.failures += 1;
                if r.witness.is_none() {
                    r.witness = Some(trace.clone());
                }
            }
            return;
        }
        if trace.len() == limit {
            r.cutoffs += 1;
            r.status = Status::Cutoff;
            return;
        }
        for worker in 0..2 {
            if s.pc[worker] != 2 {
                let next = s.step(mode, worker).expect("enabled worker");
                r.transitions += 1;
                trace.push(worker);
                visit(next, mode, limit, trace, r);
                trace.pop();
            }
        }
    }
    let mut report = Report {
        status: Status::Exhausted,
        terminal: 0,
        failures: 0,
        transitions: 0,
        cutoffs: 0,
        witness: None,
    };
    visit(
        State::default(),
        mode,
        max_depth,
        &mut Vec::new(),
        &mut report,
    );
    report
}

/// Observable result of a valid replay, which may still be incomplete.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Replay {
    /// Counter value after the supplied choices.
    pub value: u8,
    /// Number of workers whose modeled increment has finished.
    pub completed: u8,
}

impl Replay {
    /// Terminal oracle; `None` means the supplied trace did not finish.
    pub fn valid_terminal(self) -> Option<bool> {
        (self.completed == 2).then_some(self.value == self.completed)
    }
}

/// Replay exact worker choices without substitution or automatic completion.
///
/// Unknown workers, finished workers, and extra choices after termination are
/// errors. An incomplete valid prefix is returned with an undecided oracle.
pub fn replay(mode: Mode, choices: &[usize]) -> Result<Replay, &'static str> {
    let mut state = State::default();
    for &worker in choices {
        state = state.step(mode, worker)?;
    }
    Ok(Replay {
        value: state.value,
        completed: state.pc.into_iter().filter(|&pc| pc == 2).count() as u8,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn negative_control_finds_four_lost_updates() {
        let r = search(Mode::Split, 4);
        assert_eq!(r.status, Status::Exhausted);
        assert_eq!(
            (r.terminal, r.failures, r.transitions, r.cutoffs),
            (6, 4, 18, 0)
        );
        assert_eq!(r.witness, Some(vec![0, 1, 0, 1]));
    }

    #[test]
    fn atomic_control_exhausts_both_orders() {
        let r = search(Mode::Atomic, 2);
        assert_eq!(r.status, Status::Exhausted);
        assert_eq!(
            (r.terminal, r.failures, r.transitions, r.cutoffs),
            (2, 0, 4, 0)
        );
        assert!(r.witness.is_none());
    }

    #[test]
    fn shallow_search_is_not_a_pass() {
        let r = search(Mode::Split, 3);
        assert_eq!(r.status, Status::Cutoff);
        assert_eq!((r.terminal, r.failures, r.cutoffs), (0, 0, 6));
        assert!(r.witness.is_none());
    }

    #[test]
    fn zero_depth_is_cut_off_at_initial_state() {
        let r = search(Mode::Atomic, 0);
        assert_eq!((r.status, r.transitions, r.cutoffs), (Status::Cutoff, 0, 1));
    }

    #[test]
    fn larger_bound_does_not_add_schedules() {
        assert_eq!(search(Mode::Split, 4), search(Mode::Split, 100));
    }

    #[test]
    fn witness_replays_and_serial_control_passes() {
        let witness = search(Mode::Split, 4).witness.unwrap();
        assert_eq!(
            replay(Mode::Split, &witness).unwrap().valid_terminal(),
            Some(false)
        );
        assert_eq!(
            replay(Mode::Split, &[0, 0, 1, 1]).unwrap().valid_terminal(),
            Some(true)
        );
        assert_eq!(
            replay(Mode::Atomic, &[1, 0]).unwrap().valid_terminal(),
            Some(true)
        );
    }

    #[test]
    fn invalid_replay_is_rejected() {
        assert_eq!(replay(Mode::Split, &[2]), Err("worker index out of range"));
        assert_eq!(
            replay(Mode::Split, &[0, 0, 0]),
            Err("worker already finished")
        );
        assert_eq!(
            replay(Mode::Atomic, &[0, 1, 0]),
            Err("worker already finished")
        );
    }

    #[test]
    fn incomplete_replay_is_not_success() {
        assert_eq!(replay(Mode::Split, &[0, 1]).unwrap().valid_terminal(), None);
    }
}
