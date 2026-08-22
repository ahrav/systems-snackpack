//! Fresh-process timing probe for the three Topic 43 lookup shapes.
//!
//! The process reports setup, warmup, and timed intervals separately. The
//! harness fixes the seed, iteration count, CPU, and process order. Timings
//! compare these exact functions on one host; they make no security claim.

use std::env;
use std::hint::black_box;
use std::process::ExitCode;
use std::time::Instant;

use spectre_era_performance_tradeoffs::{
    LookupMode, lookup, mode_name, topic43_speculation_barrier,
};

const WORDS: usize = 4096;
const DEFAULT_ITERATIONS: u64 = 2_000_000;
const WARMUP_ITERATIONS: u64 = 200_000;
const DEFAULT_SEED: u64 = 0x243f_6a88_85a3_08d3;

fn parse_mode(value: &str) -> Result<LookupMode, String> {
    match value {
        "plain" => Ok(LookupMode::Plain),
        "mask" => Ok(LookupMode::Mask),
        "barrier" => Ok(LookupMode::Barrier),
        _ => Err(format!("unknown mode: {value}")),
    }
}
fn parse_args() -> Result<(LookupMode, u64, u64), String> {
    let mut mode = None;
    let mut iterations = DEFAULT_ITERATIONS;
    let mut seed = DEFAULT_SEED;
    let mut args = env::args().skip(1);
    while let Some(argument) = args.next() {
        match argument.as_str() {
            "--mode" => mode = Some(parse_mode(&args.next().ok_or("--mode needs a value")?)?),
            "--iterations" => {
                iterations = args
                    .next()
                    .ok_or("--iterations needs a value")?
                    .parse()
                    .map_err(|_| "--iterations must be an integer")?;
            }
            "--seed" => {
                let value = args.next().ok_or("--seed needs a value")?;
                seed = value
                    .strip_prefix("0x")
                    .map_or_else(|| value.parse(), |hex| u64::from_str_radix(hex, 16))
                    .map_err(|_| "--seed must be an integer or 0x-prefixed hex")?;
            }
            _ => return Err(format!("unknown argument: {argument}")),
        }
    }
    if iterations == 0 {
        return Err("--iterations must be positive".into());
    }
    Ok((mode.ok_or("--mode is required")?, iterations, seed))
}

fn next_state(state: &mut u64) -> u64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    *state
}

fn run(mode: LookupMode, words: &[u64], iterations: u64, seed: u64) -> u64 {
    let mut state = seed;
    let mut checksum = 0_u64;
    for _ in 0..iterations {
        let index = (next_state(&mut state) as usize) & (WORDS * 2 - 1);
        checksum = checksum.wrapping_add(black_box(lookup(mode, black_box(words), index)));
    }
    black_box(checksum)
}

fn main() -> ExitCode {
    let process_start = Instant::now();
    let (mode, iterations, seed) = match parse_args() {
        Ok(parsed) => parsed,
        Err(error) => {
            eprintln!("{error}");
            return ExitCode::from(2);
        }
    };

    // Keep the exact standalone barrier symbol in the release binary for the
    // generated-code receipt. This one setup call is outside both the warmup
    // and timed intervals.
    topic43_speculation_barrier();

    let mut state = seed ^ 0xa409_3822_299f_31d0;
    let words: Vec<u64> = (0..WORDS).map(|_| next_state(&mut state)).collect();
    let setup_ns = process_start.elapsed().as_nanos();

    let warmup_start = Instant::now();
    let warmup_checksum = run(mode, &words, WARMUP_ITERATIONS, seed);
    let warmup_ns = warmup_start.elapsed().as_nanos();

    let timed_start = Instant::now();
    let checksum = run(mode, &words, iterations, seed);
    let timed_ns = timed_start.elapsed().as_nanos();

    println!(
        "{{\"mode\":\"{}\",\"iterations\":{},\"seed\":{},\"setup_ns\":{},\"warmup_iterations\":{},\"warmup_ns\":{},\"timed_ns\":{},\"warmup_checksum\":{},\"checksum\":{}}}",
        mode_name(mode),
        iterations,
        seed,
        setup_ns,
        WARMUP_ITERATIONS,
        warmup_ns,
        timed_ns,
        warmup_checksum,
        checksum
    );
    ExitCode::SUCCESS
}
