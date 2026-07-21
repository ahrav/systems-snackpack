//! Times one CRC32C kernel over one deterministic, repeatedly warmed byte slice.
//!
//! `elapsed_ns` covers repeated whole-slice CRC calls, black-box barriers, and
//! digest accumulation. It excludes argument parsing, allocation, input
//! generation, runtime feature detection, kernel selection, the independent
//! correctness check, and at least 64 MiB of warmup. Calls through the selected
//! function pointer remain inside the timed loop. `setup_ns` reports allocation,
//! input generation, kernel selection, the check, and feature detection in
//! hardware mode. Each invocation is one process-level observation; loop
//! iterations are the workload, not independent samples.
//!
//! Run a correctness check with
//! `cargo bench -p systems-snackpack-topic-010 --bench crc32c -- --verify`.
//! Select a timed kernel with `--mode table` or `--mode hardware`.

use std::{env, hint::black_box, process, time::Instant};

use systems_snackpack_topic_010::{Crc32cKernel, crc32c_bitwise, crc32c_table};

const DEFAULT_LEN: usize = 4096;
const DEFAULT_ALIGN: usize = 3;
const DEFAULT_ITERATIONS: usize = 262_144;
const WARMUP_TARGET_BYTES: usize = 64 * 1024 * 1024;
const DIGEST_MULTIPLIER: u64 = 0x9e37_79b1_85eb_ca87;

#[derive(Clone, Copy)]
enum Mode {
    Table,
    Hardware,
}

impl Mode {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "table" => Ok(Self::Table),
            "hardware" => Ok(Self::Hardware),
            _ => Err(format!("mode must be table or hardware, got {value:?}")),
        }
    }

    const fn name(self) -> &'static str {
        match self {
            Self::Table => "table",
            Self::Hardware => "hardware",
        }
    }

    fn kernel(self) -> Result<Crc32cKernel, String> {
        match self {
            Self::Table => Ok(Crc32cKernel::table()),
            Self::Hardware => Crc32cKernel::detect_hardware()
                .ok_or_else(|| "hardware CRC32C is unavailable on this host".to_owned()),
        }
    }
}

#[derive(Clone, Copy)]
struct Config {
    mode: Mode,
    len: usize,
    align: usize,
    iterations: usize,
}

fn parse_usize(flag: &str, value: Option<String>) -> Result<usize, String> {
    let value = value.ok_or_else(|| format!("{flag} requires a value"))?;
    value
        .parse::<usize>()
        .map_err(|error| format!("invalid {flag} value {value:?}: {error}"))
}

fn parse_config() -> Result<Config, String> {
    let mut mode = None;
    let mut len = DEFAULT_LEN;
    let mut align = DEFAULT_ALIGN;
    let mut iterations = DEFAULT_ITERATIONS;
    let mut args = env::args().skip(1);
    while let Some(flag) = args.next() {
        match flag.as_str() {
            // `cargo bench` appends this harness argument even for a
            // `harness = false` target. Direct runner invocations omit it.
            "--bench" => {}
            "--mode" => {
                let value = args
                    .next()
                    .ok_or_else(|| "--mode requires a value".to_owned())?;
                mode = Some(Mode::parse(&value)?);
            }
            "--len" => len = parse_usize("--len", args.next())?,
            "--align" => align = parse_usize("--align", args.next())?,
            "--iterations" => iterations = parse_usize("--iterations", args.next())?,
            _ => return Err(format!("unknown argument {flag:?}")),
        }
    }
    if len == 0 {
        return Err("--len must be positive".to_owned());
    }
    if iterations == 0 {
        return Err("--iterations must be positive".to_owned());
    }
    align
        .checked_add(len)
        .ok_or_else(|| "--align + --len overflows usize".to_owned())?;
    len.checked_mul(iterations)
        .ok_or_else(|| "--len * --iterations overflows usize".to_owned())?;
    Ok(Config {
        mode: mode.ok_or_else(|| "--mode is required".to_owned())?,
        len,
        align,
        iterations,
    })
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn dataset(len: usize) -> Vec<u8> {
    let mut state = 0x243f_6a88_85a3_08d3_u64;
    (0..len).map(|_| splitmix64(&mut state) as u8).collect()
}

fn run_iterations(kernel: Crc32cKernel, input: &[u8], iterations: usize) -> (u32, u64) {
    let mut checksum = 0_u32;
    let mut digest = 0x6a09_e667_f3bc_c909_u64;
    for iteration in 0..iterations {
        checksum = kernel.checksum(black_box(input));
        digest = digest
            .wrapping_mul(DIGEST_MULTIPLIER)
            .wrapping_add(u64::from(black_box(checksum)) ^ iteration as u64);
    }
    (black_box(checksum), black_box(digest))
}

fn verify() {
    assert_eq!(crc32c_bitwise(b"123456789"), 0xe306_9283);
    assert_eq!(crc32c_table(b"123456789"), 0xe306_9283);
    let bytes = dataset(16 + 1024);
    let hardware = Crc32cKernel::detect_hardware();
    let mut cases = 0_usize;
    for align in 0..16 {
        for len in 0..=1024 {
            let input = &bytes[align..align + len];
            let expected = crc32c_bitwise(input);
            assert_eq!(
                crc32c_table(input),
                expected,
                "table align={align} len={len}"
            );
            if let Some(kernel) = hardware {
                assert_eq!(
                    kernel.checksum(input),
                    expected,
                    "hardware align={align} len={len}"
                );
            }
            cases += 1;
        }
    }
    println!(
        "VERIFY pid={} hardware={} cases={} crc32c_vector=e3069283",
        process::id(),
        hardware.map_or("unavailable", Crc32cKernel::name),
        cases
    );
}

fn run(config: Config) -> Result<(), String> {
    let setup_started = Instant::now();
    let bytes = dataset(config.align + config.len);
    let input = &bytes[config.align..config.align + config.len];
    let address_mod_64 = input.as_ptr() as usize % 64;
    let kernel = config.mode.kernel()?;
    let expected = crc32c_bitwise(input);
    if crc32c_table(input) != expected || kernel.checksum(input) != expected {
        return Err("selected CRC32C kernel failed the independent check".to_owned());
    }
    let setup_ns = setup_started.elapsed().as_nanos();

    let warmup_iterations = WARMUP_TARGET_BYTES.div_ceil(config.len);
    let warmup_bytes = warmup_iterations
        .checked_mul(config.len)
        .ok_or_else(|| "warmup byte count overflows usize".to_owned())?;
    let _ = run_iterations(kernel, input, warmup_iterations);

    let started = Instant::now();
    let (checksum, digest) = run_iterations(kernel, input, config.iterations);
    let elapsed_ns = started.elapsed().as_nanos();
    let total_bytes = config.len * config.iterations;
    let ns_per_byte = elapsed_ns as f64 / total_bytes as f64;
    let gb_per_s = total_bytes as f64 / elapsed_ns as f64;

    println!(
        "RESULT mode={} len={} align={} iterations={} total_bytes={} elapsed_ns={} setup_ns={} warmup_bytes={} ns_per_byte={:.9} gb_per_s={:.9} checksum={:08x} digest={:016x} pid={} address_mod_64={}",
        config.mode.name(),
        config.len,
        config.align,
        config.iterations,
        total_bytes,
        elapsed_ns,
        setup_ns,
        warmup_bytes,
        ns_per_byte,
        gb_per_s,
        checksum,
        digest,
        process::id(),
        address_mod_64
    );
    Ok(())
}

fn usage() -> ! {
    eprintln!(
        "usage: crc32c --verify | --mode <table|hardware> [--len N] [--align N] [--iterations N]"
    );
    process::exit(2);
}

fn main() {
    let args = env::args()
        .filter(|argument| argument != "--bench")
        .collect::<Vec<_>>();
    if args.len() == 2 && args[1] == "--verify" {
        verify();
        return;
    }
    if args.iter().any(|arg| arg == "--verify") {
        usage();
    }
    let config = parse_config().unwrap_or_else(|error| {
        eprintln!("{error}");
        usage();
    });
    if let Err(error) = run(config) {
        eprintln!("{error}");
        process::exit(2);
    }
}
