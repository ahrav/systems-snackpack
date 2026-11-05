//! Finite two-phase-commit model with atomic durable records and retained messages.
//!
//! Each state represents one transaction with a fixed participant set. A crash
//! discards coordinator votes and the volatile decision; durable records survive.
//! Messages remain deliverable and duplicate delivery is an idempotent self-loop.
//! Run `cargo run -p distributed-atomic-commit --example explore -- safe 2`.
//!
//! ```
//! use distributed_atomic_commit::{explore, Mode};
//! let graph = explore(2, Mode::Safe);
//! assert!(graph.states.len() > 10);
//! ```
use std::collections::HashMap;

const WORKING: u8 = 0;
const PREPARED: u8 = 1;
const COMMITTED: u8 = 2;
const ABORTED: u8 = 3;

/// Protocol choice. Fault modes deliberately violate the durable protocol.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// Durable prepare, durable decision, then delivery.
    Safe,
    /// Permit a prepared participant to abort on timeout.
    Timeout,
    /// Permit COMMIT messages before the coordinator persists COMMIT.
    Early,
}

/// Complete state, including durable participant records and retained messages.
#[derive(Clone, Copy, Debug, Default, Hash, PartialEq, Eq)]
pub struct State {
    participants: [u8; 3],
    votes: u8,
    decision: u8,
    volatile_commit: bool,
    alive: bool,
    commit_messages: u8,
    abort_messages: u8,
}

impl State {
    /// Export fields for a separately implemented abstract-specification checker.
    ///
    /// # Panics
    /// Panics when `n` exceeds the three stored participant slots.
    pub fn fields(self, n: usize) -> String {
        let p: String = self.participants[..n]
            .iter()
            .map(|v| char::from(b'0' + v))
            .collect();
        format!(
            "{p}\t{}\t{}\t{}\t{}\t{}\t{}",
            self.votes,
            self.decision,
            u8::from(self.volatile_commit),
            u8::from(self.alive),
            self.commit_messages,
            self.abort_messages
        )
    }
}

/// Reachable state graph. Edges carry stable action names for counterexamples.
pub struct Graph {
    /// Breadth-first discovery order, beginning with initial state zero.
    pub states: Vec<State>,
    /// Source index, destination index, and action name.
    pub edges: Vec<(usize, usize, String)>,
}

fn successors(s: State, n: usize, mode: Mode) -> Vec<(State, String)> {
    let mut out = Vec::new();
    let all = (1 << n) - 1;
    for i in 0..n {
        let bit = 1 << i;
        if s.participants[i] == WORKING {
            for (value, name) in [(PREPARED, "prepare"), (ABORTED, "reject")] {
                let mut t = s;
                t.participants[i] = value;
                out.push((t, format!("{name}{i}")));
            }
        }
        if s.alive && s.participants[i] == PREPARED && s.votes & bit == 0 {
            let mut t = s;
            t.votes |= bit;
            out.push((t, format!("vote{i}")));
        }
        if mode == Mode::Timeout && s.participants[i] == PREPARED {
            let mut t = s;
            t.participants[i] = ABORTED;
            out.push((t, format!("timeout{i}")));
        }
        for (decision, messages, name) in [
            (COMMITTED, s.commit_messages, "commit"),
            (ABORTED, s.abort_messages, "abort"),
        ] {
            if messages & bit != 0 {
                let mut t = s;
                // Terminal records reject contradictory messages. Repeated delivery
                // acknowledges the existing record without applying the debit again.
                if s.participants[i] == PREPARED
                    || (decision == ABORTED && s.participants[i] == WORKING)
                {
                    t.participants[i] = decision;
                }
                out.push((t, format!("deliver_{name}{i}")));
            }
        }
    }
    if s.alive {
        let mut t = s;
        t.alive = false;
        t.votes = 0;
        t.volatile_commit = false;
        out.push((t, "crash".into()));
        if s.decision == 0 {
            if s.votes == all || s.volatile_commit {
                let mut t = s;
                t.decision = COMMITTED;
                out.push((t, "persist_commit".into()));
                if mode == Mode::Early && !s.volatile_commit {
                    let mut t = s;
                    t.volatile_commit = true;
                    out.push((t, "choose_volatile_commit".into()));
                }
            }
            if !s.volatile_commit {
                let mut t = s;
                t.decision = ABORTED;
                out.push((t, "persist_abort".into()));
            }
        }
        for i in 0..n {
            let bit = 1 << i;
            if (s.decision == COMMITTED || s.volatile_commit) && s.commit_messages & bit == 0 {
                let mut t = s;
                t.commit_messages |= bit;
                out.push((t, format!("send_commit{i}")));
            }
            if s.decision == ABORTED && s.abort_messages & bit == 0 {
                let mut t = s;
                t.abort_messages |= bit;
                out.push((t, format!("send_abort{i}")));
            }
        }
    } else {
        let mut t = s;
        t.alive = true;
        if t.decision == 0 {
            // A sole recovering coordinator has exclusive authority. With no
            // durable decision it may abort; a live prepared participant may not.
            t.decision = ABORTED;
        }
        out.push((t, "recover".into()));
    }
    out
}

/// Enumerate the complete finite graph, including crashes, retries and delivery orders.
///
/// # Panics
/// Panics when the participant count is outside 2..=3.
pub fn explore(n: usize, mode: Mode) -> Graph {
    assert!((2..=3).contains(&n));
    let start = State {
        alive: true,
        ..State::default()
    };
    let mut graph = Graph {
        states: vec![start],
        edges: Vec::new(),
    };
    let mut ids = HashMap::from([(start, 0)]);
    let mut index = 0;
    while index < graph.states.len() {
        for (next, label) in successors(graph.states[index], n, mode) {
            let id = *ids.entry(next).or_insert_with(|| {
                graph.states.push(next);
                graph.states.len() - 1
            });
            graph.edges.push((index, id, label));
        }
        index += 1;
    }
    graph
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn safe_graph_preserves_agreement_and_reaches_both_outcomes() {
        for n in [2, 3] {
            let g = explore(n, Mode::Safe);
            assert!(g.states.iter().all(|s| {
                let p = &s.participants[..n];
                !(p.contains(&COMMITTED) && p.contains(&ABORTED))
            }));
            for outcome in [COMMITTED, ABORTED] {
                assert!(
                    g.states
                        .iter()
                        .any(|s| s.participants[..n].iter().all(|p| *p == outcome))
                );
            }
            assert!(
                g.edges
                    .iter()
                    .any(|(a, b, label)| a == b && label.starts_with("deliver_"))
            );
        }
    }

    #[test]
    fn both_faults_have_terminal_disagreement() {
        for mode in [Mode::Timeout, Mode::Early] {
            let g = explore(2, mode);
            assert!(g.states.iter().any(|s| {
                s.participants.contains(&COMMITTED) && s.participants.contains(&ABORTED)
            }));
        }
    }
}
