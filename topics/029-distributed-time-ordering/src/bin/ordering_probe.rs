//! Runs deterministic self-checks for the distributed-time ordering models.
//!
//! With no arguments, or with `--self-check`, the probe prints the same stable
//! lines. It uses injected integer clock readings and performs no networking or
//! host-clock reads.
//!
//! All transition and relation checks finish before the probe submits the first
//! receipt line to its buffered writer. Invalid argument shapes return status
//! `2`; a check or observed write failure returns [`ExitCode::FAILURE`].

use distributed_time_ordering::{
    HybridLogicalClock, HybridTimestamp, IntervalRelation, LamportClock, LwwStamp, Replica,
    UncertaintyInterval, VectorClock, VectorRelation, topic29_hlc_receive, topic29_lamport_receive,
    topic29_lww_choice, topic29_vector_relation, wall_clock_lww,
};
use std::env;
use std::error::Error;
use std::ffi::OsStr;
use std::fmt::{self, Display, Formatter};
use std::io::{self, BufWriter, Write};
use std::process::ExitCode;

#[cfg(test)]
const EXPECTED_OUTPUT: &str = include_str!("../../experiment/expected.txt");

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct SelfCheckError(&'static str);

impl Display for SelfCheckError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.0)
    }
}

impl Error for SelfCheckError {}

fn ensure(condition: bool, message: &'static str) -> Result<(), SelfCheckError> {
    if condition {
        Ok(())
    } else {
        Err(SelfCheckError(message))
    }
}

fn run_self_check(output: &mut impl Write) -> Result<(), Box<dyn Error>> {
    let paid = LwwStamp::new(1_000, Replica::A);
    let packed = LwwStamp::new(900, Replica::B);
    let winner = wall_clock_lww(paid, packed);
    ensure(
        winner == paid,
        "skewed wall-clock LWW did not select the greater physical reading",
    )?;
    ensure(
        wall_clock_lww(paid, LwwStamp::new(1_100, Replica::B)).replica() == Replica::B,
        "wall-clock LWW positive control failed",
    )?;

    let mut sender = LamportClock::new(0);
    let sent_lamport = sender.tick()?;
    let mut receiver = LamportClock::new(0);
    let received_lamport = receiver.receive(sent_lamport)?;
    ensure(
        (sent_lamport, received_lamport) == (1, 2),
        "Lamport send/receive transition changed",
    )?;

    let mut vector_a = VectorClock::new();
    vector_a.tick(Replica::A)?;
    let mut vector_b = VectorClock::new();
    vector_b.receive(Replica::B, vector_a)?;
    let causal_relation = vector_a.relation(vector_b);

    let mut independent_b = VectorClock::new();
    independent_b.tick(Replica::B)?;
    let concurrent_relation = vector_a.relation(independent_b);
    ensure(
        causal_relation == VectorRelation::Before
            && concurrent_relation == VectorRelation::Concurrent
            && vector_a.counters() == [1, 0]
            && vector_b.counters() == [1, 1],
        "vector-clock relation changed",
    )?;

    let mut hlc_sender = HybridLogicalClock::new();
    let sent_hlc = hlc_sender.local(1_000)?;
    let mut hlc_receiver = HybridLogicalClock::new();
    let received_hlc = hlc_receiver.receive(900, sent_hlc)?;
    ensure(
        sent_hlc == HybridTimestamp::new(1_000, 0)
            && received_hlc == HybridTimestamp::new(1_000, 1),
        "hybrid logical clock transition changed",
    )?;

    let early = UncertaintyInterval::new(990, 1_010)?;
    let overlap = UncertaintyInterval::new(1_000, 1_020)?;
    let later = UncertaintyInterval::new(1_011, 1_030)?;
    ensure(
        early.relation(later) == IntervalRelation::DefinitelyBefore
            && early.relation(overlap) == IntervalRelation::Indeterminate,
        "uncertainty-interval relation changed",
    )?;

    ensure(
        topic29_lww_choice(1_000, 900) == 0
            && topic29_lamport_receive(0, sent_lamport) == received_lamport
            && topic29_lamport_receive(0, u64::MAX) == 0
            && topic29_vector_relation(1, 0, 0, 1) == 3
            && topic29_hlc_receive(0, 0, 1_000, 0, 900) == HybridTimestamp::new(1_000, 1),
        "inspection hook contract changed",
    )?;

    writeln!(
        output,
        "wall LWW: paid@1000 beats packed@900 -> causal predecessor selected"
    )?;
    writeln!(
        output,
        "Lamport: paid=1, packed=2 -> causal order preserved"
    )?;
    writeln!(output, "vector: [1,0] < [1,1]; [1,0] || [0,1]")?;
    writeln!(
        output,
        "HLC: paid=(1000,0), packed=(1000,1) with B wall=900"
    )?;
    writeln!(
        output,
        "interval: [990,1010] and [1000,1020] overlap -> physical order unknown"
    )?;
    writeln!(output, "self-check: PASS")?;
    Ok(())
}

fn main() -> ExitCode {
    let mut args = env::args_os().skip(1);
    let first = args.next();
    let valid = (first.is_none() || first.as_deref() == Some(OsStr::new("--self-check")))
        && args.next().is_none();
    if !valid {
        eprintln!("usage: ordering-probe [--self-check]");
        return ExitCode::from(2);
    }

    let stdout = io::stdout();
    let mut output = BufWriter::new(stdout.lock());
    match run_self_check(&mut output).and_then(|()| output.flush().map_err(Into::into)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("ordering-probe: {error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn self_check_output_is_stable() {
        let mut output = Vec::new();
        run_self_check(&mut output).unwrap();
        assert_eq!(String::from_utf8(output).unwrap(), EXPECTED_OUTPUT);
    }
}
