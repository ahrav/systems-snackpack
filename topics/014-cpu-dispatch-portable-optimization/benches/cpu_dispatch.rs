//! Runs one dispatch mode and emits one tab-separated process record.
//!
//! The steady phase covers each mode's dispatch path and byte-counting kernel
//! across the configured passes. Allocation, fixture generation, scalar-oracle
//! evaluation, and mode-specific pre-resolution are reported as `setup_ns`.
//! Verification is reported separately as `verify_ns`. The enclosing process
//! runner records startup and runner overhead in `external_wall_ns`.

use std::hint::black_box;
use std::process::ExitCode;
use std::time::Instant;

use systems_snackpack_topic_014::{
    KernelKind, RECORDED_CHUNK_BYTES, RECORDED_INPUT_BYTES, RECORDED_NEEDLE, RECORDED_PASSES,
    ResolvedKernel, count_eq_cached_chunks, count_eq_detect_chunks, count_eq_dispatch_once,
    count_eq_scalar, resolve_best, resolve_cached,
};

const EMBEDDED_SOURCE_COMMIT: &str = match option_env!("TOPIC14_SOURCE_COMMIT") {
    Some(commit) => commit,
    None => "unrecorded",
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Mode {
    ScalarWhole,
    SimdWhole,
    DispatchOnce,
    CachedChunks,
    DetectChunks,
}

impl Mode {
    fn parse(value: &str) -> Option<Self> {
        match value {
            "scalar_whole" => Some(Self::ScalarWhole),
            "simd_whole" => Some(Self::SimdWhole),
            "dispatch_once" => Some(Self::DispatchOnce),
            "cached_chunks" => Some(Self::CachedChunks),
            "detect_chunks" => Some(Self::DetectChunks),
            _ => None,
        }
    }

    const fn as_str(self) -> &'static str {
        match self {
            Self::ScalarWhole => "scalar_whole",
            Self::SimdWhole => "simd_whole",
            Self::DispatchOnce => "dispatch_once",
            Self::CachedChunks => "cached_chunks",
            Self::DetectChunks => "detect_chunks",
        }
    }

    fn comparison_peer(self, comparison: &str) -> bool {
        matches!(
            (comparison, self),
            ("scalar-vs-simd", Self::ScalarWhole | Self::SimdWhole)
                | ("whole-vs-chunks", Self::DispatchOnce | Self::CachedChunks)
                | ("cached-vs-detect", Self::CachedChunks | Self::DetectChunks)
        )
    }
}

fn fail(message: &str) -> ExitCode {
    eprintln!("{message}");
    ExitCode::from(2)
}

fn parse_positive_env(name: &str, default: usize) -> Result<usize, String> {
    match std::env::var(name) {
        Ok(value) => value
            .parse::<usize>()
            .ok()
            .filter(|parsed| *parsed > 0)
            .ok_or_else(|| format!("{name} must be a positive usize")),
        Err(std::env::VarError::NotPresent) => Ok(default),
        Err(std::env::VarError::NotUnicode(_)) => Err(format!("{name} must be valid UTF-8")),
    }
}

fn build_fixture(length: usize) -> (Vec<u8>, u64) {
    let mut state = 0x243f_6a88_85a3_08d3_u64;
    let mut checksum = 0_u64;
    let mut input = Vec::with_capacity(length);
    for _ in 0..length {
        state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
        let mut mixed = state;
        mixed = (mixed ^ (mixed >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        mixed = (mixed ^ (mixed >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        mixed ^= mixed >> 31;
        let byte = (mixed >> 56) as u8;
        input.push(byte);
        checksum = checksum.wrapping_add(byte as u64);
    }
    (input, checksum)
}

fn run_pass(
    mode: Mode,
    selected: Option<ResolvedKernel>,
    input: &[u8],
    chunk_bytes: usize,
) -> usize {
    match mode {
        Mode::ScalarWhole => count_eq_scalar(input, RECORDED_NEEDLE),
        Mode::SimdWhole => selected
            .expect("simd mode resolves during setup")
            .count(input, RECORDED_NEEDLE),
        Mode::DispatchOnce => count_eq_dispatch_once(input, RECORDED_NEEDLE),
        Mode::CachedChunks => count_eq_cached_chunks(input, RECORDED_NEEDLE, chunk_bytes)
            .expect("the command-line contract rejects zero-sized chunks"),
        Mode::DetectChunks => count_eq_detect_chunks(input, RECORDED_NEEDLE, chunk_bytes)
            .expect("the command-line contract rejects zero-sized chunks"),
    }
}

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().collect();
    let cargo_bench_suffix =
        arguments.len() == 8 && arguments.last().is_some_and(|value| value == "--bench");
    if arguments.len() != 7 && !cargo_bench_suffix {
        return fail("usage: cpu_dispatch RUN_ID COMPARISON PAIR POSITION ORDER MODE");
    }
    let run_id = &arguments[1];
    let comparison = &arguments[2];
    let pair = match arguments[3].parse::<usize>() {
        Ok(value @ 1..=12) => value,
        _ => return fail("PAIR must be in 1..=12"),
    };
    let position = match arguments[4].parse::<usize>() {
        Ok(value @ 1..=2) => value,
        _ => return fail("POSITION must be 1 or 2"),
    };
    let order = arguments[5].as_str();
    if !matches!(order, "ab" | "ba") {
        return fail("ORDER must be ab or ba");
    }
    let expected_run_id = format!("{}-p{pair:02}-{position}", comparison.replace("-vs-", "_"));
    if run_id != &expected_run_id {
        return fail("RUN_ID does not match COMPARISON, PAIR, and POSITION");
    }
    let mode = match Mode::parse(&arguments[6]) {
        Some(value) if value.comparison_peer(comparison) => value,
        _ => return fail("MODE is not a member of COMPARISON"),
    };

    let input_bytes = match parse_positive_env("TOPIC14_BYTES", RECORDED_INPUT_BYTES) {
        Ok(value) => value,
        Err(error) => return fail(&error),
    };
    let passes = match parse_positive_env("TOPIC14_PASSES", RECORDED_PASSES) {
        Ok(value) => value,
        Err(error) => return fail(&error),
    };
    let chunk_bytes = match parse_positive_env("TOPIC14_CHUNK_BYTES", RECORDED_CHUNK_BYTES) {
        Ok(value) => value,
        Err(error) => return fail(&error),
    };

    let setup_started = Instant::now();
    let (input, input_checksum) = build_fixture(input_bytes);
    let expected_per_pass = count_eq_scalar(&input, RECORDED_NEEDLE);
    let expected_checksum = match expected_per_pass.checked_mul(passes) {
        Some(value) => value,
        None => return fail("expected checksum overflowed usize"),
    };
    let selected = match mode {
        Mode::SimdWhole => Some(resolve_best()),
        Mode::CachedChunks => Some(*resolve_cached()),
        Mode::ScalarWhole | Mode::DispatchOnce | Mode::DetectChunks => None,
    };
    if mode == Mode::SimdWhole && selected.is_some_and(|kernel| kernel.kind() == KernelKind::Scalar)
    {
        return fail("simd_whole requires a supported architecture-specific kernel");
    }
    let setup_ns = setup_started.elapsed().as_nanos();

    let steady_started = Instant::now();
    let mut checksum = 0_usize;
    for _ in 0..passes {
        checksum = checksum.wrapping_add(run_pass(mode, selected, black_box(&input), chunk_bytes));
    }
    let steady_ns = steady_started.elapsed().as_nanos();

    let verify_started = Instant::now();
    if checksum != expected_checksum {
        return fail("timed result differs from the scalar oracle");
    }
    let variant = match mode {
        Mode::ScalarWhole => "scalar",
        Mode::SimdWhole | Mode::CachedChunks => selected
            .expect("selected modes resolve during setup")
            .kind()
            .as_str(),
        Mode::DispatchOnce | Mode::DetectChunks => resolve_best().kind().as_str(),
    };
    black_box(checksum);
    let verify_ns = verify_started.elapsed().as_nanos();

    println!(
        "{run_id}\t{comparison}\t{pair}\t{position}\t{order}\t{}\t{variant}\t{input_bytes}\t{passes}\t{chunk_bytes}\t{}\t{input_checksum}\t{expected_per_pass}\t{checksum}\t{expected_checksum}\t{setup_ns}\t{steady_ns}\t{verify_ns}",
        mode.as_str(),
        EMBEDDED_SOURCE_COMMIT,
    );
    ExitCode::SUCCESS
}
