//! Fresh-process correctness and timing probe for topology-controlled byte dictionaries.
//!
//! # Modes
//!
//! `verify` checks the prescribed membership probes against a sorted-key oracle
//! and checks the fixed state, arc, and topology-record counts for both corpora.
//! `calibrate` selects one repetition count for a method and dataset. `process`
//! consumes a frozen tab-separated calibration map and emits one JSON row per
//! dataset for one method process.
//!
//! # Measurement boundary
//!
//! Each row times the repeated lookup loop over 16,384 fixed queries, including
//! loop iteration, `black_box`, lookup calls, and result-checksum arithmetic.
//! Graph construction, correctness checks, the explicit warmup pass,
//! calibration, process startup, and JSON formatting stay outside the interval.
//! The repetition count scales interval duration; its individual lookups are
//! not independent samples. A row from each fresh process is the replication
//! unit for a method-dataset comparison.
//!
//! # Reported size
//!
//! `topology_bytes` counts occupied eight-byte state and arc records. It does
//! not report serialization size, vector capacity, allocator metadata, or
//! resident memory.

use std::env;
use std::fs;
use std::hint::black_box;
use std::process;
use std::time::{Duration, Instant};

use finite_state_transducers_compact_dictionaries::{
    FlatDictionary, benchmark_queries, build_flat_trie, build_minimal_dafsa, opaque_keys,
    retain_inspection_hook, sequence_checksum, shared_keys, topic035_flat_contains,
};

const METHODS: [&str; 2] = ["flat-trie", "minimal-dafsa"];
const DATASETS: [&str; 2] = ["shared", "opaque"];

struct Dataset {
    name: &'static str,
    keys: Vec<Vec<u8>>,
    queries: Vec<Vec<u8>>,
    key_bytes: usize,
    hit_count: usize,
    input_checksum: u64,
    query_checksum: u64,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("ERROR={error}");
        process::exit(2);
    }
}

fn run() -> Result<(), String> {
    retain_linked_code()?;
    let args: Vec<String> = env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("verify") if args.len() == 2 => verify_contract(),
        Some("calibrate") if args.len() == 5 => {
            let method = parse_method(&args[2])?;
            let dataset = make_dataset(parse_dataset(&args[3])?);
            let target_ms = args[4]
                .parse::<u64>()
                .map_err(|_| "target milliseconds must be an integer".to_owned())?;
            let dictionary = build_method(method, &dataset.keys)?;
            verify_dictionary(&dataset, &dictionary)?;
            let repetitions = calibrate(&dictionary, &dataset.queries, target_ms.max(1));
            println!("reps={repetitions}");
            Ok(())
        }
        Some("process") if args.len() == 4 => {
            let method = parse_method(&args[2])?;
            let calibration = fs::read_to_string(&args[3])
                .map_err(|error| format!("read calibration: {error}"))?;
            process_rows(method, &calibration)
        }
        _ => Err(format!(
            "usage: {} verify | calibrate METHOD DATASET TARGET_MS | process METHOD CALIBRATION_TSV",
            args.first().map_or("dictionary-probe", String::as_str)
        )),
    }
}

fn retain_linked_code() -> Result<(), String> {
    let dictionary =
        build_flat_trie(&[b"linked-code".to_vec()]).map_err(|error| error.to_string())?;
    retain_inspection_hook(&dictionary);
    Ok(())
}

fn parse_method(value: &str) -> Result<&str, String> {
    METHODS
        .contains(&value)
        .then_some(value)
        .ok_or_else(|| format!("unknown method {value:?}"))
}

fn parse_dataset(value: &str) -> Result<&str, String> {
    DATASETS
        .contains(&value)
        .then_some(value)
        .ok_or_else(|| format!("unknown dataset {value:?}"))
}

fn make_dataset(name: &str) -> Dataset {
    let keys = match name {
        "shared" => shared_keys(),
        "opaque" => opaque_keys(),
        _ => unreachable!("dataset validated before construction"),
    };
    let queries = benchmark_queries(&keys);
    let key_bytes = keys.iter().map(Vec::len).sum();
    let hit_count = queries
        .iter()
        .filter(|query| keys.binary_search(query).is_ok())
        .count();
    let input_checksum = sequence_checksum(&keys);
    let query_checksum = sequence_checksum(&queries);
    Dataset {
        name: if name == "shared" { "shared" } else { "opaque" },
        keys,
        queries,
        key_bytes,
        hit_count,
        input_checksum,
        query_checksum,
    }
}

fn build_method(method: &str, keys: &[Vec<u8>]) -> Result<FlatDictionary, String> {
    match method {
        "flat-trie" => build_flat_trie(keys),
        "minimal-dafsa" => build_minimal_dafsa(keys),
        _ => unreachable!("method validated before construction"),
    }
    .map_err(|error| error.to_string())
}

fn verify_contract() -> Result<(), String> {
    let example = [
        b"bar".to_vec(),
        b"bat".to_vec(),
        b"car".to_vec(),
        b"cat".to_vec(),
    ];
    let example_trie = build_flat_trie(&example).map_err(|error| error.to_string())?;
    let example_dafsa = build_minimal_dafsa(&example).map_err(|error| error.to_string())?;
    if (example_trie.state_count(), example_trie.arc_count()) != (9, 8)
        || (example_dafsa.state_count(), example_dafsa.arc_count()) != (4, 5)
    {
        return Err("running-example topology changed".to_owned());
    }

    let mut summaries = Vec::new();
    for dataset_name in DATASETS {
        let dataset = make_dataset(dataset_name);
        for method in METHODS {
            let dictionary = build_method(method, &dataset.keys)?;
            verify_dictionary(&dataset, &dictionary)?;
            verify_expected_topology(method, dataset_name, &dictionary)?;
            summaries.push(format!(
                "{method}/{dataset_name}:{}/{}/{}",
                dictionary.state_count(),
                dictionary.arc_count(),
                dictionary.topology_bytes()
            ));
        }
    }
    println!(
        "CHECK=PASS keys={} queries={} structures={} topology={}",
        65_536 * DATASETS.len(),
        16_384 * DATASETS.len(),
        summaries.len(),
        summaries.join(",")
    );
    Ok(())
}

fn verify_expected_topology(
    method: &str,
    dataset: &str,
    dictionary: &FlatDictionary,
) -> Result<(), String> {
    let expected = match (method, dataset) {
        ("flat-trie", "shared") => (790_801, 790_800, 12_652_808),
        ("minimal-dafsa", "shared") => (16, 75, 728),
        ("flat-trie", "opaque") => (959_061, 959_060, 15_344_968),
        ("minimal-dafsa", "opaque") => (804_065, 869_599, 13_389_312),
        _ => unreachable!("method and dataset validated"),
    };
    let actual = (
        dictionary.state_count(),
        dictionary.arc_count(),
        dictionary.topology_bytes(),
    );
    if actual != expected {
        return Err(format!(
            "topology mismatch for {method}/{dataset}: expected={expected:?} actual={actual:?}"
        ));
    }
    if method == "minimal-dafsa" && !dictionary.has_unique_state_signatures() {
        return Err(format!("duplicate canonical signature in {dataset}"));
    }
    Ok(())
}

fn verify_dictionary(dataset: &Dataset, dictionary: &FlatDictionary) -> Result<(), String> {
    for key in &dataset.keys {
        if !dictionary.contains(key) {
            return Err(format!("{} source key missed", dataset.name));
        }
        let mut extension = key.clone();
        extension.push(0);
        if dictionary.contains(&extension) {
            return Err(format!("{} extension accepted", dataset.name));
        }
    }
    for query in &dataset.queries {
        let expected = dataset.keys.binary_search(query).is_ok();
        if dictionary.contains(query) != expected {
            return Err(format!(
                "{} benchmark query disagrees with oracle",
                dataset.name
            ));
        }
    }
    for key in dataset.keys.iter().step_by(257) {
        let mut probes = Vec::with_capacity(4);
        probes.push(key[..key.len().saturating_sub(1)].to_vec());
        let mut first = key.clone();
        first[0] ^= 0x80;
        probes.push(first);
        let mut middle = key.clone();
        middle[key.len() / 2] ^= 0x5a;
        probes.push(middle);
        let mut last = key.clone();
        let last_index = last.len() - 1;
        last[last_index] ^= 1;
        probes.push(last);
        for probe in probes {
            let expected = dataset.keys.binary_search(&probe).is_ok();
            if dictionary.contains(&probe) != expected {
                return Err(format!(
                    "{} structured miss disagrees with oracle",
                    dataset.name
                ));
            }
        }
    }
    Ok(())
}

fn parse_calibration(calibration: &str, method: &str, dataset: &str) -> Result<u64, String> {
    let mut found = None;
    for line in calibration.lines().filter(|line| !line.trim().is_empty()) {
        let fields: Vec<&str> = line.split('\t').collect();
        if fields == ["method", "dataset", "reps"] {
            continue;
        }
        if fields.len() != 3 {
            return Err(format!("invalid calibration row {line:?}"));
        }
        if fields[0] == method && fields[1] == dataset {
            if found.is_some() {
                return Err(format!("duplicate calibration for {method}/{dataset}"));
            }
            let repetitions = fields[2]
                .parse::<u64>()
                .map_err(|_| format!("invalid repetitions {:?}", fields[2]))?;
            if repetitions == 0 {
                return Err(format!("zero repetitions for {method}/{dataset}"));
            }
            found = Some(repetitions);
        }
    }
    found.ok_or_else(|| format!("missing calibration for {method}/{dataset}"))
}

fn calibrate(dictionary: &FlatDictionary, queries: &[Vec<u8>], target_ms: u64) -> u64 {
    let mut repetitions = 1_u64;
    let elapsed = loop {
        let elapsed = measure(dictionary, queries, repetitions);
        if elapsed >= Duration::from_millis(10) || repetitions >= (1 << 24) {
            break elapsed;
        }
        repetitions = repetitions.saturating_mul(2);
    };
    let elapsed_ns = elapsed.as_nanos().max(1);
    let target_ns = u128::from(target_ms) * 1_000_000;
    let scaled = (u128::from(repetitions) * target_ns / elapsed_ns).max(1);
    u64::try_from(scaled.min(u128::from(u32::MAX))).unwrap()
}

fn process_rows(method: &str, calibration: &str) -> Result<(), String> {
    for dataset_name in DATASETS {
        let dataset = make_dataset(dataset_name);
        let dictionary = build_method(method, &dataset.keys)?;
        verify_dictionary(&dataset, &dictionary)?;
        verify_expected_topology(method, dataset_name, &dictionary)?;
        let repetitions = parse_calibration(calibration, method, dataset_name)?;
        let result_checksum = one_pass_result_checksum(&dictionary, &dataset.queries);
        let elapsed = measure(&dictionary, &dataset.queries, repetitions);
        let elapsed_ns = elapsed.as_nanos();
        let lookup_count = u128::from(repetitions) * dataset.queries.len() as u128;
        let ns_per_lookup = elapsed_ns as f64 / lookup_count as f64;
        println!(
            "{{\"pid\":{},\"method\":\"{method}\",\"actual_method\":\"{method}\",\"dataset\":\"{}\",\"reps\":{repetitions},\"elapsed_ns\":{elapsed_ns},\"ns_per_lookup\":{ns_per_lookup:.9},\"key_count\":{},\"key_bytes\":{},\"query_count\":{},\"hit_count\":{},\"state_count\":{},\"arc_count\":{},\"topology_bytes\":{},\"input_checksum\":{},\"query_checksum\":{},\"result_checksum\":{result_checksum}}}",
            process::id(),
            dataset.name,
            dataset.keys.len(),
            dataset.key_bytes,
            dataset.queries.len(),
            dataset.hit_count,
            dictionary.state_count(),
            dictionary.arc_count(),
            dictionary.topology_bytes(),
            dataset.input_checksum,
            dataset.query_checksum,
        );
    }
    Ok(())
}

fn one_pass_result_checksum(dictionary: &FlatDictionary, queries: &[Vec<u8>]) -> u64 {
    queries
        .iter()
        .enumerate()
        .fold(0_u64, |state, (index, query)| {
            state.rotate_left(7)
                ^ u64::from(topic035_flat_contains(dictionary, query))
                    .wrapping_add((index as u64).wrapping_mul(0x9e37_79b9))
        })
}

fn measure(dictionary: &FlatDictionary, queries: &[Vec<u8>], repetitions: u64) -> Duration {
    black_box(one_pass_result_checksum(dictionary, queries));
    let start = Instant::now();
    let mut folded = 0_u64;
    for repetition in 0..repetitions {
        for (index, query) in queries.iter().enumerate() {
            let present = topic035_flat_contains(black_box(dictionary), black_box(query));
            folded = folded.rotate_left(7)
                ^ u64::from(present).wrapping_add(
                    repetition
                        .wrapping_mul(0x9e37_79b9)
                        .wrapping_add(index as u64),
                );
        }
    }
    let elapsed = start.elapsed();
    black_box(folded);
    elapsed
}
