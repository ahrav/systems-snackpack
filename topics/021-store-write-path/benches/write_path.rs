//! Fresh-process benchmark entry point for Topic 21.
//!
//! Each invocation measures exactly one kernel. Setup, cache scrubbing, the
//! timed kernel, and full verification have separate durations and Linux
//! process-fault deltas. Comparative statistics belong to
//! `experiment/run_processes.py`, where a process is the observation unit.

use std::env;
use std::fs::File;
use std::hint::black_box;
use std::io::{self, Read, Seek, SeekFrom};
use std::process::ExitCode;
use std::sync::atomic::{AtomicU64, Ordering, compiler_fence, fence};
use std::time::Instant;
use topic_021_store_write_path::{
    AlignedBuffer, BUFFER_ALIGNMENT, STLF_SEED, StlfMode, WriteMode, architecture_name,
    publish_pattern, run_stlf, stlf_oracle, write_kernels_supported,
};

#[repr(align(64))]
struct Ready(AtomicU64);

#[derive(Clone, Copy)]
struct Faults {
    minor: u64,
    major: u64,
}

impl Faults {
    fn delta(self, before: Self) -> io::Result<Self> {
        Ok(Self {
            minor: self.minor.checked_sub(before.minor).ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "minor faults decreased")
            })?,
            major: self.major.checked_sub(before.major).ok_or_else(|| {
                io::Error::new(io::ErrorKind::InvalidData, "major faults decreased")
            })?,
        })
    }
}

struct ProcStat {
    file: File,
    buffer: String,
}

impl ProcStat {
    fn open() -> io::Result<Self> {
        let mut reader = Self {
            file: File::open("/proc/self/stat")?,
            buffer: String::with_capacity(1024),
        };
        // Warm the file path, descriptor, and reusable string before any
        // phase boundary. Otherwise the observer can create the first minor
        // fault attributed to the following phase.
        for _ in 0..4 {
            let _ = reader.read()?;
        }
        Ok(reader)
    }

    fn read(&mut self) -> io::Result<Faults> {
        self.file.seek(SeekFrom::Start(0))?;
        self.buffer.clear();
        self.file.read_to_string(&mut self.buffer)?;
        let close = self.buffer.rfind(") ").ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, "malformed /proc/self/stat")
        })?;
        // The suffix begins at field 3 (`state`). `minflt` and `majflt` are
        // fields 10 and 12, so their zero-based suffix indices are 7 and 9.
        let mut fields = self.buffer[close + 2..].split_whitespace();
        let minflt = fields
            .nth(7)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "missing minflt"))?;
        let majflt = fields
            .nth(1)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "missing majflt"))?;
        let parse = |value: &str, name: &str| -> io::Result<u64> {
            value.parse().map_err(|error| {
                io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!("invalid {name}: {error}"),
                )
            })
        };
        Ok(Faults {
            minor: parse(minflt, "minflt")?,
            major: parse(majflt, "majflt")?,
        })
    }
}

#[derive(Clone, Copy)]
struct PhaseFaults {
    setup: Faults,
    scrub: Faults,
    timed: Faults,
    verify: Faults,
}

fn write_mode(name: &str) -> Option<(WriteMode, &'static str)> {
    match name {
        "temporal" | "temporal_a" | "temporal_b" => Some((WriteMode::Temporal, "temporal")),
        "nontemporal" => Some((WriteMode::NonTemporal, "nontemporal")),
        _ => None,
    }
}

fn stlf_mode(name: &str) -> Option<(StlfMode, &'static str)> {
    match name {
        "exact" | "exact_a" | "exact_b" => Some((StlfMode::Exact, "exact")),
        "partial" => Some((StlfMode::Partial, "partial")),
        _ => None,
    }
}

fn run_write(requested_mode: &str, mib: usize) -> Result<(), String> {
    let (mode, implementation) = write_mode(requested_mode)
        .ok_or_else(|| format!("unknown write mode: {requested_mode}"))?;
    if !write_kernels_supported() {
        return Err("required target features are unavailable".to_owned());
    }
    let size = mib
        .checked_mul(1024 * 1024)
        .ok_or_else(|| "write size overflow".to_owned())?;
    if size == 0 || size % BUFFER_ALIGNMENT != 0 {
        return Err("write size must be a nonzero multiple of 4 KiB".to_owned());
    }

    let mut faults = ProcStat::open().map_err(|error| format!("open proc stat: {error}"))?;
    let f0 = faults
        .read()
        .map_err(|error| format!("read setup-start faults: {error}"))?;
    let setup_start = Instant::now();
    let mut destination = AlignedBuffer::new(size);
    let mut eviction = AlignedBuffer::new(size);
    let ready = Ready(AtomicU64::new(0));
    compiler_fence(Ordering::SeqCst);
    let setup_ns = setup_start.elapsed().as_nanos();
    let f1 = faults
        .read()
        .map_err(|error| format!("read setup-end faults: {error}"))?;

    let scrub_start = Instant::now();
    destination.fill(0xa5);
    eviction.fill(0x3c);
    let scrub_digest = eviction.sweep_lines();
    compiler_fence(Ordering::SeqCst);
    let scrub_ns = scrub_start.elapsed().as_nanos();
    let f2 = faults
        .read()
        .map_err(|error| format!("read scrub-end faults: {error}"))?;

    compiler_fence(Ordering::SeqCst);
    let timed_start = Instant::now();
    publish_pattern(mode, &mut destination, &ready.0);
    compiler_fence(Ordering::SeqCst);
    let timed_ns = timed_start.elapsed().as_nanos();
    // The timed boundary is release publication. The stronger barrier used
    // for same-thread verification is deliberately outside that interval.
    fence(Ordering::SeqCst);
    let f3 = faults
        .read()
        .map_err(|error| format!("read timed-end faults: {error}"))?;

    let verify_start = Instant::now();
    let published = ready.0.load(Ordering::Acquire);
    let verification = destination.verify_pattern();
    compiler_fence(Ordering::SeqCst);
    let verify_ns = verify_start.elapsed().as_nanos();
    let f4 = faults
        .read()
        .map_err(|error| format!("read verify-end faults: {error}"))?;

    let phase_faults = PhaseFaults {
        setup: f1
            .delta(f0)
            .map_err(|error| format!("setup fault delta: {error}"))?,
        scrub: f2
            .delta(f1)
            .map_err(|error| format!("scrub fault delta: {error}"))?,
        timed: f3
            .delta(f2)
            .map_err(|error| format!("timed fault delta: {error}"))?,
        verify: f4
            .delta(f3)
            .map_err(|error| format!("verify fault delta: {error}"))?,
    };
    let gib_per_second = size as f64 / timed_ns as f64 * 1e9 / 1024_f64.powi(3);

    println!(
        concat!(
            "{{\"schema\":1,\"kind\":\"write\",\"architecture\":\"{}\",",
            "\"mode\":\"{}\",\"implementation\":\"{}\",\"bytes\":{},",
            "\"setup_ns\":{},\"scrub_ns\":{},\"timed_ns\":{},\"verify_ns\":{},",
            "\"setup_minor_faults\":{},\"setup_major_faults\":{},",
            "\"scrub_minor_faults\":{},\"scrub_major_faults\":{},",
            "\"timed_minor_faults\":{},\"timed_major_faults\":{},",
            "\"verify_minor_faults\":{},\"verify_major_faults\":{},",
            "\"published\":{},\"bad_words\":{},\"digest\":\"{:016x}\",",
            "\"scrub_digest\":\"{:016x}\",\"gib_per_second\":{:.9}}}"
        ),
        architecture_name(),
        requested_mode,
        implementation,
        size,
        setup_ns,
        scrub_ns,
        timed_ns,
        verify_ns,
        phase_faults.setup.minor,
        phase_faults.setup.major,
        phase_faults.scrub.minor,
        phase_faults.scrub.major,
        phase_faults.timed.minor,
        phase_faults.timed.major,
        phase_faults.verify.minor,
        phase_faults.verify.major,
        published,
        verification.bad_words,
        verification.digest,
        scrub_digest,
        gib_per_second,
    );

    if published != 1 || verification.bad_words != 0 {
        return Err("write publication or full-pattern verification failed".to_owned());
    }
    if phase_faults.timed.minor != 0 || phase_faults.timed.major != 0 {
        return Err("timed write period incurred a page fault".to_owned());
    }
    Ok(())
}

fn run_stlf_benchmark(requested_mode: &str, iterations: u64) -> Result<(), String> {
    let (mode, implementation) =
        stlf_mode(requested_mode).ok_or_else(|| format!("unknown STLF mode: {requested_mode}"))?;
    if iterations == 0 {
        return Err("STLF iterations must be nonzero".to_owned());
    }
    if !write_kernels_supported() {
        return Err("required target is unavailable".to_owned());
    }

    let mut faults = ProcStat::open().map_err(|error| format!("open proc stat: {error}"))?;
    let f0 = faults
        .read()
        .map_err(|error| format!("read setup-start faults: {error}"))?;
    let setup_start = Instant::now();
    let mut buffer = AlignedBuffer::new(64);
    compiler_fence(Ordering::SeqCst);
    let setup_ns = setup_start.elapsed().as_nanos();
    let f1 = faults
        .read()
        .map_err(|error| format!("read setup-end faults: {error}"))?;

    let scrub_start = Instant::now();
    buffer.fill(0);
    buffer.initialize_stlf_fixture();
    compiler_fence(Ordering::SeqCst);
    let scrub_ns = scrub_start.elapsed().as_nanos();
    let f2 = faults
        .read()
        .map_err(|error| format!("read scrub-end faults: {error}"))?;

    compiler_fence(Ordering::SeqCst);
    let timed_start = Instant::now();
    let observed = run_stlf(mode, &mut buffer, iterations, STLF_SEED);
    compiler_fence(Ordering::SeqCst);
    let timed_ns = timed_start.elapsed().as_nanos();
    let f3 = faults
        .read()
        .map_err(|error| format!("read timed-end faults: {error}"))?;

    let verify_start = Instant::now();
    let expected = stlf_oracle(mode, iterations, STLF_SEED);
    let oracle_match = black_box(observed) == expected;
    compiler_fence(Ordering::SeqCst);
    let verify_ns = verify_start.elapsed().as_nanos();
    let f4 = faults
        .read()
        .map_err(|error| format!("read verify-end faults: {error}"))?;

    let phase_faults = PhaseFaults {
        setup: f1
            .delta(f0)
            .map_err(|error| format!("setup fault delta: {error}"))?,
        scrub: f2
            .delta(f1)
            .map_err(|error| format!("scrub fault delta: {error}"))?,
        timed: f3
            .delta(f2)
            .map_err(|error| format!("timed fault delta: {error}"))?,
        verify: f4
            .delta(f3)
            .map_err(|error| format!("verify fault delta: {error}"))?,
    };

    println!(
        concat!(
            "{{\"schema\":1,\"kind\":\"stlf\",\"architecture\":\"{}\",",
            "\"mode\":\"{}\",\"implementation\":\"{}\",\"iterations\":{},",
            "\"setup_ns\":{},\"scrub_ns\":{},\"timed_ns\":{},\"verify_ns\":{},",
            "\"setup_minor_faults\":{},\"setup_major_faults\":{},",
            "\"scrub_minor_faults\":{},\"scrub_major_faults\":{},",
            "\"timed_minor_faults\":{},\"timed_major_faults\":{},",
            "\"verify_minor_faults\":{},\"verify_major_faults\":{},",
            "\"result\":\"{:016x}\",\"oracle\":\"{:016x}\",",
            "\"oracle_match\":{},\"ns_per_iteration\":{:.9}}}"
        ),
        architecture_name(),
        requested_mode,
        implementation,
        iterations,
        setup_ns,
        scrub_ns,
        timed_ns,
        verify_ns,
        phase_faults.setup.minor,
        phase_faults.setup.major,
        phase_faults.scrub.minor,
        phase_faults.scrub.major,
        phase_faults.timed.minor,
        phase_faults.timed.major,
        phase_faults.verify.minor,
        phase_faults.verify.major,
        observed,
        expected,
        oracle_match,
        timed_ns as f64 / iterations as f64,
    );

    if !oracle_match {
        return Err("STLF result differs from the correctness oracle".to_owned());
    }
    if phase_faults.timed.minor != 0 || phase_faults.timed.major != 0 {
        return Err("timed STLF period incurred a page fault".to_owned());
    }
    Ok(())
}

fn run_check() -> Result<(), String> {
    if !write_kernels_supported() {
        return Err("required target features are unavailable".to_owned());
    }
    for mode in [WriteMode::Temporal, WriteMode::NonTemporal] {
        let mut destination = AlignedBuffer::new(64 * 1024);
        destination.fill(0xa5);
        let ready = Ready(AtomicU64::new(0));
        publish_pattern(mode, &mut destination, &ready.0);
        if ready.0.load(Ordering::Acquire) != 1 || destination.verify_pattern().bad_words != 0 {
            return Err(format!("write correctness check failed for {mode:?}"));
        }
    }
    for mode in [StlfMode::Exact, StlfMode::Partial] {
        let mut buffer = AlignedBuffer::new(64);
        buffer.initialize_stlf_fixture();
        let observed = run_stlf(mode, &mut buffer, 4_096, STLF_SEED);
        if observed != stlf_oracle(mode, 4_096, STLF_SEED) {
            return Err(format!("STLF correctness check failed for {mode:?}"));
        }
    }
    println!(
        "{{\"schema\":1,\"kind\":\"check\",\"architecture\":\"{}\",\"ok\":true}}",
        architecture_name()
    );
    Ok(())
}

fn parse_number<T: std::str::FromStr>(value: Option<String>, name: &str) -> Result<T, String> {
    value
        .ok_or_else(|| format!("missing {name}"))?
        .parse()
        .map_err(|_| format!("{name} must be a positive integer"))
}

fn main() -> ExitCode {
    let mut raw_args: Vec<String> = env::args().skip(1).collect();
    // `cargo bench` appends this harness marker even when `harness = false`.
    // Accept one trailing marker while preserving strict validation of every
    // experiment argument.
    if raw_args
        .last()
        .is_some_and(|argument| argument == "--bench")
    {
        raw_args.pop();
    }
    let mut args = raw_args.into_iter();
    let result = match args.next().as_deref() {
        Some("check") if args.len() == 0 => run_check(),
        Some("write") => {
            let mode = args.next().ok_or_else(|| "missing write MODE".to_owned());
            let mib = parse_number(args.next(), "MIB");
            match (mode, mib, args.next()) {
                (Ok(mode), Ok(mib), None) => run_write(&mode, mib),
                (_, _, Some(_)) => Err("too many write arguments".to_owned()),
                (Err(error), _, _) | (_, Err(error), _) => Err(error),
            }
        }
        Some("stlf") => {
            let mode = args.next().ok_or_else(|| "missing STLF MODE".to_owned());
            let iterations = parse_number(args.next(), "ITERATIONS");
            match (mode, iterations, args.next()) {
                (Ok(mode), Ok(iterations), None) => run_stlf_benchmark(&mode, iterations),
                (_, _, Some(_)) => Err("too many STLF arguments".to_owned()),
                (Err(error), _, _) | (_, Err(error), _) => Err(error),
            }
        }
        _ => Err("usage: write_path check | write MODE MIB | stlf MODE ITERATIONS".to_owned()),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
