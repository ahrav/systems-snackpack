//! Measures nonblocking admission to one FCFS worker behind a bounded queue.
//!
//! Each request has an intended offset from one process origin. The producer
//! waits for that absolute deadline, attempts admission once, and records a
//! rejection instead of waiting when the queue is full. Normal mode writes one
//! summary CSV row and a raw CSV row for every completed or rejected request.

use queueing_service_design::{ExperimentConfig, Mode, mix64, service_factor_x4, work_iterations};
use std::env;
use std::error::Error;
use std::fs::File;
use std::hint::black_box;
use std::io::{self, BufWriter, Write};
use std::path::PathBuf;
use std::sync::mpsc::{TrySendError, sync_channel};
use std::thread;
use std::time::{Duration, Instant};

/// Runs the calibrated service-work loop retained for code-generation checks.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic27_do_work(iterations: u64, seed: u64) -> u64 {
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

#[derive(Clone, Debug)]
struct RunConfig {
    experiment: ExperimentConfig,
    mode: Mode,
    label: String,
    phase: String,
    block: u64,
    period: u64,
    seed: u64,
    raw_path: PathBuf,
}

struct Job {
    id: usize,
    intended_ns: u64,
    admitted_ns: u64,
    iterations: u64,
    factor_x4: u64,
    seed: u64,
}

struct Completion {
    id: usize,
    intended_ns: u64,
    admitted_ns: u64,
    service_start_ns: u64,
    completion_ns: u64,
    wait_ns: u64,
    service_ns: u64,
    factor_x4: u64,
    checksum: u64,
}

fn parse_args() -> Result<RunConfig, Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    let value = |name: &str| -> Result<String, io::Error> {
        let position = args
            .iter()
            .position(|argument| argument == name)
            .ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidInput, format!("missing {name}"))
            })?;
        args.get(position + 1).cloned().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("missing value for {name}"),
            )
        })
    };
    let parse_u64 = |name: &str| -> Result<u64, io::Error> {
        value(name)?.parse::<u64>().map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("invalid {name}: {error}"),
            )
        })
    };

    let mode = value("--mode")?.parse::<Mode>()?;
    let label = value("--label")?;
    if label != "A" && label != "B" {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "label must be A or B").into());
    }
    let phase = value("--phase")?;
    if phase != "main" && phase != "aa" {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "phase must be main or aa").into());
    }
    let expected_mode = if phase == "main" && label == "B" {
        Mode::Variable
    } else {
        Mode::Fixed
    };
    if mode != expected_mode {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "mode does not match the phase and label treatment mapping",
        )
        .into());
    }
    let block = parse_u64("--block")?;
    let period = parse_u64("--period")?;
    if block == 0 || !(1..=4).contains(&period) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "block must be nonzero and period must be in 1..=4",
        )
        .into());
    }
    let requests = usize::try_from(parse_u64("--requests")?)?;
    let queue_capacity = usize::try_from(parse_u64("--queue-cap")?)?;
    let base_iterations = parse_u64("--base-iters")?;
    let interval_ns = parse_u64("--interval-ns")?;
    let experiment = ExperimentConfig::new(requests, queue_capacity, base_iterations, interval_ns)?;

    Ok(RunConfig {
        experiment,
        mode,
        label,
        phase,
        block,
        period,
        seed: parse_u64("--seed")?,
        raw_path: PathBuf::from(value("--raw")?),
    })
}

fn measure_mean_ns(iterations: u64, repetitions: u64) -> (u64, u64) {
    let start = Instant::now();
    let mut checksum = 0_u64;
    for repetition in 0..repetitions {
        checksum ^= topic27_do_work(iterations, mix64(repetition.wrapping_add(17)));
    }
    let elapsed_ns = start.elapsed().as_nanos() as u64;
    (elapsed_ns / repetitions.max(1), checksum)
}

fn calibrate(target_ns: u64, output: &mut impl Write) -> io::Result<()> {
    if target_ns == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "calibration target must be nonzero",
        ));
    }
    let mut iterations = 1_024_u64;
    while measure_mean_ns(iterations, 16).0 < target_ns {
        iterations = iterations
            .checked_mul(2)
            .ok_or_else(|| io::Error::other("calibration iteration overflow"))?;
    }
    for _ in 0..4 {
        let (mean_ns, _) = measure_mean_ns(iterations, 128);
        let scaled =
            (u128::from(iterations) * u128::from(target_ns) / u128::from(mean_ns.max(1))) as u64;
        iterations = scaled.max(4);
        iterations -= iterations % 4;
        if iterations == 0 {
            iterations = 4;
        }
    }
    let (mean_ns, checksum) = measure_mean_ns(iterations, 512);
    writeln!(output, "{iterations},{mean_ns},{checksum}")
}

fn relative_ns(origin: Instant, now: Instant) -> u64 {
    now.saturating_duration_since(origin).as_nanos() as u64
}

fn wait_until(deadline: Instant) {
    // Avoid adding sleep granularity to the measured arrival-schedule lag.
    while Instant::now() < deadline {
        std::hint::spin_loop();
    }
}

fn percentile(values: &[u64], percentile: f64) -> u64 {
    if values.is_empty() {
        return 0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_unstable();
    let rank = ((percentile * sorted.len() as f64).ceil() as usize).max(1) - 1;
    sorted[rank.min(sorted.len() - 1)]
}

fn mean(values: &[u64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    values.iter().map(|&value| value as f64).sum::<f64>() / values.len() as f64
}

fn run(config: &RunConfig, output: &mut impl Write) -> Result<(), Box<dyn Error>> {
    let experiment = config.experiment;
    let mut warmup_checksum = 0_u64;
    for repetition in 0..64_u64 {
        warmup_checksum ^= topic27_do_work(
            experiment.base_iterations(),
            mix64(config.seed ^ repetition),
        );
    }
    black_box(warmup_checksum);

    let experiment_origin = Instant::now()
        .checked_add(Duration::from_millis(50))
        .ok_or_else(|| io::Error::other("experiment origin is outside Instant range"))?;
    let worker_origin = experiment_origin;
    let (sender, receiver) = sync_channel::<Job>(experiment.queue_capacity());
    let worker = thread::spawn(move || {
        let mut completed = Vec::new();
        while let Ok(job) = receiver.recv() {
            let service_start = Instant::now();
            let service_start_ns = relative_ns(worker_origin, service_start);
            let checksum = topic27_do_work(job.iterations, job.seed);
            let completion = Instant::now();
            let completion_ns = relative_ns(worker_origin, completion);
            completed.push(Completion {
                id: job.id,
                intended_ns: job.intended_ns,
                admitted_ns: job.admitted_ns,
                service_start_ns,
                completion_ns,
                wait_ns: service_start_ns.saturating_sub(job.admitted_ns),
                service_ns: completion.duration_since(service_start).as_nanos() as u64,
                factor_x4: job.factor_x4,
                checksum,
            });
        }
        completed
    });

    let requests = experiment.requests();
    let mut actual_arrival = vec![0_u64; requests];
    let mut admitted_at = vec![None::<u64>; requests];
    let mut offered_factor_x4 = vec![0_u64; requests];
    // Keep rejection accounting directly countable without adding bit packing
    // to the queue probe.
    let mut rejected = vec![0_u8; requests];

    for request_id in 0..requests {
        let intended_ns = (request_id as u64).saturating_mul(experiment.interval_ns());
        let factor_x4 = service_factor_x4(config.mode, request_id, config.seed);
        offered_factor_x4[request_id] = factor_x4;
        let iterations = work_iterations(experiment.base_iterations(), factor_x4)
            .ok_or_else(|| io::Error::other("validated work iteration conversion failed"))?;
        let mut job = Job {
            id: request_id,
            intended_ns,
            admitted_ns: 0,
            iterations,
            factor_x4,
            seed: mix64(config.seed ^ request_id as u64),
        };
        let deadline = experiment_origin
            .checked_add(Duration::from_nanos(intended_ns))
            .ok_or_else(|| io::Error::other("arrival deadline is outside Instant range"))?;
        wait_until(deadline);
        let actual_ns = relative_ns(experiment_origin, Instant::now());
        actual_arrival[request_id] = actual_ns;
        job.admitted_ns = actual_ns;
        // A full queue counts as rejection instead of backpressuring arrivals.
        match sender.try_send(job) {
            Ok(()) => admitted_at[request_id] = Some(actual_ns),
            Err(TrySendError::Full(_)) => rejected[request_id] = 1,
            Err(TrySendError::Disconnected(_)) => {
                return Err(io::Error::other("worker disconnected").into());
            }
        }
    }
    drop(sender);
    let completed = worker
        .join()
        .map_err(|_| io::Error::other("worker panicked"))?;

    let mut completion_by_id = vec![None::<usize>; requests];
    for (index, item) in completed.iter().enumerate() {
        completion_by_id[item.id] = Some(index);
    }
    write_raw(
        config,
        &actual_arrival,
        &offered_factor_x4,
        &completed,
        &completion_by_id,
    )?;

    let schedule_lags: Vec<u64> = actual_arrival
        .iter()
        .enumerate()
        .map(|(request_id, &actual)| {
            actual.saturating_sub((request_id as u64).saturating_mul(experiment.interval_ns()))
        })
        .collect();
    let waits: Vec<u64> = completed.iter().map(|item| item.wait_ns).collect();
    let services: Vec<u64> = completed.iter().map(|item| item.service_ns).collect();
    let admitted = admitted_at.iter().filter(|value| value.is_some()).count();
    let rejected_count = rejected.iter().filter(|&&value| value != 0).count();
    if admitted != completed.len() || admitted + rejected_count != requests {
        return Err(io::Error::other(format!(
            "population accounting failed: admitted={admitted} completed={} rejected={rejected_count} requests={requests}",
            completed.len()
        ))
        .into());
    }
    let offered_work_x4 = offered_factor_x4.iter().sum::<u64>();
    let last_completion_ns = completed
        .iter()
        .map(|item| item.completion_ns)
        .max()
        .unwrap_or(0);
    let last_intended_ns = ((requests - 1) as u64).saturating_mul(experiment.interval_ns());
    // Retain the full offered-arrival window when trailing requests are rejected.
    let duration_ns = last_completion_ns.max(last_intended_ns.saturating_add(1));
    let goodput_rps = completed.len() as f64 * 1_000_000_000.0 / duration_ns as f64;
    let service_mean = mean(&services);
    let service_variance = if services.is_empty() {
        0.0
    } else {
        services
            .iter()
            .map(|&value| {
                let delta = value as f64 - service_mean;
                delta * delta
            })
            .sum::<f64>()
            / services.len() as f64
    };
    let service_cs2 = if service_mean > 0.0 {
        service_variance / (service_mean * service_mean)
    } else {
        0.0
    };
    let checksum = completed
        .iter()
        .fold(0_u64, |accumulator, item| accumulator ^ item.checksum);
    let pid = std::process::id();

    let summary = [
        pid.to_string(),
        config.label.clone(),
        config.phase.clone(),
        config.block.to_string(),
        config.period.to_string(),
        config.mode.as_str().to_string(),
        config.seed.to_string(),
        requests.to_string(),
        experiment.queue_capacity().to_string(),
        experiment.base_iterations().to_string(),
        experiment.interval_ns().to_string(),
        offered_work_x4.to_string(),
        admitted.to_string(),
        completed.len().to_string(),
        rejected_count.to_string(),
        format!("{:.9}", rejected_count as f64 * 100.0 / requests as f64),
        duration_ns.to_string(),
        format!("{goodput_rps:.3}"),
        format!("{:.3}", mean(&schedule_lags)),
        percentile(&schedule_lags, 0.50).to_string(),
        percentile(&schedule_lags, 0.99).to_string(),
        format!("{:.3}", mean(&waits)),
        percentile(&waits, 0.50).to_string(),
        percentile(&waits, 0.99).to_string(),
        format!("{service_mean:.3}"),
        percentile(&services, 0.50).to_string(),
        percentile(&services, 0.99).to_string(),
        format!("{service_cs2:.6}"),
        checksum.to_string(),
        config.raw_path.display().to_string(),
    ]
    .join(",");
    writeln!(output, "{summary}")?;
    Ok(())
}

fn write_raw(
    config: &RunConfig,
    actual_arrival: &[u64],
    offered_factor_x4: &[u64],
    completed: &[Completion],
    completion_by_id: &[Option<usize>],
) -> io::Result<()> {
    let file = File::create(&config.raw_path)?;
    let mut output = BufWriter::new(file);
    writeln!(
        output,
        "id,pid,label,phase,block,period,mode,intended_ns,actual_arrival_ns,status,admitted_ns,service_start_ns,completion_ns,wait_ns,service_ns,sojourn_from_intended_ns,factor_x4,checksum"
    )?;
    let pid = std::process::id();
    for request_id in 0..config.experiment.requests() {
        let fields = if let Some(index) = completion_by_id[request_id] {
            let item = &completed[index];
            [
                request_id.to_string(),
                pid.to_string(),
                config.label.clone(),
                config.phase.clone(),
                config.block.to_string(),
                config.period.to_string(),
                config.mode.as_str().to_string(),
                item.intended_ns.to_string(),
                actual_arrival[request_id].to_string(),
                "completed".to_string(),
                item.admitted_ns.to_string(),
                item.service_start_ns.to_string(),
                item.completion_ns.to_string(),
                item.wait_ns.to_string(),
                item.service_ns.to_string(),
                item.completion_ns
                    .saturating_sub(item.intended_ns)
                    .to_string(),
                item.factor_x4.to_string(),
                item.checksum.to_string(),
            ]
        } else {
            [
                request_id.to_string(),
                pid.to_string(),
                config.label.clone(),
                config.phase.clone(),
                config.block.to_string(),
                config.period.to_string(),
                config.mode.as_str().to_string(),
                (request_id as u64)
                    .saturating_mul(config.experiment.interval_ns())
                    .to_string(),
                actual_arrival[request_id].to_string(),
                "rejected".to_string(),
                String::new(),
                String::new(),
                String::new(),
                String::new(),
                String::new(),
                String::new(),
                offered_factor_x4[request_id].to_string(),
                String::new(),
            ]
        };
        writeln!(output, "{}", fields.join(","))?;
    }
    output.flush()
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().collect();
    let stdout = io::stdout();
    let mut output = BufWriter::new(stdout.lock());
    if args.len() == 3 && args[1] == "--calibrate" {
        calibrate(args[2].parse()?, &mut output)?;
    } else {
        let config = parse_args()?;
        run(&config, &mut output)?;
    }
    output.flush()?;
    Ok(())
}
