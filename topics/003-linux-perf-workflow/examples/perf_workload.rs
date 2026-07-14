//! Runs the deterministic phase workload under tools such as `perf stat`.

use std::{env, process::ExitCode};
use systems_snackpack_topic_003::{PhaseConfig, run_alternating};

const DEFAULT_ROUNDS: u32 = 400;
const DEFAULT_ITERATIONS_PER_PHASE: u64 = 250_000;
const SEED: u64 = 0x1234_5678_9abc_def0;

fn parse<T>(value: Option<String>, default: T, name: &str) -> Result<T, String>
where
    T: std::str::FromStr,
{
    match value {
        Some(value) => value
            .parse()
            .map_err(|_| format!("invalid {name}: {value}")),
        None => Ok(default),
    }
}

fn run() -> Result<(), String> {
    let mut arguments = env::args().skip(1);
    let rounds = parse(arguments.next(), DEFAULT_ROUNDS, "round count")?;
    let iterations = parse(
        arguments.next(),
        DEFAULT_ITERATIONS_PER_PHASE,
        "phase iteration count",
    )?;
    if let Some(argument) = arguments.next() {
        return Err(format!("unexpected argument: {argument}"));
    }

    let result = run_alternating(PhaseConfig::new(rounds, iterations, SEED));
    println!(
        "checksum={:#018x} completed_iterations={}",
        result.checksum, result.completed_iterations
    );
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("usage: perf_workload [rounds] [iterations_per_phase]");
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
