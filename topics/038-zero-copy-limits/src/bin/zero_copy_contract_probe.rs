//! Runs deterministic checks for the copy-avoidance contract models.
//!
//! `verify` checks copy accounting, an unaligned page range, a bounded pipe,
//! and a completion range that crosses the 32-bit identifier wrap. `model`
//! prints the fixed serial-cost and held-memory examples from the topic note.

use std::env;
use std::process;

use zero_copy_limits::{
    CompletionTracker, FilePath, PathCostInputs, TransferCostInputs, compare_transfer_costs,
    file_path_accounting, held_bytes, pages_spanned, splice_pipe_estimate,
};

fn main() {
    if let Err(error) = run() {
        eprintln!("ERROR={error}");
        process::exit(2);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<_> = env::args_os().collect();
    match args.get(1).and_then(|argument| argument.to_str()) {
        Some("verify") if args.len() == 2 => verify(),
        Some("model") if args.len() == 2 => model(),
        _ => Err(format!(
            "usage: {} verify | model",
            args.first()
                .and_then(|argument| argument.to_str())
                .unwrap_or("zero-copy-contract-probe")
        )),
    }
}

fn verify() -> Result<(), String> {
    let bytes = 64 * 1024 * 1024;
    let buffered =
        file_path_accounting(FilePath::Buffered, bytes).map_err(|error| error.to_string())?;
    if buffered.named_payload_copy_bytes != 2 * bytes {
        return Err("buffered copy accounting changed".to_owned());
    }
    if pages_spanned(4095, 2, 4096).map_err(|error| error.to_string())? != 2 {
        return Err("unaligned page-span accounting changed".to_owned());
    }
    let pipe =
        splice_pipe_estimate(bytes, 64 * 1024, 1024 * 1024).map_err(|error| error.to_string())?;
    if pipe.cycles != 1024 || pipe.minimum_splice_calls != 2048 {
        return Err("bounded-pipe accounting changed".to_owned());
    }

    let mut completions = CompletionTracker::with_next_id(u32::MAX);
    let high = completions.submit().map_err(|error| error.to_string())?;
    let zero = completions.submit().map_err(|error| error.to_string())?;
    let reusable = completions.complete_range(u32::MAX, 0);
    if high != u32::MAX || zero != 0 || reusable != [0, u32::MAX] {
        return Err("wrapped completion-range accounting changed".to_owned());
    }

    println!(
        "CHECK=PASS logical_bytes={} buffered_named_copy_bytes={} pipe_cycles={} wrapped_completion=yes",
        bytes, buffered.named_payload_copy_bytes, pipe.cycles
    );
    Ok(())
}

fn model() -> Result<(), String> {
    let bytes = 64 * 1024 * 1024;
    let comparison = compare_transfer_costs(TransferCostInputs {
        baseline: PathCostInputs {
            logical_bytes: bytes,
            payload_copy_passes: 2,
            syscall_count: 128,
            copy_bandwidth_bytes_per_second: 20 * 1024 * 1024 * 1024,
            fixed_syscall_ns: 200,
            other_ns: 0,
        },
        copy_avoiding: PathCostInputs {
            logical_bytes: bytes,
            payload_copy_passes: 0,
            syscall_count: 64,
            copy_bandwidth_bytes_per_second: 20 * 1024 * 1024 * 1024,
            fixed_syscall_ns: 200,
            other_ns: 0,
        },
    })
    .map_err(|error| error.to_string())?;
    let held_5ms = held_bytes(20_000, 64 * 1024, 5_000_000).map_err(|error| error.to_string())?;
    let held_100ms =
        held_bytes(20_000, 64 * 1024, 100_000_000).map_err(|error| error.to_string())?;
    println!(
        "baseline_ns={} copy_avoiding_ns={} held_5ms_bytes={} held_100ms_bytes={}",
        comparison.baseline.total_ns, comparison.copy_avoiding.total_ns, held_5ms, held_100ms
    );
    Ok(())
}
