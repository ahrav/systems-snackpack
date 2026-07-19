//! Times both rank representations on identical deterministic point queries.
//!
//! Each `--run` invocation constructs both indexes and the query sequence,
//! warms the compact loop and then the prefix loop, and times both query loops
//! in the requested order. The `compact_ns` and `prefix_ns` intervals include
//! the query loop, `rank1` calls, black-box barriers, and checksum accumulation.
//! They exclude input generation, index construction, query construction, and
//! warmup; separate fields report those stages. Timed positions are in
//! `[0, N)`; correctness checks cover the valid endpoint at `N` separately.
//!
//! The companion process runner launches 12 fresh processes, alternates the
//! measured order, and treats each within-process pair as one replication unit.
//! Inner-loop queries define the workload; they are not independent samples.
//! `main_elapsed_ns` starts at entry to `run` and stops before result printing.
//! The runner's `external_wall_ns` also covers parent-shell command
//! substitution, `taskset` launch, process startup and teardown, and captured
//! output transfer back to the shell.

use std::{env, hint::black_box, process, time::Instant};

use systems_snackpack_topic_009::{
    CompactRank, PrefixRank, inspect_compact_rank, inspect_prefix_rank,
};

const DEFAULT_BIT_POWER: usize = 26;
const DEFAULT_QUERIES: usize = 4_000_000;
const WARMUP_QUERIES: usize = 262_144;

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn parse_usize(raw: Option<&String>, default: usize, label: &str) -> usize {
    raw.map_or(default, |value| {
        value.parse::<usize>().unwrap_or_else(|error| {
            eprintln!("invalid {label} {value:?}: {error}");
            process::exit(2);
        })
    })
}

fn make_words(bit_len: usize) -> Vec<u64> {
    let mut state = 0x243f_6a88_85a3_08d3_u64;
    (0..bit_len / 64).map(|_| splitmix64(&mut state)).collect()
}

fn make_queries(bit_len: usize, count: usize) -> Vec<usize> {
    // A power-of-two length lets the mask reduce `u64` values without modulo bias.
    assert!(bit_len.is_power_of_two());
    let mut state = 0x1319_8a2e_0370_7344_u64;
    (0..count)
        .map(|_| (splitmix64(&mut state) as usize) & (bit_len - 1))
        .collect()
}

struct Prepared {
    compact: CompactRank,
    prefix: PrefixRank,
    queries: Vec<usize>,
    dataset_ns: u128,
    input_clone_ns: u128,
    compact_build_ns: u128,
    prefix_build_ns: u128,
    query_build_ns: u128,
}

fn prepare(bit_power: usize, query_count: usize) -> Prepared {
    // `2^6` is one complete word; `2^31` is the largest power of two below the
    // `u32` cumulative-count limit.
    if !(6..=31).contains(&bit_power) {
        eprintln!("bit power must be between 6 and 31, got {bit_power}");
        process::exit(2);
    }
    if query_count == 0 {
        eprintln!("query count must be positive");
        process::exit(2);
    }
    let bit_len = 1_usize << bit_power;

    let started = Instant::now();
    let words = make_words(bit_len);
    let dataset_ns = started.elapsed().as_nanos();

    let started = Instant::now();
    let compact_words = words.clone();
    let input_clone_ns = started.elapsed().as_nanos();

    let started = Instant::now();
    let prefix = PrefixRank::from_words(&words).unwrap_or_else(|error| {
        eprintln!("failed to build prefix oracle: {error}");
        process::exit(1);
    });
    let prefix_build_ns = started.elapsed().as_nanos();
    drop(words);

    let started = Instant::now();
    let compact = CompactRank::from_words(compact_words).unwrap_or_else(|error| {
        eprintln!("failed to build compact rank directory: {error}");
        process::exit(1);
    });
    let compact_build_ns = started.elapsed().as_nanos();

    let started = Instant::now();
    let queries = make_queries(bit_len, query_count);
    let query_build_ns = started.elapsed().as_nanos();

    Prepared {
        compact,
        prefix,
        queries,
        dataset_ns,
        input_clone_ns,
        compact_build_ns,
        prefix_build_ns,
        query_build_ns,
    }
}

fn time_compact(index: &CompactRank, queries: &[usize]) -> (u128, u64) {
    let started = Instant::now();
    let mut checksum = 0_u64;
    for &pos in queries {
        let rank = index
            .rank1(black_box(pos))
            .expect("generated query is in bounds");
        checksum = checksum.wrapping_add(black_box(rank) as u64);
    }
    (started.elapsed().as_nanos(), black_box(checksum))
}

fn time_prefix(index: &PrefixRank, queries: &[usize]) -> (u128, u64) {
    let started = Instant::now();
    let mut checksum = 0_u64;
    for &pos in queries {
        let rank = index
            .rank1(black_box(pos))
            .expect("generated query is in bounds");
        checksum = checksum.wrapping_add(black_box(rank) as u64);
    }
    (started.elapsed().as_nanos(), black_box(checksum))
}

fn verify(bit_power: usize) {
    let main_started = Instant::now();
    let prepared = prepare(bit_power, 16_384);
    let bit_len = prepared.compact.len();
    for pos in 0..=bit_len {
        assert_eq!(
            prepared.compact.rank1(pos),
            prepared.prefix.rank1(pos),
            "rank mismatch at position {pos}"
        );
    }
    let probe = bit_len / 3;
    assert_eq!(
        inspect_compact_rank(&prepared.compact, probe),
        inspect_prefix_rank(&prepared.prefix, probe)
    );
    println!(
        "VERIFY pid={} bits={} positions_checked={} ones={} compact_bytes={} prefix_bytes={} main_elapsed_ns={}",
        process::id(),
        bit_len,
        bit_len + 1,
        prepared.compact.ones(),
        prepared.compact.logical_bytes(),
        prepared.prefix.logical_bytes(),
        main_started.elapsed().as_nanos()
    );
}

fn run(order: &str, query_count: usize, bit_power: usize, pair: usize) {
    let main_started = Instant::now();
    let prepared = prepare(bit_power, query_count);
    for &pos in prepared.queries.iter().take(8192) {
        assert_eq!(prepared.compact.rank1(pos), prepared.prefix.rank1(pos));
    }

    let warmup_count = prepared.queries.len().min(WARMUP_QUERIES);
    let warmup = &prepared.queries[..warmup_count];
    let warmup_started = Instant::now();
    let (compact_warmup_ns, compact_warmup_sum) = time_compact(&prepared.compact, warmup);
    let (prefix_warmup_ns, prefix_warmup_sum) = time_prefix(&prepared.prefix, warmup);
    let warmup_ns = warmup_started.elapsed().as_nanos();
    assert_eq!(compact_warmup_sum, prefix_warmup_sum);

    let ((compact_ns, compact_sum), (prefix_ns, prefix_sum)) = match order {
        "compact-prefix" => (
            time_compact(&prepared.compact, &prepared.queries),
            time_prefix(&prepared.prefix, &prepared.queries),
        ),
        "prefix-compact" => {
            let prefix = time_prefix(&prepared.prefix, &prepared.queries);
            let compact = time_compact(&prepared.compact, &prepared.queries);
            (compact, prefix)
        }
        _ => {
            eprintln!("order must be compact-prefix or prefix-compact, got {order:?}");
            process::exit(2);
        }
    };
    assert_eq!(compact_sum, prefix_sum);

    let probe = prepared.queries[0];
    assert_eq!(
        black_box(inspect_compact_rank(&prepared.compact, probe)),
        black_box(inspect_prefix_rank(&prepared.prefix, probe))
    );

    println!(
        "RESULT pid={} pair={} order={} bits={} ones={} queries={} warmup_queries={} dataset_ns={} input_clone_ns={} compact_build_ns={} prefix_build_ns={} query_build_ns={} warmup_ns={} compact_warmup_ns={} prefix_warmup_ns={} compact_ns={} prefix_ns={} compact_ns_per_query={:.9} prefix_ns_per_query={:.9} checksum={} compact_bytes={} prefix_bytes={} main_elapsed_ns={}",
        process::id(),
        pair,
        order,
        prepared.compact.len(),
        prepared.compact.ones(),
        query_count,
        warmup_count,
        prepared.dataset_ns,
        prepared.input_clone_ns,
        prepared.compact_build_ns,
        prepared.prefix_build_ns,
        prepared.query_build_ns,
        warmup_ns,
        compact_warmup_ns,
        prefix_warmup_ns,
        compact_ns,
        prefix_ns,
        compact_ns as f64 / query_count as f64,
        prefix_ns as f64 / query_count as f64,
        compact_sum,
        prepared.compact.logical_bytes(),
        prepared.prefix.logical_bytes(),
        main_started.elapsed().as_nanos()
    );
}

fn usage() -> ! {
    eprintln!(
        "usage: succinct_rank --verify [bit_power] | --run <compact-prefix|prefix-compact> [queries] [bit_power] [pair]"
    );
    process::exit(2);
}

fn main() {
    let args = env::args().collect::<Vec<_>>();
    match args.get(1).map(String::as_str) {
        Some("--verify") => verify(parse_usize(
            args.get(2),
            DEFAULT_BIT_POWER.min(20),
            "bit power",
        )),
        Some("--run") => {
            let order = args.get(2).map(String::as_str).unwrap_or_else(|| usage());
            let query_count = parse_usize(args.get(3), DEFAULT_QUERIES, "query count");
            let bit_power = parse_usize(args.get(4), DEFAULT_BIT_POWER, "bit power");
            let pair = parse_usize(args.get(5), 0, "pair");
            if pair == 0 {
                eprintln!("pair must be positive");
                process::exit(2);
            }
            run(order, query_count, bit_power, pair);
        }
        _ => usage(),
    }
}
