//! Correctness and steady-state timing probe for the Topic 36 kernels.

use roaring_bitmaps_compressed_sets::{
    CASE_NAMES, CaseData, array_payload_bytes, bitmap_payload_bytes, make_case, run_payload_bytes,
};
use std::env;
use std::hint::black_box;
use std::time::{Duration, Instant};

fn repeat(case: &CaseData, method: &str, iterations: u64) -> Result<u64, String> {
    let mut checksum = 0_u64;
    match method {
        "array" => {
            for _ in 0..iterations {
                checksum = checksum.wrapping_add(u64::from(black_box(
                    black_box(case).array_intersection_cardinality(),
                )));
            }
        }
        "bitmap" => {
            for _ in 0..iterations {
                checksum = checksum.wrapping_add(u64::from(black_box(
                    black_box(case).bitmap_intersection_cardinality(),
                )));
            }
        }
        "run" => {
            for _ in 0..iterations {
                checksum = checksum.wrapping_add(u64::from(black_box(
                    black_box(case).run_intersection_cardinality(),
                )));
            }
        }
        _ => return Err(format!("unknown method: {method}")),
    }
    Ok(black_box(checksum))
}

fn calibrated_iterations(case: &CaseData, method: &str, target: Duration) -> Result<u64, String> {
    let mut iterations = 1_u64;
    loop {
        let start = Instant::now();
        let _ = repeat(case, method, iterations)?;
        let elapsed = start.elapsed();
        if elapsed >= Duration::from_millis(20) || iterations >= (1 << 30) {
            let elapsed_ns = elapsed.as_nanos().max(1);
            let desired = target.as_nanos().saturating_mul(u128::from(iterations)) / elapsed_ns;
            return Ok(desired.clamp(1, u128::from(u64::MAX)) as u64);
        }
        iterations = iterations.saturating_mul(2);
    }
}

fn verify_case(name: &str) -> Result<(), String> {
    let case = make_case(name).ok_or_else(|| format!("unknown case: {name}"))?;
    let expected = case.oracle_intersection_cardinality();
    let array = case.array_intersection_cardinality();
    let bitmap = case.bitmap_intersection_cardinality();
    let run = case.run_intersection_cardinality();
    if (array, bitmap, run) != (expected, expected, expected) {
        return Err(format!(
            "case {name} disagreed with oracle: oracle={expected} array={array} bitmap={bitmap} run={run}"
        ));
    }

    println!(
        "CHECK=PASS CASE={} CARD_A={} CARD_B={} AND={} RUNS_A={} RUNS_B={} ARRAY_BYTES={} BITMAP_BYTES={} RUN_BYTES={}",
        case.name(),
        case.array_a().len(),
        case.array_b().len(),
        expected,
        case.runs_a().len(),
        case.runs_b().len(),
        array_payload_bytes(case.array_a().len()) + array_payload_bytes(case.array_b().len()),
        2 * bitmap_payload_bytes(),
        run_payload_bytes(case.runs_a().len()) + run_payload_bytes(case.runs_b().len()),
    );
    Ok(())
}

fn bench(case_name: &str, method: &str, target_ms: u64) -> Result<(), String> {
    if target_ms == 0 {
        return Err("TARGET_MS must be greater than zero".to_owned());
    }
    let case = make_case(case_name).ok_or_else(|| format!("unknown case: {case_name}"))?;
    let expected = case.oracle_intersection_cardinality();

    // Construction, oracle validation, calibration, and warmup stay outside
    // the reported steady-state interval.
    let one = repeat(&case, method, 1)?;
    if one != u64::from(expected) {
        return Err(format!(
            "method {method} returned {one}, expected {expected} for {case_name}"
        ));
    }
    let target = Duration::from_millis(target_ms);
    let iterations = calibrated_iterations(&case, method, target)?;
    let _ = repeat(&case, method, iterations.min(128))?;

    let start = Instant::now();
    let checksum = repeat(&case, method, iterations)?;
    let elapsed = start.elapsed();
    let wanted = u64::from(expected).wrapping_mul(iterations);
    if checksum != wanted {
        return Err(format!(
            "checksum mismatch for {case_name}/{method}: observed {checksum}, expected {wanted}"
        ));
    }

    println!(
        "CHECK=PASS CASE={} METHOD={} ITERS={} ELAPSED_NS={} NS_PER_OP={:.9} COUNT={} CHECKSUM={}",
        case.name(),
        method,
        iterations,
        elapsed.as_nanos(),
        elapsed.as_nanos() as f64 / iterations as f64,
        expected,
        checksum,
    );
    Ok(())
}

fn usage() -> ! {
    eprintln!("usage: bitmap-probe verify | bench CASE METHOD TARGET_MS");
    std::process::exit(2);
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    match args.as_slice() {
        [_, command] if command == "verify" => {
            for case in CASE_NAMES {
                verify_case(case)?;
            }
            Ok(())
        }
        [_, command, case, method, target_ms] if command == "bench" => {
            let target_ms = target_ms
                .parse::<u64>()
                .map_err(|error| format!("TARGET_MS must be an integer: {error}"))?;
            bench(case, method, target_ms)
        }
        _ => usage(),
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("bitmap-probe: {error}");
        std::process::exit(2);
    }
}
