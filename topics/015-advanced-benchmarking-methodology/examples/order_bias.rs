//! Emits one CSV header and two timed checksum records for one `AB` or `BA`
//! process.
//!
//! The positional argument selects the emitted order and the label assigned to
//! each identical timed call. It does not change the timed workload. An
//! eviction-buffer traversal precedes position 1, while no traversal separates
//! positions 1 and 2.

use advanced_benchmarking_methodology::measure_pair;
use std::env;
use std::hint::black_box;
use std::process;

const MIB: usize = 1024 * 1024;
const DEFAULT_TARGET_MIB: usize = 32;
const DEFAULT_THRASH_MIB: usize = 256;

// Reads a positive MiB count, using `default` only when the variable is absent.
// Invalid UTF-8, a non-positive `usize`, or a byte-size overflow exits with
// status 2.
fn mib_from_env(name: &str, default: usize) -> usize {
    match env::var(name) {
        Ok(raw) => match raw.parse::<usize>() {
            Ok(value) if value > 0 && value <= usize::MAX / MIB => value,
            _ => {
                eprintln!("{name} must be a positive integer number of MiB");
                process::exit(2);
            }
        },
        Err(env::VarError::NotPresent) => default,
        Err(env::VarError::NotUnicode(_)) => {
            eprintln!("{name} must be valid UTF-8");
            process::exit(2);
        }
    }
}

// Rewrites every eviction word and returns a data-dependent XOR consumed by
// `black_box`.
fn thrash_cache(words: &mut [u64]) -> u64 {
    let mut checksum = 0u64;
    for (index, word) in words.iter_mut().enumerate() {
        let value = word.wrapping_add(
            (index as u64)
                .wrapping_mul(0x9e37_79b9_7f4a_7c15)
                .rotate_left((index & 63) as u32),
        );
        *word = value;
        checksum ^= value;
    }
    checksum
}

fn main() {
    let order = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: order_bias AB|BA");
        process::exit(2);
    });
    let labels = match order.as_str() {
        "AB" => ["A", "B"],
        "BA" => ["B", "A"],
        _ => {
            eprintln!("order must be AB or BA");
            process::exit(2);
        }
    };

    let target_bytes = mib_from_env("BENCH_TARGET_MIB", DEFAULT_TARGET_MIB) * MIB;
    let thrash_bytes = mib_from_env("BENCH_THRASH_MIB", DEFAULT_THRASH_MIB) * MIB;
    let target_words = target_bytes / std::mem::size_of::<u64>();
    let thrash_words = thrash_bytes / std::mem::size_of::<u64>();

    let data: Vec<u64> = (0..target_words)
        .map(|index| {
            (index as u64)
                .wrapping_mul(0xd6e8_feb8_6659_fd93)
                .rotate_left((index & 63) as u32)
        })
        .collect();
    let mut eviction = vec![0u64; thrash_words];

    // Position 1 follows the eviction traversal; no traversal separates the
    // two timed positions.
    black_box(thrash_cache(black_box(&mut eviction)));

    let pair = measure_pair(&data);
    let pid = process::id();
    println!("pid,order,position,label,elapsed_ns,checksum,target_bytes,thrash_bytes");
    println!(
        "{pid},{order},1,{},{},{},{target_bytes},{thrash_bytes}",
        labels[0], pair.first_ns, pair.checksum
    );
    println!(
        "{pid},{order},2,{},{},{},{target_bytes},{thrash_bytes}",
        labels[1], pair.second_ns, pair.checksum
    );
}
