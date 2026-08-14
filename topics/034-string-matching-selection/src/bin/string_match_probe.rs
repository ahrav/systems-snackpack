//! Fresh-process correctness and timing probe for the three teaching matchers.
//!
//! `verify` checks matcher agreement before measurement. `calibrate` chooses a
//! repetition count for one method, case, and timing mode. `process` consumes a
//! frozen repetition map and emits ten JSON rows from one process. The runner
//! keeps corpus construction, correctness checks, calibration, and output
//! outside the reported intervals.

use std::env;
use std::fs;
use std::hint::black_box;
use std::process;
use std::time::{Duration, Instant};

use string_matching_selection::{
    HorspoolPlan, KmpPlan, left_to_right_find, oracle_find, topic034_horspool_find,
    topic034_kmp_find, topic034_left_to_right_find, verify_contract,
};

const METHODS: [&str; 3] = ["left-to-right", "kmp", "horspool"];
const MODES: [&str; 2] = ["reuse", "one_shot"];
type InspectionHook = fn(&[u8], &[u8]) -> Option<usize>;

struct Case {
    name: &'static str,
    haystack: Vec<u8>,
    needle: Vec<u8>,
    expected: Option<usize>,
    input_checksum: u64,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("ERROR={error}");
        process::exit(2);
    }
}

fn run() -> Result<(), String> {
    retain_inspection_hooks();
    let args: Vec<String> = env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("verify") if args.len() == 2 => {
            let checked = verify_contract();
            verify_cases(&cases())?;
            println!("CHECK=PASS pairs={checked} benchmark_cases=5");
            Ok(())
        }
        Some("calibrate") if args.len() == 6 => {
            let method = parse_method(&args[2])?;
            let case = find_case(&args[3])?;
            let mode = parse_mode(&args[4])?;
            let target_ms = args[5]
                .parse::<u64>()
                .map_err(|_| "target milliseconds must be an integer".to_owned())?;
            let repetitions = calibrate(method, &case, mode, target_ms.max(1))?;
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
            "usage: {} verify | calibrate METHOD CASE MODE TARGET_MS | process METHOD CALIBRATION_TSV",
            args.first().map_or("string-match-probe", String::as_str)
        )),
    }
}

fn retain_inspection_hooks() {
    let haystack = black_box(b"linked code inspection".as_slice());
    let needle = black_box(b"code".as_slice());
    let hooks: [InspectionHook; 3] = black_box([
        topic034_left_to_right_find,
        topic034_kmp_find,
        topic034_horspool_find,
    ]);
    for hook in hooks {
        black_box(hook(haystack, needle));
    }
}

fn parse_method(value: &str) -> Result<&str, String> {
    METHODS
        .contains(&value)
        .then_some(value)
        .ok_or_else(|| format!("unknown method {value:?}"))
}

fn parse_mode(value: &str) -> Result<&str, String> {
    MODES
        .contains(&value)
        .then_some(value)
        .ok_or_else(|| format!("unknown mode {value:?}"))
}

fn find_case(name: &str) -> Result<Case, String> {
    cases()
        .into_iter()
        .find(|case| case.name == name)
        .ok_or_else(|| format!("unknown case {name:?}"))
}

fn cases() -> Vec<Case> {
    let mut state = 0x9e37_79b9_7f4a_7c15_u64;
    let mut uniform = vec![0; 1 << 20];
    for byte in &mut uniform {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        *byte = (state % 255).to_le_bytes()[0];
    }
    let uniform_needle = vec![0xff; 32];

    let phrase = b"the quick brown fox moves through a small systems workload. ";
    let mut text = Vec::with_capacity(1 << 20);
    while text.len() + phrase.len() <= (1 << 20) - 16 {
        text.extend_from_slice(phrase);
    }
    text.resize((1 << 20) - 16, b' ');
    let text_needle = b"the ~late match!".to_vec();
    text.extend_from_slice(&text_needle);

    let prefix_haystack = vec![b'a'; 128 << 10];
    let mut prefix_needle = vec![b'a'; 32];
    prefix_needle[31] = b'b';

    let suffix_haystack = vec![b'a'; 128 << 10];
    let mut suffix_needle = vec![b'a'; 32];
    suffix_needle[0] = b'b';

    let mut tiny_haystack = vec![b'x'; 4096];
    let tiny_needle = b"q7!z".to_vec();
    tiny_haystack[4092..].copy_from_slice(&tiny_needle);

    [
        ("uniform_absent_32", uniform, uniform_needle),
        ("text_late_16", text, text_needle),
        ("prefix_trap_32", prefix_haystack, prefix_needle),
        ("suffix_trap_32", suffix_haystack, suffix_needle),
        ("tiny_late_4", tiny_haystack, tiny_needle),
    ]
    .into_iter()
    .map(|(name, haystack, needle)| {
        let expected = oracle_find(&haystack, &needle);
        let input_checksum = checksum(&haystack) ^ checksum(&needle).rotate_left(17);
        Case {
            name,
            haystack,
            needle,
            expected,
            input_checksum,
        }
    })
    .collect()
}

fn verify_cases(cases: &[Case]) -> Result<(), String> {
    for case in cases {
        for method in METHODS {
            let actual = search_once(method, case, "reuse")?;
            if actual != case.expected {
                return Err(format!(
                    "case={} method={} expected={:?} actual={actual:?}",
                    case.name, method, case.expected
                ));
            }
        }
    }
    Ok(())
}

fn calibrate(method: &str, case: &Case, mode: &str, target_ms: u64) -> Result<u64, String> {
    let mut repetitions = 1_u64;
    let elapsed = loop {
        let elapsed = measure(method, case, mode, repetitions)?.0;
        if elapsed >= Duration::from_millis(10) || repetitions >= 1 << 24 {
            break elapsed;
        }
        repetitions = repetitions.saturating_mul(2);
    };
    let elapsed_ns = elapsed.as_nanos().max(1);
    let target_ns = u128::from(target_ms) * 1_000_000;
    let scaled = (u128::from(repetitions) * target_ns / elapsed_ns).max(1);
    Ok(u64::try_from(scaled.min(u128::from(u32::MAX))).unwrap())
}

fn process_rows(method: &str, calibration: &str) -> Result<(), String> {
    let all_cases = cases();
    verify_cases(&all_cases)?;
    let pid = process::id();
    let mut emitted = 0;
    for line in calibration.lines().filter(|line| !line.trim().is_empty()) {
        let fields: Vec<&str> = line.split('\t').collect();
        if fields.len() != 4 || fields[0] == "method" {
            continue;
        }
        if fields[0] != method {
            continue;
        }
        let case = all_cases
            .iter()
            .find(|case| case.name == fields[1])
            .ok_or_else(|| format!("unknown calibration case {:?}", fields[1]))?;
        let mode = parse_mode(fields[2])?;
        let repetitions = fields[3]
            .parse::<u64>()
            .map_err(|_| format!("invalid repetitions {:?}", fields[3]))?;
        let (elapsed, result_checksum, actual) = measure(method, case, mode, repetitions)?;
        if actual != case.expected {
            return Err(format!("timed result mismatch for {}", case.name));
        }
        let elapsed_ns = elapsed.as_nanos();
        let ns_per_search = elapsed_ns as f64 / repetitions as f64;
        let logical_bytes_per_search = case.haystack.len();
        let logical_gib_per_s = logical_bytes_per_search as f64 / ns_per_search * 1_000_000_000.0
            / (1_u64 << 30) as f64;
        let result = actual.map_or("null".to_owned(), |value| value.to_string());
        println!(
            "{{\"pid\":{pid},\"method\":\"{method}\",\"actual_method\":\"{method}\",\"case\":\"{}\",\"mode\":\"{mode}\",\"reps\":{repetitions},\"elapsed_ns\":{elapsed_ns},\"ns_per_search\":{ns_per_search:.6},\"logical_bytes_per_search\":{logical_bytes_per_search},\"logical_gib_per_s\":{logical_gib_per_s:.9},\"result\":{result},\"checksum\":{result_checksum},\"input_checksum\":{}}}",
            case.name, case.input_checksum
        );
        emitted += 1;
    }
    if emitted != 10 {
        return Err(format!(
            "expected 10 calibrated cells for {method}, found {emitted}"
        ));
    }
    Ok(())
}

fn measure(
    method: &str,
    case: &Case,
    mode: &str,
    repetitions: u64,
) -> Result<(Duration, u64, Option<usize>), String> {
    let _ = search_once(method, case, mode)?;
    let mut folded = 0_u64;
    let mut last = None;

    match (method, mode) {
        ("left-to-right", _) => {
            let start = Instant::now();
            for iteration in 0..repetitions {
                let result = left_to_right_find(
                    black_box(case.haystack.as_slice()),
                    black_box(case.needle.as_slice()),
                );
                folded = fold_result(folded, result, iteration);
                last = result;
            }
            Ok((start.elapsed(), black_box(folded), last))
        }
        ("kmp", "reuse") => {
            let plan = KmpPlan::new(black_box(case.needle.as_slice()));
            let start = Instant::now();
            for iteration in 0..repetitions {
                let result = plan.find(black_box(case.haystack.as_slice()));
                folded = fold_result(folded, result, iteration);
                last = result;
            }
            Ok((start.elapsed(), black_box(folded), last))
        }
        ("kmp", "one_shot") => {
            let start = Instant::now();
            for iteration in 0..repetitions {
                let plan = KmpPlan::new(black_box(case.needle.as_slice()));
                let result = plan.find(black_box(case.haystack.as_slice()));
                folded = fold_result(folded, result, iteration);
                last = result;
            }
            Ok((start.elapsed(), black_box(folded), last))
        }
        ("horspool", "reuse") => {
            let plan = HorspoolPlan::new(black_box(case.needle.as_slice()));
            let start = Instant::now();
            for iteration in 0..repetitions {
                let result = plan.find(black_box(case.haystack.as_slice()));
                folded = fold_result(folded, result, iteration);
                last = result;
            }
            Ok((start.elapsed(), black_box(folded), last))
        }
        ("horspool", "one_shot") => {
            let start = Instant::now();
            for iteration in 0..repetitions {
                let plan = HorspoolPlan::new(black_box(case.needle.as_slice()));
                let result = plan.find(black_box(case.haystack.as_slice()));
                folded = fold_result(folded, result, iteration);
                last = result;
            }
            Ok((start.elapsed(), black_box(folded), last))
        }
        _ => Err(format!("unsupported method/mode {method}/{mode}")),
    }
}

fn search_once(method: &str, case: &Case, mode: &str) -> Result<Option<usize>, String> {
    match (method, mode) {
        ("left-to-right", _) => Ok(left_to_right_find(&case.haystack, &case.needle)),
        ("kmp", _) => Ok(KmpPlan::new(&case.needle).find(&case.haystack)),
        ("horspool", _) => Ok(HorspoolPlan::new(&case.needle).find(&case.haystack)),
        _ => Err(format!("unsupported method/mode {method}/{mode}")),
    }
}

fn fold_result(current: u64, result: Option<usize>, iteration: u64) -> u64 {
    let value = result.map_or(u64::MAX, |position| position as u64);
    current.rotate_left(7) ^ value.wrapping_add(iteration.wrapping_mul(0x9e37_79b9))
}

fn checksum(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf2_9ce4_8422_2325, |hash, &byte| {
        (hash ^ u64::from(byte)).wrapping_mul(0x0000_0100_0000_01b3)
    })
}
