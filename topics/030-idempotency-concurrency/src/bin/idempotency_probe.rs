//! Runs one forced concurrency schedule and deterministic split-write controls.
//!
//! A condition variable holds the first owner after its claim until a duplicate
//! observes [`BeginResult::InProgress`]. The probe then checks replay,
//! fingerprint mismatch, distinct keys, generation fencing, and both split-write
//! orders. The unit test compares the emitted receipt byte for byte. The probe
//! records no timing and makes no durability or network claim.

use idempotency_concurrency::{
    BeginResult, CompleteError, CompletionTicket, IdempotencyStore, RequestFingerprint,
    effect_before_receipt, receipt_before_effect, topic30_begin_decision, topic30_finish_allowed,
};
use std::env;
use std::error::Error;
use std::ffi::OsStr;
use std::fmt::{self, Display, Formatter};
use std::io::{self, BufWriter, Write};
use std::process::ExitCode;
use std::sync::{Arc, Condvar, Mutex};
use std::thread;

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

fn owner(result: BeginResult) -> Result<CompletionTicket, SelfCheckError> {
    match result {
        BeginResult::Owner(ticket) => Ok(ticket),
        _ => Err(SelfCheckError("expected a new owner")),
    }
}

fn run_self_check(output: &mut impl Write) -> Result<(), Box<dyn Error>> {
    let store = Arc::new(IdempotencyStore::new());
    let gate = Arc::new((Mutex::new((false, false)), Condvar::new()));

    let first_store = Arc::clone(&store);
    let first_gate = Arc::clone(&gate);
    let first = thread::spawn(move || -> Result<_, SelfCheckError> {
        let ticket = owner(first_store.begin("order-42", RequestFingerprint(2_000)))?;
        let (lock, wake) = &*first_gate;
        let mut state = lock.lock().unwrap_or_else(|poison| poison.into_inner());
        state.0 = true;
        wake.notify_all();
        while !state.1 {
            state = wake
                .wait(state)
                .unwrap_or_else(|poison| poison.into_inner());
        }
        drop(state);
        Ok(first_store.complete(ticket))
    });

    let duplicate_store = Arc::clone(&store);
    let duplicate_gate = Arc::clone(&gate);
    let duplicate = thread::spawn(move || {
        let (lock, wake) = &*duplicate_gate;
        let mut state = lock.lock().unwrap_or_else(|poison| poison.into_inner());
        while !state.0 {
            state = wake
                .wait(state)
                .unwrap_or_else(|poison| poison.into_inner());
        }
        drop(state);
        let result = duplicate_store.begin("order-42", RequestFingerprint(2_000));
        let mut state = lock.lock().unwrap_or_else(|poison| poison.into_inner());
        state.1 = true;
        wake.notify_all();
        result
    });

    let duplicate_result = duplicate
        .join()
        .map_err(|_| SelfCheckError("duplicate thread panicked"))?;
    ensure(
        duplicate_result == BeginResult::InProgress,
        "duplicate bypassed in-progress owner",
    )?;
    let first_result = first
        .join()
        .map_err(|_| SelfCheckError("first thread panicked"))??;
    let resource = first_result?;
    ensure(
        store.effect_count() == 1,
        "first completion effect count changed",
    )?;

    let replay = store.begin("order-42", RequestFingerprint(2_000));
    ensure(
        replay == BeginResult::Replay(resource),
        "completed retry did not replay",
    )?;
    let mismatch = store.begin("order-42", RequestFingerprint(2_001));
    ensure(
        mismatch == BeginResult::ParameterMismatch,
        "changed payload was accepted",
    )?;

    let second = owner(store.begin("order-43", RequestFingerprint(2_000)))?;
    let second_resource = store.complete(second)?;

    let stale = owner(store.begin("order-44", RequestFingerprint(3_000)))?;
    let current = store.take_over("order-44", RequestFingerprint(3_000))?;
    ensure(
        store.complete(stale) == Err(CompleteError::StaleOwner),
        "stale owner was not fenced",
    )?;
    let current_resource = store.complete(current)?;

    ensure(topic30_begin_decision(0, 7, 9) == 0, "absent hook changed")?;
    ensure(
        topic30_begin_decision(1, 7, 7) == 1,
        "in-progress hook changed",
    )?;
    ensure(topic30_begin_decision(2, 7, 7) == 2, "replay hook changed")?;
    ensure(
        topic30_begin_decision(2, 7, 9) == 3,
        "mismatch hook changed",
    )?;
    ensure(
        topic30_finish_allowed(1, 8, 8) == 1,
        "current generation was rejected",
    )?;
    ensure(
        topic30_finish_allowed(1, 8, 7) == 0,
        "stale generation was accepted",
    )?;

    let effect_first = effect_before_receipt();
    let receipt_first = receipt_before_effect();
    ensure(
        effect_first.effects == 2 && !effect_first.replayed,
        "effect-first control changed",
    )?;
    ensure(
        receipt_first.effects == 0 && receipt_first.replayed,
        "receipt-first control changed",
    )?;
    ensure(
        store.effect_count() == 3 && store.invariants_hold(),
        "safe invariants failed",
    )?;

    writeln!(
        output,
        "concurrent same key: winner=OWNER duplicate=IN_PROGRESS"
    )?;
    writeln!(
        output,
        "lost reply: first=UNKNOWN retry=REPLAY resource={} effects=1",
        resource.0
    )?;
    writeln!(
        output,
        "same key changed payload: PARAMETER_MISMATCH effects=1"
    )?;
    writeln!(
        output,
        "new key same payload: CREATED resource={} effects=2",
        second_resource.0
    )?;
    writeln!(
        output,
        "expired owner: stale=FENCED current=CREATED resource={} effects=3",
        current_resource.0
    )?;
    writeln!(
        output,
        "unsafe effect-before-receipt: effects=2 result=DUPLICATE"
    )?;
    writeln!(
        output,
        "unsafe receipt-before-effect: effects=0 result=FALSE_REPLAY"
    )?;
    writeln!(output, "invariants: PASS")?;
    Ok(())
}

fn main() -> ExitCode {
    let mut args = env::args_os().skip(1);
    let first = args.next();
    let valid = (first.is_none() || first.as_deref() == Some(OsStr::new("--self-check")))
        && args.next().is_none();
    if !valid {
        eprintln!("usage: idempotency-probe [--self-check]");
        return ExitCode::from(2);
    }

    let stdout = io::stdout();
    let mut output = BufWriter::new(stdout.lock());
    match run_self_check(&mut output).and_then(|()| output.flush().map_err(Into::into)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("idempotency-probe: {error}");
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
