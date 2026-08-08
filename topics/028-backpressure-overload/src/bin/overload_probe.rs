//! Measures one synchronized synthetic same-key wave with independent or shared retries.
//!
//! # Synchronization
//!
//! The harness creates every caller thread before the measured release. A start
//! barrier releases the wave, and a decision barrier freezes every join-or-shed
//! decision before physical work begins. In controlled mode, one leader publishes
//! one terminal result while holding the flight mutex; followers predicate-wait on
//! the same mutex and condition variable.
//!
//! # Timing boundaries
//!
//! Receipt timestamps use the release instant as their origin. `burst_ns` ends
//! when the coordinator returns from the all-settled barrier, before thread joins
//! and CSV serialization. It includes end-barrier release overhead and therefore
//! uses a different endpoint from `max(settled_ns)`. `setup_ns` covers shared
//! synchronization-state setup and thread creation through the coordinator's
//! return from the ready barrier.
//!
//! Calibration targets 200 µs per synthetic physical attempt and reports the
//! achieved mean. It imposes no acceptance tolerance.
//!
//! # Scope
//!
//! Each wave uses one synthetic key digest and CPU work in place of an origin
//! request. The harness does not implement or measure DNS, caching, networking,
//! backoff, cancellation, recovery timing, multiple keys, or a global key bound.

use backpressure_overload::{
    ExperimentConfig, Label, Phase, Treatment, closed_form_counts, mix64, treatment_for,
};
use std::collections::BTreeSet;
use std::env;
use std::error::Error;
use std::fs::File;
use std::hint::black_box;
use std::io::{self, BufWriter, Write};
use std::path::PathBuf;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Barrier, Condvar, Mutex, MutexGuard, OnceLock};
use std::thread::{self, JoinHandle};
use std::time::Instant;

/// Runs the calibrated physical-origin loop retained for final-image inspection.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic28_origin_work(iterations: u64, seed: u64) -> u64 {
    let mut value = seed ^ 0x9e37_79b9_7f4a_7c15;
    let mut remaining = iterations;
    while remaining != 0 {
        value = value
            .wrapping_mul(0xd6e8_feb8_6659_fd93)
            .wrapping_add(0xa076_1d64_78bd_642f);
        value ^= value.rotate_left(23);
        value = black_box(value);
        remaining -= 1;
    }
    black_box(value)
}

#[inline(never)]
fn completed_digest(key_digest: u64) -> u64 {
    black_box(mix64(key_digest ^ 0x434f_4d50_4c45_5445))
}

#[inline(never)]
fn exhausted_digest(key_digest: u64) -> u64 {
    black_box(mix64(key_digest ^ 0x4558_4841_5553_5445))
}

#[derive(Clone, Debug)]
struct RunConfig {
    phase: Phase,
    block: usize,
    period: usize,
    label: Label,
    treatment: Treatment,
    seed: u64,
    key_digest: u64,
    experiment: ExperimentConfig,
    logical_path: PathBuf,
    attempt_path: PathBuf,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum FlightResult {
    Success(u64),
    RetryExhausted(u64),
}

impl FlightResult {
    fn status(self) -> &'static str {
        match self {
            Self::Success(_) => "completed",
            Self::RetryExhausted(_) => "retry_exhausted",
        }
    }

    fn digest(self) -> u64 {
        match self {
            Self::Success(digest) | Self::RetryExhausted(digest) => digest,
        }
    }
}

#[derive(Clone, Debug)]
struct LogicalRecord {
    logical_id: usize,
    role: &'static str,
    flight_id: Option<usize>,
    admission_ns: u64,
    settled_ns: u64,
    status: &'static str,
    result_digest: Option<u64>,
}

#[derive(Clone, Debug)]
struct AttemptRecord {
    flight_id: usize,
    attempt_no: usize,
    retry_token_charged: usize,
    retry_tokens_after: usize,
    queued_ns: u64,
    start_ns: u64,
    end_ns: u64,
    outcome: &'static str,
    active_at_start: usize,
    work_checksum: u64,
}

struct ThreadReceipt {
    logical: LogicalRecord,
    attempts: Vec<AttemptRecord>,
}

struct WaveReceipt {
    logical: Vec<LogicalRecord>,
    attempts: Vec<AttemptRecord>,
    peak_origin_active: usize,
    peak_admitted: usize,
    setup_ns: u64,
    burst_ns: u64,
}

#[derive(Clone)]
struct ThreadSync {
    ready: Arc<Barrier>,
    start: Arc<Barrier>,
    decision: Arc<Barrier>,
    end: Arc<Barrier>,
}

#[derive(Default)]
struct AdmissionState {
    current: usize,
    peak: usize,
}

#[derive(Default)]
struct ControlledState {
    // Protected state for one synthetic key. `leader_taken` never reverts;
    // `done` becomes true only after `result` is populated under the same mutex.
    admission: AdmissionState,
    leader_taken: bool,
    done: bool,
    result: Option<FlightResult>,
}

#[derive(Default)]
struct ControlledFlight {
    state: Mutex<ControlledState>,
    ready: Condvar,
}

struct OriginPermits {
    // Physical-work permits are independent of admission; an admitted caller
    // retains its waiter slot while queued here.
    capacity: usize,
    active: Mutex<usize>,
    ready: Condvar,
}

impl OriginPermits {
    fn new(capacity: usize) -> Self {
        Self {
            capacity,
            active: Mutex::new(0),
            ready: Condvar::new(),
        }
    }

    fn acquire(&self) -> (OriginPermit<'_>, usize) {
        let mut active = lock(&self.active);
        while *active == self.capacity {
            active = wait(&self.ready, active);
        }
        *active += 1;
        let active_at_start = *active;
        drop(active);
        (OriginPermit { permits: self }, active_at_start)
    }
}

struct OriginPermit<'a> {
    permits: &'a OriginPermits,
}

impl Drop for OriginPermit<'_> {
    fn drop(&mut self) {
        let mut active = lock(&self.permits.active);
        *active -= 1;
        self.permits.ready.notify_one();
    }
}

#[derive(Clone)]
struct AttemptContext {
    origin: Arc<OnceLock<Instant>>,
    permits: Arc<OriginPermits>,
    peak_origin_active: Arc<AtomicUsize>,
    experiment: ExperimentConfig,
    seed: u64,
    key_digest: u64,
}

fn lock<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn wait<'a, T>(condition: &Condvar, guard: MutexGuard<'a, T>) -> MutexGuard<'a, T> {
    condition
        .wait(guard)
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn relative_ns(origin: &OnceLock<Instant>) -> u64 {
    origin
        .get()
        .expect("release instant is set before barriers open")
        .elapsed()
        .as_nanos() as u64
}

fn execute_flight(
    flight_id: usize,
    context: &AttemptContext,
    attempts: &mut Vec<AttemptRecord>,
) -> FlightResult {
    // Attempts after the first charge one retry token before acquiring the
    // origin permit. The permit spans the active-peak update, attempt start/end
    // timestamps, seed derivation, and calibrated CPU loop; the queue timestamp,
    // retry decisions, and receipt append occur outside it.
    let mut retry_tokens = context.experiment.retry_tokens();
    for attempt_no in 1..=context.experiment.max_attempts() {
        let retry_token_charged = usize::from(attempt_no > 1);
        if retry_token_charged != 0 {
            debug_assert!(retry_tokens != 0);
            retry_tokens -= 1;
        }
        let queued_ns = relative_ns(&context.origin);
        let (permit, active_at_start) = context.permits.acquire();
        context
            .peak_origin_active
            .fetch_max(active_at_start, Ordering::Relaxed);
        let start_ns = relative_ns(&context.origin);
        let work_seed =
            mix64(context.seed ^ (flight_id as u64).wrapping_mul(0x9e37_79b9) ^ attempt_no as u64);
        let work_checksum = topic28_origin_work(context.experiment.work_iters(), work_seed);
        let end_ns = relative_ns(&context.origin);
        drop(permit);

        let success = attempt_no == backpressure_overload::SUCCESS_ATTEMPT;
        attempts.push(AttemptRecord {
            flight_id,
            attempt_no,
            retry_token_charged,
            retry_tokens_after: retry_tokens,
            queued_ns,
            start_ns,
            end_ns,
            outcome: if success { "success" } else { "transient" },
            active_at_start,
            work_checksum,
        });
        if success {
            return FlightResult::Success(completed_digest(context.key_digest));
        }
        if attempt_no == context.experiment.max_attempts() || retry_tokens == 0 {
            return FlightResult::RetryExhausted(exhausted_digest(context.key_digest));
        }
    }
    unreachable!("validated maximum-attempt count is nonzero")
}

fn controlled_thread(
    logical_id: usize,
    config: &RunConfig,
    sync: &ThreadSync,
    flight: &ControlledFlight,
    context: &AttemptContext,
) -> ThreadReceipt {
    sync.ready.wait();
    sync.start.wait();
    let admission_ns = relative_ns(&context.origin);
    let (admitted, leader) = {
        let mut state = lock(&flight.state);
        if state.admission.current == config.experiment.waiter_cap() {
            (false, false)
        } else {
            state.admission.current += 1;
            state.admission.peak = state.admission.peak.max(state.admission.current);
            let leader = !state.leader_taken;
            state.leader_taken = true;
            (true, leader)
        }
    };

    // No leader can execute until every caller has made an atomic join-or-shed
    // decision, so the measured follower population cannot disappear in a race.
    sync.decision.wait();
    if !admitted {
        let settled_ns = relative_ns(&context.origin);
        sync.end.wait();
        return ThreadReceipt {
            logical: LogicalRecord {
                logical_id,
                role: "shed",
                flight_id: None,
                admission_ns,
                settled_ns,
                status: "shed",
                result_digest: None,
            },
            attempts: Vec::new(),
        };
    }

    let mut attempts = Vec::new();
    let result = if leader {
        let result = execute_flight(1, context, &mut attempts);
        let mut state = lock(&flight.state);
        state.result = Some(result);
        state.done = true;
        flight.ready.notify_all();
        result
    } else {
        let mut state = lock(&flight.state);
        while !state.done {
            state = wait(&flight.ready, state);
        }
        state.result.expect("done flight has a terminal result")
    };
    let settled_ns = relative_ns(&context.origin);
    {
        let mut state = lock(&flight.state);
        state.admission.current -= 1;
    }
    sync.end.wait();
    ThreadReceipt {
        logical: LogicalRecord {
            logical_id,
            role: if leader { "leader" } else { "follower" },
            flight_id: Some(1),
            admission_ns,
            settled_ns,
            status: result.status(),
            result_digest: Some(result.digest()),
        },
        attempts,
    }
}

fn naive_thread(
    logical_id: usize,
    config: &RunConfig,
    sync: &ThreadSync,
    admission: &Mutex<AdmissionState>,
    context: &AttemptContext,
) -> ThreadReceipt {
    sync.ready.wait();
    sync.start.wait();
    let admission_ns = relative_ns(&context.origin);
    let admitted = {
        let mut state = lock(admission);
        if state.current == config.experiment.waiter_cap() {
            false
        } else {
            state.current += 1;
            state.peak = state.peak.max(state.current);
            true
        }
    };
    sync.decision.wait();
    if !admitted {
        let settled_ns = relative_ns(&context.origin);
        sync.end.wait();
        return ThreadReceipt {
            logical: LogicalRecord {
                logical_id,
                role: "shed",
                flight_id: None,
                admission_ns,
                settled_ns,
                status: "shed",
                result_digest: None,
            },
            attempts: Vec::new(),
        };
    }

    let flight_id = logical_id + 1;
    let mut attempts = Vec::new();
    let result = execute_flight(flight_id, context, &mut attempts);
    let settled_ns = relative_ns(&context.origin);
    {
        let mut state = lock(admission);
        state.current -= 1;
    }
    sync.end.wait();
    ThreadReceipt {
        logical: LogicalRecord {
            logical_id,
            role: "independent",
            flight_id: Some(flight_id),
            admission_ns,
            settled_ns,
            status: result.status(),
            result_digest: Some(result.digest()),
        },
        attempts,
    }
}

fn run_wave(config: &RunConfig) -> Result<WaveReceipt, Box<dyn Error>> {
    // Warm code and black-box plumbing before setup or burst timing.
    black_box(topic28_origin_work(
        config.experiment.work_iters().min(4_096),
        mix64(config.seed),
    ));

    let setup_started = Instant::now();
    let participants = config.experiment.callers() + 1;
    let sync = ThreadSync {
        ready: Arc::new(Barrier::new(participants)),
        start: Arc::new(Barrier::new(participants)),
        decision: Arc::new(Barrier::new(participants)),
        end: Arc::new(Barrier::new(participants)),
    };
    let origin = Arc::new(OnceLock::new());
    let permits = Arc::new(OriginPermits::new(config.experiment.origin_capacity()));
    let peak_origin_active = Arc::new(AtomicUsize::new(0));
    let controlled = Arc::new(ControlledFlight::default());
    let naive_admission = Arc::new(Mutex::new(AdmissionState::default()));
    let mut handles: Vec<JoinHandle<ThreadReceipt>> =
        Vec::with_capacity(config.experiment.callers());

    for logical_id in 0..config.experiment.callers() {
        let thread_config = config.clone();
        let thread_sync = sync.clone();
        let thread_controlled = Arc::clone(&controlled);
        let thread_naive_admission = Arc::clone(&naive_admission);
        let context = AttemptContext {
            origin: Arc::clone(&origin),
            permits: Arc::clone(&permits),
            peak_origin_active: Arc::clone(&peak_origin_active),
            experiment: config.experiment,
            seed: config.seed,
            key_digest: config.key_digest,
        };
        let handle = thread::Builder::new()
            .name(format!("topic28-{logical_id}"))
            .spawn(move || match thread_config.treatment {
                Treatment::Controlled => controlled_thread(
                    logical_id,
                    &thread_config,
                    &thread_sync,
                    &thread_controlled,
                    &context,
                ),
                Treatment::Naive => naive_thread(
                    logical_id,
                    &thread_config,
                    &thread_sync,
                    &thread_naive_admission,
                    &context,
                ),
            })?;
        handles.push(handle);
    }

    // Every caller has been created and has reached the ready barrier before
    // the measured release. They next rendezvous at `start`; none can pass it
    // before the origin exists.
    sync.ready.wait();
    let setup_ns = setup_started.elapsed().as_nanos() as u64;
    let release = Instant::now();
    origin
        .set(release)
        .map_err(|_| io::Error::other("release instant set twice"))?;
    sync.start.wait();
    sync.decision.wait();
    sync.end.wait();
    let burst_ns = release.elapsed().as_nanos() as u64;

    // Thread joins and receipt merging start after `burst_ns` is fixed.
    let mut logical = Vec::with_capacity(config.experiment.callers());
    let mut attempts = Vec::new();
    for handle in handles {
        let receipt = handle
            .join()
            .map_err(|_| io::Error::other("caller thread panicked"))?;
        logical.push(receipt.logical);
        attempts.extend(receipt.attempts);
    }
    logical.sort_by_key(|record| record.logical_id);
    attempts.sort_by_key(|record| (record.flight_id, record.attempt_no));
    let peak_admitted = match config.treatment {
        Treatment::Controlled => lock(&controlled.state).admission.peak,
        Treatment::Naive => lock(&naive_admission).peak,
    };
    Ok(WaveReceipt {
        logical,
        attempts,
        peak_origin_active: peak_origin_active.load(Ordering::Relaxed),
        peak_admitted,
        setup_ns,
        burst_ns,
    })
}

fn result_checksum(records: &[LogicalRecord]) -> u64 {
    records
        .iter()
        .filter_map(|record| {
            record
                .result_digest
                .map(|digest| mix64(digest ^ record.logical_id as u64))
        })
        .fold(0_u64, u64::wrapping_add)
}

fn verify_counts(config: &RunConfig, receipt: &WaveReceipt) -> Result<(), io::Error> {
    let expected = closed_form_counts(config.treatment, config.experiment)
        .ok_or_else(|| io::Error::other("closed-form count overflow"))?;
    let completed = receipt
        .logical
        .iter()
        .filter(|record| record.status == "completed")
        .count();
    let exhausted = receipt
        .logical
        .iter()
        .filter(|record| record.status == "retry_exhausted")
        .count();
    let shed = receipt
        .logical
        .iter()
        .filter(|record| record.status == "shed")
        .count();
    let leaders = receipt
        .logical
        .iter()
        .filter(|record| record.role == "leader")
        .count();
    let followers = receipt
        .logical
        .iter()
        .filter(|record| record.role == "follower")
        .count();
    let flights = receipt
        .attempts
        .iter()
        .map(|attempt| attempt.flight_id)
        .collect::<BTreeSet<_>>()
        .len();
    let retries = receipt
        .attempts
        .iter()
        .filter(|attempt| attempt.retry_token_charged != 0)
        .count();
    let transients = receipt
        .attempts
        .iter()
        .filter(|attempt| attempt.outcome == "transient")
        .count();
    let successes = receipt
        .attempts
        .iter()
        .filter(|attempt| attempt.outcome == "success")
        .count();
    let actual = (
        completed,
        exhausted,
        shed,
        leaders,
        followers,
        flights,
        receipt.attempts.len(),
        retries,
        transients,
        successes,
    );
    let modeled = (
        expected.completed,
        expected.retry_exhausted,
        expected.shed,
        expected.leaders,
        expected.followers,
        expected.flights,
        expected.origin_attempts,
        expected.retry_attempts,
        expected.transient_attempts,
        expected.successful_attempts,
    );
    if actual != modeled {
        return Err(io::Error::other(format!(
            "runtime counts {actual:?} differ from model {modeled:?}"
        )));
    }
    if receipt.peak_origin_active > config.experiment.origin_capacity()
        || receipt.peak_admitted > config.experiment.waiter_cap()
    {
        return Err(io::Error::other("measured capacity bound exceeded"));
    }
    Ok(())
}

fn write_csv_row(output: &mut impl Write, fields: &[String]) -> io::Result<()> {
    for (index, field) in fields.iter().enumerate() {
        if index != 0 {
            output.write_all(b",")?;
        }
        if field.contains([',', '"', '\n', '\r']) {
            output.write_all(b"\"")?;
            output.write_all(field.replace('"', "\"\"").as_bytes())?;
            output.write_all(b"\"")?;
        } else {
            output.write_all(field.as_bytes())?;
        }
    }
    output.write_all(b"\n")
}

fn write_receipts(config: &RunConfig, receipt: &WaveReceipt) -> io::Result<()> {
    let pid = std::process::id().to_string();
    let mut logical_output = BufWriter::new(File::create(&config.logical_path)?);
    writeln!(
        logical_output,
        "logical_id,pid,phase,block,period,label,treatment,key_digest,role,flight_id,admission_ns,settled_ns,status,result_digest"
    )?;
    for record in &receipt.logical {
        write_csv_row(
            &mut logical_output,
            &[
                record.logical_id.to_string(),
                pid.clone(),
                config.phase.as_str().to_string(),
                config.block.to_string(),
                config.period.to_string(),
                config.label.as_str().to_string(),
                config.treatment.as_str().to_string(),
                config.key_digest.to_string(),
                record.role.to_string(),
                record
                    .flight_id
                    .map_or_else(String::new, |id| id.to_string()),
                record.admission_ns.to_string(),
                record.settled_ns.to_string(),
                record.status.to_string(),
                record
                    .result_digest
                    .map_or_else(String::new, |digest| digest.to_string()),
            ],
        )?;
    }
    logical_output.flush()?;

    let mut attempt_output = BufWriter::new(File::create(&config.attempt_path)?);
    writeln!(
        attempt_output,
        "pid,phase,block,period,label,treatment,flight_id,attempt_no,retry_token_charged,retry_tokens_after,queued_ns,start_ns,end_ns,outcome,active_at_start,work_checksum"
    )?;
    for attempt in &receipt.attempts {
        write_csv_row(
            &mut attempt_output,
            &[
                pid.clone(),
                config.phase.as_str().to_string(),
                config.block.to_string(),
                config.period.to_string(),
                config.label.as_str().to_string(),
                config.treatment.as_str().to_string(),
                attempt.flight_id.to_string(),
                attempt.attempt_no.to_string(),
                attempt.retry_token_charged.to_string(),
                attempt.retry_tokens_after.to_string(),
                attempt.queued_ns.to_string(),
                attempt.start_ns.to_string(),
                attempt.end_ns.to_string(),
                attempt.outcome.to_string(),
                attempt.active_at_start.to_string(),
                attempt.work_checksum.to_string(),
            ],
        )?;
    }
    attempt_output.flush()
}

fn summary_fields(config: &RunConfig, receipt: &WaveReceipt) -> Vec<String> {
    let completed = receipt
        .logical
        .iter()
        .filter(|record| record.status == "completed")
        .count();
    let shed = receipt
        .logical
        .iter()
        .filter(|record| record.status == "shed")
        .count();
    let leaders = receipt
        .logical
        .iter()
        .filter(|record| record.role == "leader")
        .count();
    let followers = receipt
        .logical
        .iter()
        .filter(|record| record.role == "follower")
        .count();
    let flights = receipt
        .attempts
        .iter()
        .map(|attempt| attempt.flight_id)
        .collect::<BTreeSet<_>>()
        .len();
    vec![
        std::process::id().to_string(),
        config.phase.as_str().to_string(),
        config.block.to_string(),
        config.period.to_string(),
        config.label.as_str().to_string(),
        config.treatment.as_str().to_string(),
        config.seed.to_string(),
        config.key_digest.to_string(),
        config.experiment.callers().to_string(),
        config.experiment.waiter_cap().to_string(),
        config.experiment.origin_capacity().to_string(),
        config.experiment.max_attempts().to_string(),
        config.experiment.retry_tokens().to_string(),
        config.experiment.work_iters().to_string(),
        completed.to_string(),
        shed.to_string(),
        leaders.to_string(),
        followers.to_string(),
        flights.to_string(),
        receipt.attempts.len().to_string(),
        receipt
            .attempts
            .iter()
            .filter(|attempt| attempt.retry_token_charged != 0)
            .count()
            .to_string(),
        receipt
            .attempts
            .iter()
            .filter(|attempt| attempt.outcome == "transient")
            .count()
            .to_string(),
        receipt
            .attempts
            .iter()
            .filter(|attempt| attempt.outcome == "success")
            .count()
            .to_string(),
        receipt.peak_origin_active.to_string(),
        receipt.peak_admitted.to_string(),
        receipt.burst_ns.to_string(),
        receipt.setup_ns.to_string(),
        result_checksum(&receipt.logical).to_string(),
        config.logical_path.display().to_string(),
        config.attempt_path.display().to_string(),
    ]
}

fn value(args: &[String], name: &str) -> Result<String, io::Error> {
    let position = args
        .iter()
        .position(|argument| argument == name)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, format!("missing {name}")))?;
    args.get(position + 1).cloned().ok_or_else(|| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("missing value for {name}"),
        )
    })
}

fn parse_usize(args: &[String], name: &str) -> Result<usize, io::Error> {
    value(args, name)?.parse::<usize>().map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid {name}: {error}"),
        )
    })
}

fn parse_u64(args: &[String], name: &str) -> Result<u64, io::Error> {
    value(args, name)?.parse::<u64>().map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid {name}: {error}"),
        )
    })
}

fn parse_args(args: &[String]) -> Result<RunConfig, Box<dyn Error>> {
    let phase = value(args, "--phase")?.parse::<Phase>()?;
    let label = value(args, "--label")?.parse::<Label>()?;
    let treatment = value(args, "--treatment")?.parse::<Treatment>()?;
    if treatment != treatment_for(phase, label) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "treatment does not match phase/label mapping",
        )
        .into());
    }
    let block = parse_usize(args, "--block")?;
    let period = parse_usize(args, "--period")?;
    if block == 0 || !(1..=4).contains(&period) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "block must be nonzero and period must be in 1..=4",
        )
        .into());
    }
    let experiment = ExperimentConfig::new(
        parse_usize(args, "--callers")?,
        parse_usize(args, "--waiter-cap")?,
        parse_usize(args, "--origin-cap")?,
        parse_usize(args, "--max-attempts")?,
        parse_usize(args, "--retry-tokens")?,
        parse_u64(args, "--work-iters")?,
    )?;
    Ok(RunConfig {
        phase,
        block,
        period,
        label,
        treatment,
        seed: parse_u64(args, "--seed")?,
        key_digest: parse_u64(args, "--key-digest")?,
        experiment,
        logical_path: PathBuf::from(value(args, "--logical")?),
        attempt_path: PathBuf::from(value(args, "--attempts")?),
    })
}

fn measure_mean_ns(iterations: u64, repetitions: u64) -> (u64, u64) {
    let started = Instant::now();
    let mut checksum = 0_u64;
    for repetition in 0..repetitions {
        checksum ^= topic28_origin_work(iterations, mix64(repetition.wrapping_add(28)));
    }
    (
        started.elapsed().as_nanos() as u64 / repetitions.max(1),
        checksum,
    )
}

fn calibrate(target_ns: u64, output: &mut impl Write) -> io::Result<()> {
    if target_ns == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "calibration target must be nonzero",
        ));
    }
    let mut iterations = 1_024_u64;
    // Find an upper bracket with 16 repetitions, apply four proportional
    // corrections using 128 repetitions, then report a 512-repetition mean.
    // No acceptance tolerance compares the final mean with `target_ns`.
    while measure_mean_ns(iterations, 16).0 < target_ns {
        iterations = iterations
            .checked_mul(2)
            .ok_or_else(|| io::Error::other("calibration iteration overflow"))?;
    }
    for _ in 0..4 {
        let (mean_ns, _) = measure_mean_ns(iterations, 128);
        iterations =
            (u128::from(iterations) * u128::from(target_ns) / u128::from(mean_ns.max(1))) as u64;
        iterations = iterations.max(1);
    }
    let (mean_ns, checksum) = measure_mean_ns(iterations, 512);
    writeln!(output, "{iterations},{mean_ns},{checksum}")
}

fn self_check_config(
    treatment: Treatment,
    callers: usize,
    waiter_cap: usize,
    retry_tokens: usize,
    seed: u64,
) -> RunConfig {
    let phase = if treatment == Treatment::Naive {
        Phase::Main
    } else {
        Phase::Aa
    };
    RunConfig {
        phase,
        block: 1,
        period: 1,
        label: Label::A,
        treatment,
        seed,
        key_digest: mix64(0x0074_6f70_6963_3238),
        experiment: ExperimentConfig::new(callers, waiter_cap, 4, 3, retry_tokens, 256)
            .expect("self-check configuration is valid"),
        logical_path: PathBuf::new(),
        attempt_path: PathBuf::new(),
    }
}

fn self_check(output: &mut impl Write) -> Result<(), Box<dyn Error>> {
    let naive = self_check_config(Treatment::Naive, 8, 8, 2, 1);
    let naive_receipt = run_wave(&naive)?;
    verify_counts(&naive, &naive_receipt)?;
    if naive_receipt.attempts.len() != 24
        || naive_receipt
            .logical
            .iter()
            .filter(|record| record.status == "completed")
            .count()
            != 8
    {
        return Err(io::Error::other("naive N=8 self-check failed").into());
    }

    let controlled = self_check_config(Treatment::Controlled, 8, 4, 2, 2);
    let controlled_receipt = run_wave(&controlled)?;
    verify_counts(&controlled, &controlled_receipt)?;
    if controlled_receipt.attempts.len() != 3
        || controlled_receipt
            .logical
            .iter()
            .filter(|record| record.status == "completed")
            .count()
            != 4
        || controlled_receipt
            .logical
            .iter()
            .filter(|record| record.status == "shed")
            .count()
            != 4
    {
        return Err(io::Error::other("controlled N=8/W=4 self-check failed").into());
    }

    let exhausted = self_check_config(Treatment::Controlled, 8, 4, 1, 3);
    let exhausted_receipt = run_wave(&exhausted)?;
    verify_counts(&exhausted, &exhausted_receipt)?;
    if exhausted_receipt.attempts.len() != 2
        || exhausted_receipt
            .logical
            .iter()
            .filter(|record| record.status == "retry_exhausted")
            .count()
            != 4
    {
        return Err(io::Error::other("Q=1 propagation self-check failed").into());
    }

    // A zero-token budget must exhaust after the first physical attempt
    // without touching the retry-token decrement.
    let zero_tokens = self_check_config(Treatment::Controlled, 8, 4, 0, 4);
    let zero_receipt = run_wave(&zero_tokens)?;
    verify_counts(&zero_tokens, &zero_receipt)?;
    if zero_receipt.attempts.len() != 1
        || zero_receipt
            .logical
            .iter()
            .filter(|record| record.status == "retry_exhausted")
            .count()
            != 4
    {
        return Err(io::Error::other("Q=0 exhaustion self-check failed").into());
    }
    writeln!(output, "self-check: PASS")?;
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    let stdout = io::stdout();
    let mut output = BufWriter::new(stdout.lock());
    if args.len() == 2 && args[1] == "--self-check" {
        self_check(&mut output)?;
    } else if args.len() == 3 && args[1] == "--calibrate" {
        calibrate(args[2].parse()?, &mut output)?;
    } else {
        let config = parse_args(&args)?;
        let receipt = run_wave(&config)?;
        verify_counts(&config, &receipt)?;
        write_receipts(&config, &receipt)?;
        write_csv_row(&mut output, &summary_fields(&config, &receipt))?;
    }
    output.flush()?;
    Ok(())
}
