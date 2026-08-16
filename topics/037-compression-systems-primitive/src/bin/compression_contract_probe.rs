//! Runs deterministic checks for the compression-system contract models.
//!
//! The `verify` command checks raw-block framing, decoder accounting, and
//! fixed-unit read amplification, then prints one `CHECK=PASS` record. The
//! `model` command prints the crate's fixed serial-path example. Invalid
//! arguments and failed checks print an `ERROR` record to standard error and
//! exit with status 2.

use std::env;
use std::process;

use compression_systems_primitive::{
    Codec, CostInputs, DecodeClaim, DecoderBudget, DecoderLedger, ExpansionLimit,
    estimate_serial_path, fixed_unit_read_amplification, parse_lz4_raw_block,
    select_with_raw_fallback,
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
                .unwrap_or("compression-contract-probe")
        )),
    }
}

fn verify() -> Result<(), String> {
    let original = [b'a'; 1_024];
    let stored = select_with_raw_fallback(&original, Codec::Lz4RawBlock, &[0; 100], 32)
        .map_err(|error| error.to_string())?;
    let block = parse_lz4_raw_block(&stored.bytes()[1..]).map_err(|error| error.to_string())?;
    if block.decoded_len != 1_024 || block.payload.len() != 100 {
        return Err("LZ4 raw-block wrapper changed".to_owned());
    }

    let budget = DecoderBudget {
        max_input_bytes: 128,
        max_output_bytes: 1_024,
        max_window_bytes: 1 << 20,
        max_memory_bytes: 1 << 20,
        max_units: 4,
        max_work: 10_000,
        max_expansion: Some(ExpansionLimit {
            output: 8,
            input: 1,
        }),
    };
    let ledger = DecoderLedger::default()
        .try_admit(
            budget,
            DecodeClaim {
                input_bytes: 128,
                output_bytes: 1_024,
                window_bytes: 64 << 10,
                memory_bytes: 64 << 10,
                work: 500,
            },
        )
        .map_err(|error| error.to_string())?;
    if (ledger.input_bytes(), ledger.output_bytes(), ledger.units()) != (128, 1_024, 1) {
        return Err("decoder accounting changed".to_owned());
    }

    let read = fixed_unit_read_amplification(10_000, 4_096, 4_095, 2)
        .map_err(|error| error.to_string())?;
    if (read.decoded_bytes, read.units_touched) != (8_192, 2) {
        return Err("read-amplification model changed".to_owned());
    }

    println!(
        "CHECK=PASS stored_codec={:?} stored_bytes={} budget_output={} read_decoded_bytes={}",
        stored.codec(),
        stored.bytes().len(),
        ledger.output_bytes(),
        read.decoded_bytes
    );
    Ok(())
}

fn model() -> Result<(), String> {
    let estimate = estimate_serial_path(CostInputs {
        original_bytes: 1_000_000,
        encoded_bytes: 400_000,
        io_bytes_per_second: 100_000_000,
        codec_bytes_per_second: 500_000_000,
        fixed_codec_ns: 20_000,
    })
    .map_err(|error| error.to_string())?;
    println!(
        "raw_ns={} compressed_ns={} saved_bytes={} compression_wins={}",
        estimate.raw_ns, estimate.compressed_ns, estimate.saved_bytes, estimate.compression_wins
    );
    Ok(())
}
