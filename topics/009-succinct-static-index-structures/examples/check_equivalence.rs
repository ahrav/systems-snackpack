//! Exhaustively compares both rank representations over deterministic input.
//!
//! `check_ns` covers only the comparison of every half-open prefix, including
//! the endpoint. It excludes input generation and index construction and is a
//! correctness diagnostic, not a query-latency measurement.

use std::{env, process, time::Instant};

use systems_snackpack_topic_009::{CompactRank, PrefixRank, dataset_words};

const DEFAULT_BIT_POWER: usize = 20;

fn parse_bit_power() -> usize {
    let raw = env::args().nth(1);
    let bit_power = raw.as_ref().map_or(DEFAULT_BIT_POWER, |value| {
        value.parse::<usize>().unwrap_or_else(|error| {
            eprintln!("invalid bit power {value:?}: {error}");
            process::exit(2);
        })
    });
    // `2^6` is one complete word; `2^31` is the largest power of two below the
    // `u32` cumulative-count limit.
    if !(6..=31).contains(&bit_power) {
        eprintln!("bit power must be between 6 and 31, got {bit_power}");
        process::exit(2);
    }
    bit_power
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let bit_power = parse_bit_power();
    let bit_len = 1_usize << bit_power;
    let words = dataset_words(bit_len);

    let compact = CompactRank::from_words(words.clone())?;
    let prefix = PrefixRank::from_words(&words)?;
    let started = Instant::now();
    for pos in 0..=bit_len {
        let compact_rank = compact.rank1(pos);
        let prefix_rank = prefix.rank1(pos);
        if compact_rank != prefix_rank {
            return Err(format!(
                "rank mismatch at {pos}: compact={compact_rank:?} prefix={prefix_rank:?}"
            )
            .into());
        }
    }

    println!(
        "CHECK bits={} positions_checked={} ones={} compact_bytes={} prefix_bytes={} check_ns={}",
        bit_len,
        bit_len + 1,
        compact.ones(),
        compact.logical_bytes(),
        prefix.logical_bytes(),
        started.elapsed().as_nanos()
    );
    Ok(())
}
