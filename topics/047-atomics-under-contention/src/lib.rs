//! A checked Linux experiment for atomic counters under contention.
//!
//! The experiment compares four update shapes:
//!
//! - one shared [`AtomicU64`] updated with `fetch_add`;
//! - one shared [`AtomicU64`] updated by a weak compare-and-swap (CAS) loop;
//! - one 128-byte-aligned [`AtomicU64`] stripe per worker;
//! - thread-local batching followed by shared `fetch_add` operations.
//!
//! All measured counter operations use [`Ordering::Relaxed`]. This preserves
//! atomicity for the counter but does not publish unrelated memory. Stripes and
//! batching also weaken live-read semantics: stripes require a multi-location
//! sum, and a batched counter omits increments that have not yet been flushed.
//!
//! [`run_benchmark`] is available on every target so callers can compile and
//! test configuration code portably. It returns
//! [`BenchmarkError::UnsupportedPlatform`] unless the executable is running on
//! 64-bit AArch64 or x86-64 Linux with 64-bit atomic support.
//!
//! # Configuration example
//!
//! ```
//! use atomics_under_contention::{BenchmarkConfig, Mode};
//!
//! let config = BenchmarkConfig {
//!     mode: Mode::Batched,
//!     threads: 2,
//!     iterations_per_thread: 1_000,
//!     warmup_iterations_per_thread: 100,
//!     batch_size: 64,
//!     coordinator_cpu: 4,
//!     worker_cpus: vec![0, 2],
//! };
//!
//! assert_eq!(config.logical_operations().unwrap(), 2_000);
//! assert_eq!(config.measured_batch_flushes().unwrap(), 32);
//! assert!(config.validate().is_ok());
//! ```

#![deny(missing_docs)]

use std::fmt;
use std::hint::black_box;
use std::mem::{align_of, size_of};
use std::str::FromStr;
use std::sync::atomic::{AtomicU64, Ordering};

/// Byte alignment and stride used for every per-worker atomic stripe.
///
/// Adjacent stripes cannot share a 64-byte or 128-byte cache line. A target
/// with wider cache lines requires a wider stripe.
pub const STRIPE_ALIGNMENT: usize = 128;

// The Linux affinity implementation uses a 1,024-byte bit mask. Keeping the
// bound in common validation makes an invalid CPU index fail before threads are
// created and keeps the portable tests aligned with the Linux implementation.
const CPU_MASK_BITS: usize = 8_192;

/// Counter update shape selected for one fresh benchmark process.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Mode {
    /// Every logical increment performs `fetch_add` on one shared atomic.
    Shared,
    /// Every logical increment uses a weak compare-and-swap retry loop.
    Cas,
    /// Every worker updates its own 128-byte atomic stripe.
    Striped,
    /// Every worker accumulates locally and flushes to one shared atomic.
    Batched,
}

impl Mode {
    /// Returns the stable command-line and result-record spelling.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Shared => "shared",
            Self::Cas => "cas",
            Self::Striped => "striped",
            Self::Batched => "batched",
        }
    }
}

impl fmt::Display for Mode {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.as_str())
    }
}

/// Error returned when a counter mode name is not recognized.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ParseModeError;

impl fmt::Display for ParseModeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("mode must be shared, cas, striped, or batched")
    }
}

impl std::error::Error for ParseModeError {}

impl FromStr for Mode {
    type Err = ParseModeError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "shared" => Ok(Self::Shared),
            "cas" => Ok(Self::Cas),
            "striped" => Ok(Self::Striped),
            "batched" => Ok(Self::Batched),
            _ => Err(ParseModeError),
        }
    }
}

/// Fully specified inputs for one fresh benchmark process.
///
/// Worker CPU identifiers must be unique, must exclude `coordinator_cpu`, and
/// must already have been selected from the process's allowed Linux CPU set.
/// The caller is responsible for verifying physical-core, package, and
/// non-uniform memory access (NUMA) topology before combining process results.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BenchmarkConfig {
    /// Counter update shape used by every worker.
    pub mode: Mode,
    /// Number of worker threads.
    pub threads: usize,
    /// Logical increments executed by each worker in the measured phase.
    pub iterations_per_thread: u64,
    /// Logical increments executed by each worker before reset and measurement.
    pub warmup_iterations_per_thread: u64,
    /// Number of local increments per shared flush in [`Mode::Batched`].
    pub batch_size: u64,
    /// Logical CPU used by the coordinating thread.
    pub coordinator_cpu: usize,
    /// One exact logical CPU identifier for each worker, in worker order.
    pub worker_cpus: Vec<usize>,
}

impl BenchmarkConfig {
    /// Validates placement bounds, nonzero inputs, and every derived `u64` count.
    ///
    /// This check makes no system calls. It does not prove that a CPU belongs to
    /// the process's allowed set, that CPUs identify distinct physical cores,
    /// or that CPUs share a non-uniform memory access (NUMA) node. Record those
    /// host properties with each measurement.
    ///
    /// # Errors
    ///
    /// - Returns [`BenchmarkError::InvalidConfig`] when a required count is
    ///   zero, the worker list length differs from `threads`, a CPU identifier
    ///   exceeds the 8,192-bit mask, or worker placement overlaps.
    /// - Returns [`BenchmarkError::ArithmeticOverflow`] when a thread count or
    ///   derived operation count cannot be represented as `u64`.
    pub fn validate(&self) -> Result<(), BenchmarkError> {
        if self.threads == 0 {
            return Err(BenchmarkError::InvalidConfig("threads must be nonzero"));
        }
        if self.iterations_per_thread == 0 {
            return Err(BenchmarkError::InvalidConfig(
                "iterations_per_thread must be nonzero",
            ));
        }
        if self.warmup_iterations_per_thread == 0 {
            return Err(BenchmarkError::InvalidConfig(
                "warmup_iterations_per_thread must be nonzero",
            ));
        }
        if self.batch_size == 0 {
            return Err(BenchmarkError::InvalidConfig("batch_size must be nonzero"));
        }
        if self.worker_cpus.len() != self.threads {
            return Err(BenchmarkError::InvalidConfig(
                "worker_cpus length must equal threads",
            ));
        }
        if self.coordinator_cpu >= CPU_MASK_BITS {
            return Err(BenchmarkError::InvalidConfig(
                "coordinator CPU exceeds the 8192-CPU affinity mask",
            ));
        }
        for (index, cpu) in self.worker_cpus.iter().copied().enumerate() {
            if cpu >= CPU_MASK_BITS {
                return Err(BenchmarkError::InvalidConfig(
                    "worker CPU exceeds the 8192-CPU affinity mask",
                ));
            }
            if cpu == self.coordinator_cpu {
                return Err(BenchmarkError::InvalidConfig(
                    "worker CPUs must exclude the coordinator CPU",
                ));
            }
            if self.worker_cpus[..index].contains(&cpu) {
                return Err(BenchmarkError::InvalidConfig("worker CPUs must be unique"));
            }
        }

        self.logical_operations()?;
        checked_product(
            self.threads,
            self.warmup_iterations_per_thread,
            "warmup logical operation count",
        )?;
        self.measured_batch_flushes()?;
        Ok(())
    }

    /// Returns the exact number of measured logical increments.
    ///
    /// # Errors
    ///
    /// Returns [`BenchmarkError::ArithmeticOverflow`] when `threads` cannot be
    /// represented as `u64` or `threads * iterations_per_thread` overflows it.
    pub fn logical_operations(&self) -> Result<u64, BenchmarkError> {
        checked_product(
            self.threads,
            self.iterations_per_thread,
            "measured logical operation count",
        )
    }

    /// Returns the exact shared flush count for the measured batched kernel.
    ///
    /// The value is reported even when another mode is selected so a runner can
    /// validate a fixed configuration before assigning treatments.
    ///
    /// # Errors
    ///
    /// - Returns [`BenchmarkError::InvalidConfig`] when `batch_size` is zero.
    /// - Returns [`BenchmarkError::ArithmeticOverflow`] when `threads` cannot be
    ///   represented as `u64` or the total flush count overflows it.
    pub fn measured_batch_flushes(&self) -> Result<u64, BenchmarkError> {
        if self.batch_size == 0 {
            return Err(BenchmarkError::InvalidConfig("batch_size must be nonzero"));
        }
        let per_thread = self.iterations_per_thread.div_ceil(self.batch_size);
        checked_product(self.threads, per_thread, "measured batch flush count")
    }
}

fn checked_product(
    threads: usize,
    per_thread: u64,
    what: &'static str,
) -> Result<u64, BenchmarkError> {
    let threads = u64::try_from(threads).map_err(|_| BenchmarkError::ArithmeticOverflow(what))?;
    threads
        .checked_mul(per_thread)
        .ok_or(BenchmarkError::ArithmeticOverflow(what))
}

/// Failure from configuration validation, platform setup, or benchmark checks.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum BenchmarkError {
    /// A configuration invariant was violated.
    InvalidConfig(&'static str),
    /// A derived count could not be represented as `u64`.
    ArithmeticOverflow(&'static str),
    /// The target is not supported by the Linux affinity experiment.
    UnsupportedPlatform,
    /// The kernel rejected an affinity request or did not retain it exactly.
    Affinity {
        /// Coordinator or worker role whose placement failed.
        role: String,
        /// Requested logical CPU identifier.
        cpu: usize,
        /// Operating-system or verification error.
        detail: String,
    },
    /// A worker panicked after crossing the measured-completion barrier.
    WorkerPanicked {
        /// Zero-based worker index.
        worker: usize,
    },
    /// The post-join count differed from the checked expected count.
    CountMismatch {
        /// Checked `threads * iterations_per_thread` value.
        expected: u64,
        /// Shared count or checked sum of per-worker stripes.
        observed: u64,
    },
}

impl fmt::Display for BenchmarkError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidConfig(detail) => write!(formatter, "invalid benchmark config: {detail}"),
            Self::ArithmeticOverflow(what) => write!(formatter, "{what} overflows u64"),
            Self::UnsupportedPlatform => formatter.write_str(
                "the benchmark requires 64-bit AArch64 or x86-64 Linux with 64-bit atomics",
            ),
            Self::Affinity { role, cpu, detail } => {
                write!(formatter, "failed to pin {role} to CPU {cpu}: {detail}")
            }
            Self::WorkerPanicked { worker } => write!(formatter, "worker {worker} panicked"),
            Self::CountMismatch { expected, observed } => write!(
                formatter,
                "final count mismatch: expected {expected}, observed {observed}"
            ),
        }
    }
}

impl std::error::Error for BenchmarkError {}

/// Observation fields from one fresh benchmark process.
///
/// Results returned by [`run_benchmark`] have passed exact affinity and
/// final-count checks. For those returned results, the time fields partition
/// the internal benchmark interval exactly, so `total_ns` equals
/// `startup_ns + warmup_ns + steady_ns + teardown_ns`. The fields remain public
/// for serialization; callers can construct values that lack those guarantees.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BenchmarkResult {
    /// Counter update shape used by the process.
    pub mode: Mode,
    /// Number of worker threads.
    pub threads: usize,
    /// Measured logical increments per worker.
    pub iterations_per_thread: u64,
    /// Warmup logical increments per worker.
    pub warmup_iterations_per_thread: u64,
    /// Configured local batch size.
    pub batch_size: u64,
    /// Checked number of measured logical increments.
    pub logical_operations: u64,
    /// Attempted atomic read-modify-write (RMW) operations.
    ///
    /// Compare-and-swap mode includes failed software attempts. This field does
    /// not count cache-line transfers or retries hidden by the implementation.
    pub rmw_attempts: u64,
    /// Failed weak compare-and-swap (CAS) attempts; zero in every other mode.
    pub cas_retries: u64,
    /// Shared count or checked sum of all stripes after workers join.
    pub final_count: u64,
    /// Allocation, worker creation, affinity, and ready-barrier time.
    pub startup_ns: u128,
    /// Warmup, warmup completion barrier, and per-worker reset time.
    pub warmup_ns: u128,
    /// Start barrier, measured kernels, and completion barrier time.
    pub steady_ns: u128,
    /// Join, ending-placement checks, and final-count validation time.
    pub teardown_ns: u128,
    /// Exact sum of the four phase durations.
    pub total_ns: u128,
    /// Exact logical CPU requested for the coordinating thread.
    pub coordinator_cpu: usize,
    /// Exact requested logical CPU for every worker.
    pub worker_cpus: Vec<usize>,
    /// Logical CPU observed after each worker's affinity call.
    pub worker_start_cpus: Vec<usize>,
    /// Logical CPU observed after each worker's measured kernel.
    pub worker_end_cpus: Vec<usize>,
}

impl BenchmarkResult {
    /// Returns steady-state nanoseconds per logical increment.
    ///
    /// The quotient excludes startup, warmup, and teardown time.
    #[must_use]
    pub fn nanoseconds_per_logical_operation(&self) -> f64 {
        self.steady_ns as f64 / self.logical_operations as f64
    }
}

#[repr(C, align(128))]
struct PaddedAtomic(AtomicU64);

const _: () = assert!(align_of::<PaddedAtomic>() == STRIPE_ALIGNMENT);
const _: () = assert!(size_of::<PaddedAtomic>() == STRIPE_ALIGNMENT);

/// Executes one relaxed shared `fetch_add(1)` per logical increment.
///
/// The return value of `fetch_add` is intentionally unused. Inspect the final
/// linked symbol before naming the emitted instruction. The counter wraps
/// modulo 2^64.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic47_shared_fetch_add(counter: &AtomicU64, iterations: u64) {
    for index in 0..iterations {
        black_box(index);
        counter.fetch_add(1, Ordering::Relaxed);
    }
}

/// Executes weak relaxed compare-and-swap increments and returns failed attempts.
///
/// A retry can reflect an intervening value change or a spurious weak-CAS
/// failure. It is not a direct count of cache-line transfers.
/// The counter wraps modulo 2^64.
///
/// # Panics
///
/// Panics if the retry counter overflows `u64`. Because this exported function
/// uses the non-unwinding C application binary interface (ABI), that panic
/// terminates the process rather than unwinding to its caller.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic47_cas_increment(counter: &AtomicU64, iterations: u64) -> u64 {
    let mut retries = 0_u64;
    let mut observed = counter.load(Ordering::Relaxed);
    for index in 0..iterations {
        black_box(index);
        loop {
            match counter.compare_exchange_weak(
                observed,
                observed.wrapping_add(1),
                Ordering::Relaxed,
                Ordering::Relaxed,
            ) {
                Ok(_) => {
                    observed = observed.wrapping_add(1);
                    break;
                }
                Err(actual) => {
                    retries = retries.checked_add(1).expect("CAS retry count overflow");
                    observed = actual;
                }
            }
        }
    }
    retries
}

/// Executes one relaxed `fetch_add(1)` per increment on a worker's own stripe.
///
/// This separate symbol has the same local operation as
/// [`topic47_shared_fetch_add`]. Its runtime distinction comes from each worker
/// receiving a different 128-byte allocation slot. An optimizer may retain the
/// two stable symbol names at one shared code address because their bodies are
/// identical. The counter wraps modulo 2^64.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic47_striped_fetch_add(counter: &AtomicU64, iterations: u64) {
    for index in 0..iterations {
        black_box(index);
        counter.fetch_add(1, Ordering::Relaxed);
    }
}

/// Accumulates locally and returns the number of relaxed shared flushes.
///
/// A final partial batch is always flushed, so a caller that joins every worker
/// observes every logical increment. Batching withholds at most
/// `batch_size - 1` increments per progressing worker; this does not bound how
/// quickly a relaxed load observes a completed flush. The shared counter wraps
/// modulo 2^64. The flush count cannot exceed `iterations`.
///
/// # Panics
///
/// Panics if `batch_size` is zero. Because this exported function uses the
/// non-unwinding C application binary interface (ABI), that panic terminates
/// the process rather than unwinding to its caller.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic47_batched_fetch_add(
    counter: &AtomicU64,
    iterations: u64,
    batch_size: u64,
) -> u64 {
    assert!(batch_size > 0, "batch_size must be nonzero");
    let mut pending = 0_u64;
    let mut flushes = 0_u64;
    for index in 0..iterations {
        black_box(index);
        pending += 1;
        if pending == batch_size {
            counter.fetch_add(pending, Ordering::Relaxed);
            pending = 0;
            flushes = flushes.checked_add(1).expect("batch flush count overflow");
        }
    }
    if pending != 0 {
        counter.fetch_add(pending, Ordering::Relaxed);
        flushes = flushes.checked_add(1).expect("batch flush count overflow");
    }
    flushes
}

#[cfg(all(
    target_os = "linux",
    target_pointer_width = "64",
    target_has_atomic = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
))]
fn run_kernel(
    mode: Mode,
    worker: usize,
    shared: &AtomicU64,
    stripes: &[PaddedAtomic],
    iterations: u64,
    batch_size: u64,
) -> Result<(u64, u64), BenchmarkError> {
    match mode {
        Mode::Shared => {
            topic47_shared_fetch_add(shared, iterations);
            Ok((0, iterations))
        }
        Mode::Cas => {
            let retries = topic47_cas_increment(shared, iterations);
            let attempts = iterations
                .checked_add(retries)
                .ok_or(BenchmarkError::ArithmeticOverflow("CAS attempt count"))?;
            Ok((retries, attempts))
        }
        Mode::Striped => {
            topic47_striped_fetch_add(&stripes[worker].0, iterations);
            Ok((0, iterations))
        }
        Mode::Batched => {
            let flushes = topic47_batched_fetch_add(shared, iterations, batch_size);
            Ok((0, flushes))
        }
    }
}

/// Runs one checked benchmark process.
///
/// Worker creation and warmup are outside `steady_ns`. The steady interval
/// includes only the start barrier, measured kernels, and completion barrier.
/// On a supported target, once coordinator pinning succeeds, this function does
/// not restore the prior affinity. The thread therefore remains pinned after a
/// successful run and on later error paths. Run the experiment in a short-lived
/// process. The barriers have no timeout; a worker that stalls or panics before
/// the final barrier can keep the process from returning.
///
/// # Errors
///
/// - Returns [`BenchmarkError::InvalidConfig`] for a configuration violation or
///   an internal phase or operation-accounting mismatch.
/// - Returns [`BenchmarkError::ArithmeticOverflow`] when a derived count or
///   duration sum cannot be represented.
/// - Returns [`BenchmarkError::UnsupportedPlatform`] outside 64-bit AArch64 or
///   x86-64 Linux targets with 64-bit atomics.
/// - Returns [`BenchmarkError::Affinity`] when Linux rejects or changes an
///   exact one-CPU affinity request.
/// - Returns [`BenchmarkError::WorkerPanicked`] when `join` observes a worker
///   panic after the final barrier.
/// - Returns [`BenchmarkError::CountMismatch`] when the post-join counter does
///   not equal the checked logical-operation count.
pub fn run_benchmark(config: &BenchmarkConfig) -> Result<BenchmarkResult, BenchmarkError> {
    config.validate()?;
    platform::run(config)
}

#[cfg(all(
    target_os = "linux",
    target_pointer_width = "64",
    target_has_atomic = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
))]
mod platform {
    use super::*;
    use std::io;
    use std::sync::{Arc, Barrier};
    use std::thread;
    use std::time::Instant;

    const CPU_SET_WORDS: usize = CPU_MASK_BITS / u64::BITS as usize;

    #[repr(C)]
    #[derive(Clone, Eq, PartialEq)]
    struct CpuSet {
        bits: [u64; CPU_SET_WORDS],
    }

    unsafe extern "C" {
        fn sched_setaffinity(pid: i32, cpusetsize: usize, mask: *const CpuSet) -> i32;
        fn sched_getaffinity(pid: i32, cpusetsize: usize, mask: *mut CpuSet) -> i32;
        fn sched_getcpu() -> i32;
    }

    #[derive(Debug)]
    struct WorkerResult {
        placement_error: Option<String>,
        start_cpu: Option<usize>,
        end_cpu: Option<usize>,
        kernel_result: Result<(u64, u64), BenchmarkError>,
    }

    fn one_cpu_set(cpu: usize) -> CpuSet {
        let mut set = CpuSet {
            bits: [0; CPU_SET_WORDS],
        };
        set.bits[cpu / u64::BITS as usize] |= 1_u64 << (cpu % u64::BITS as usize);
        set
    }

    fn pin_current_thread(cpu: usize) -> Result<(), String> {
        let expected = one_cpu_set(cpu);
        // SAFETY: `expected` is initialized for the supplied size and remains
        // alive for the duration of the Linux system call.
        let set_result = unsafe { sched_setaffinity(0, size_of::<CpuSet>(), &expected) };
        if set_result != 0 {
            return Err(io::Error::last_os_error().to_string());
        }

        let mut observed = CpuSet {
            bits: [0; CPU_SET_WORDS],
        };
        // SAFETY: `observed` is writable for the supplied size and remains alive
        // for the duration of the Linux system call.
        let get_result = unsafe { sched_getaffinity(0, size_of::<CpuSet>(), &mut observed) };
        if get_result != 0 {
            return Err(io::Error::last_os_error().to_string());
        }
        if observed != expected {
            return Err("kernel did not retain the exact one-CPU affinity mask".to_string());
        }
        Ok(())
    }

    fn current_cpu() -> Result<usize, String> {
        // SAFETY: `sched_getcpu` takes no arguments and has no memory preconditions.
        let cpu = unsafe { sched_getcpu() };
        if cpu < 0 {
            Err(io::Error::last_os_error().to_string())
        } else {
            Ok(cpu as usize)
        }
    }

    fn affinity_error(role: String, cpu: usize, detail: String) -> BenchmarkError {
        BenchmarkError::Affinity { role, cpu, detail }
    }

    pub(super) fn run(config: &BenchmarkConfig) -> Result<BenchmarkResult, BenchmarkError> {
        pin_current_thread(config.coordinator_cpu).map_err(|detail| {
            affinity_error("coordinator".to_string(), config.coordinator_cpu, detail)
        })?;
        let coordinator_start = current_cpu().map_err(|detail| {
            affinity_error("coordinator".to_string(), config.coordinator_cpu, detail)
        })?;
        if coordinator_start != config.coordinator_cpu {
            return Err(affinity_error(
                "coordinator".to_string(),
                config.coordinator_cpu,
                format!("observed CPU {coordinator_start} after pinning"),
            ));
        }

        let total_start = Instant::now();
        let shared = Arc::new(AtomicU64::new(0));
        let stripes = Arc::new(
            (0..config.threads)
                .map(|_| PaddedAtomic(AtomicU64::new(0)))
                .collect::<Vec<_>>(),
        );
        let barrier = Arc::new(Barrier::new(config.threads + 1));
        let mut workers = Vec::with_capacity(config.threads);

        for (worker, requested_cpu) in config.worker_cpus.iter().copied().enumerate() {
            let shared = Arc::clone(&shared);
            let stripes = Arc::clone(&stripes);
            let barrier = Arc::clone(&barrier);
            let mode = config.mode;
            let iterations = config.iterations_per_thread;
            let warmup_iterations = config.warmup_iterations_per_thread;
            let batch_size = config.batch_size;

            workers.push(thread::spawn(move || {
                let mut placement_error = pin_current_thread(requested_cpu).err();
                let start_query = current_cpu();
                let start_cpu = start_query.as_ref().ok().copied();
                if placement_error.is_none() && start_cpu != Some(requested_cpu) {
                    placement_error = Some(match &start_query {
                        Ok(observed) => {
                            format!("observed CPU {observed} after requesting CPU {requested_cpu}")
                        }
                        Err(detail) => format!(
                            "could not read the CPU after requesting CPU {requested_cpu}: {detail}"
                        ),
                    });
                }
                let placement_valid = placement_error.is_none();

                // Ready, warmup start, warmup done, reset done, measured start,
                // and measured done each synchronize all workers with main.
                barrier.wait();
                barrier.wait();
                if placement_valid {
                    let _ = run_kernel(
                        mode,
                        worker,
                        &shared,
                        &stripes,
                        warmup_iterations,
                        batch_size,
                    );
                }
                barrier.wait();
                if placement_valid {
                    match mode {
                        Mode::Striped => stripes[worker].0.store(0, Ordering::Relaxed),
                        _ if worker == 0 => shared.store(0, Ordering::Relaxed),
                        _ => {}
                    }
                }
                barrier.wait();
                barrier.wait();
                let kernel_result = if placement_valid {
                    run_kernel(mode, worker, &shared, &stripes, iterations, batch_size)
                } else {
                    Ok((0, 0))
                };
                barrier.wait();

                let end_query = current_cpu();
                let end_cpu = end_query.as_ref().ok().copied();
                if placement_error.is_none() && end_cpu != Some(requested_cpu) {
                    placement_error = Some(match &end_query {
                        Ok(observed) => {
                            format!("observed CPU {observed} after requesting CPU {requested_cpu}")
                        }
                        Err(detail) => format!(
                            "could not read the CPU after requesting CPU {requested_cpu}: {detail}"
                        ),
                    });
                }
                WorkerResult {
                    placement_error,
                    start_cpu,
                    end_cpu,
                    kernel_result,
                }
            }));
        }

        barrier.wait();
        let startup_ns = total_start.elapsed().as_nanos();

        let warmup_start = Instant::now();
        barrier.wait();
        barrier.wait();
        barrier.wait();
        let warmup_ns = warmup_start.elapsed().as_nanos();

        let steady_start = Instant::now();
        barrier.wait();
        barrier.wait();
        let steady_ns = steady_start.elapsed().as_nanos();

        let worker_results = workers
            .into_iter()
            .enumerate()
            .map(|(worker, handle)| {
                handle
                    .join()
                    .map_err(|_| BenchmarkError::WorkerPanicked { worker })
            })
            .collect::<Result<Vec<_>, _>>()?;

        for (worker, result) in worker_results.iter().enumerate() {
            if let Some(detail) = &result.placement_error {
                return Err(affinity_error(
                    format!("worker {worker}"),
                    config.worker_cpus[worker],
                    detail.clone(),
                ));
            }
        }

        let mut cas_retries = 0_u64;
        let mut rmw_attempts = 0_u64;
        for result in &worker_results {
            let (retries, attempts) = result.kernel_result.clone()?;
            cas_retries = cas_retries
                .checked_add(retries)
                .ok_or(BenchmarkError::ArithmeticOverflow("CAS retry sum"))?;
            rmw_attempts = rmw_attempts
                .checked_add(attempts)
                .ok_or(BenchmarkError::ArithmeticOverflow("RMW attempt sum"))?;
        }

        let final_count = match config.mode {
            Mode::Striped => stripes.iter().try_fold(0_u64, |sum, stripe| {
                sum.checked_add(stripe.0.load(Ordering::Relaxed))
                    .ok_or(BenchmarkError::ArithmeticOverflow("stripe count sum"))
            })?,
            _ => shared.load(Ordering::Relaxed),
        };
        let logical_operations = config.logical_operations()?;
        if final_count != logical_operations {
            return Err(BenchmarkError::CountMismatch {
                expected: logical_operations,
                observed: final_count,
            });
        }

        let expected_attempts = match config.mode {
            Mode::Shared | Mode::Striped => logical_operations,
            Mode::Cas => logical_operations
                .checked_add(cas_retries)
                .ok_or(BenchmarkError::ArithmeticOverflow("CAS attempt count"))?,
            Mode::Batched => config.measured_batch_flushes()?,
        };
        if rmw_attempts != expected_attempts {
            return Err(BenchmarkError::InvalidConfig(
                "measured RMW attempt accounting violated its mode formula",
            ));
        }

        let coordinator_end = current_cpu().map_err(|detail| {
            affinity_error("coordinator".to_string(), config.coordinator_cpu, detail)
        })?;
        if coordinator_end != config.coordinator_cpu {
            return Err(affinity_error(
                "coordinator".to_string(),
                config.coordinator_cpu,
                format!("observed CPU {coordinator_end} after measurement"),
            ));
        }

        let elapsed_ns = total_start.elapsed().as_nanos();
        let accounted_ns = startup_ns
            .checked_add(warmup_ns)
            .and_then(|value| value.checked_add(steady_ns))
            .ok_or(BenchmarkError::ArithmeticOverflow("phase duration sum"))?;
        let teardown_ns =
            elapsed_ns
                .checked_sub(accounted_ns)
                .ok_or(BenchmarkError::InvalidConfig(
                    "phase clocks did not form a monotonic partition",
                ))?;
        let total_ns = accounted_ns
            .checked_add(teardown_ns)
            .ok_or(BenchmarkError::ArithmeticOverflow("total duration"))?;

        Ok(BenchmarkResult {
            mode: config.mode,
            threads: config.threads,
            iterations_per_thread: config.iterations_per_thread,
            warmup_iterations_per_thread: config.warmup_iterations_per_thread,
            batch_size: config.batch_size,
            logical_operations,
            rmw_attempts,
            cas_retries,
            final_count,
            startup_ns,
            warmup_ns,
            steady_ns,
            teardown_ns,
            total_ns,
            coordinator_cpu: config.coordinator_cpu,
            worker_cpus: config.worker_cpus.clone(),
            worker_start_cpus: worker_results
                .iter()
                .map(|result| result.start_cpu.expect("validated worker start CPU"))
                .collect(),
            worker_end_cpus: worker_results
                .iter()
                .map(|result| result.end_cpu.expect("validated worker end CPU"))
                .collect(),
        })
    }
}

#[cfg(not(all(
    target_os = "linux",
    target_pointer_width = "64",
    target_has_atomic = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
)))]
mod platform {
    use super::*;

    pub(super) fn run(_config: &BenchmarkConfig) -> Result<BenchmarkResult, BenchmarkError> {
        Err(BenchmarkError::UnsupportedPlatform)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    fn config(mode: Mode) -> BenchmarkConfig {
        BenchmarkConfig {
            mode,
            threads: 2,
            iterations_per_thread: 65,
            warmup_iterations_per_thread: 7,
            batch_size: 64,
            coordinator_cpu: 4,
            worker_cpus: vec![0, 2],
        }
    }

    #[test]
    fn modes_round_trip_through_the_cli_names() {
        for mode in [Mode::Shared, Mode::Cas, Mode::Striped, Mode::Batched] {
            assert_eq!(mode.as_str().parse::<Mode>(), Ok(mode));
        }
        assert_eq!("unknown".parse::<Mode>(), Err(ParseModeError));
    }

    #[test]
    fn configuration_checks_counts_and_placement() {
        let valid = config(Mode::Batched);
        assert_eq!(valid.logical_operations(), Ok(130));
        assert_eq!(valid.measured_batch_flushes(), Ok(4));
        assert_eq!(valid.validate(), Ok(()));

        let mut duplicate = valid.clone();
        duplicate.worker_cpus = vec![0, 0];
        assert!(matches!(
            duplicate.validate(),
            Err(BenchmarkError::InvalidConfig("worker CPUs must be unique"))
        ));

        let overflowing = BenchmarkConfig {
            iterations_per_thread: u64::MAX,
            ..valid
        };
        assert!(matches!(
            overflowing.validate(),
            Err(BenchmarkError::ArithmeticOverflow(
                "measured logical operation count"
            ))
        ));
    }

    #[test]
    fn shared_and_cas_kernels_are_exact_under_contention() {
        for mode in [Mode::Shared, Mode::Cas] {
            let counter = Arc::new(AtomicU64::new(0));
            let mut workers = Vec::new();
            for _ in 0..4 {
                let counter = Arc::clone(&counter);
                workers.push(thread::spawn(move || match mode {
                    Mode::Shared => topic47_shared_fetch_add(&counter, 10_000),
                    Mode::Cas => {
                        topic47_cas_increment(&counter, 10_000);
                    }
                    _ => unreachable!(),
                }));
            }
            for worker in workers {
                worker.join().unwrap();
            }
            assert_eq!(counter.load(Ordering::Relaxed), 40_000);
        }
    }

    #[test]
    fn batched_kernel_flushes_a_partial_tail() {
        let counter = AtomicU64::new(0);
        assert_eq!(topic47_batched_fetch_add(&counter, 130, 64), 3);
        assert_eq!(counter.load(Ordering::Relaxed), 130);
    }

    #[test]
    fn stripes_have_the_declared_alignment_and_stride() {
        let stripes = [
            PaddedAtomic(AtomicU64::new(0)),
            PaddedAtomic(AtomicU64::new(0)),
        ];
        let first = (&raw const stripes[0]) as usize;
        let second = (&raw const stripes[1]) as usize;
        assert_eq!(align_of::<PaddedAtomic>(), STRIPE_ALIGNMENT);
        assert_eq!(size_of::<PaddedAtomic>(), STRIPE_ALIGNMENT);
        assert_eq!(second.abs_diff(first), STRIPE_ALIGNMENT);

        topic47_striped_fetch_add(&stripes[0].0, 11);
        topic47_striped_fetch_add(&stripes[1].0, 13);
        assert_eq!(stripes[0].0.load(Ordering::Relaxed), 11);
        assert_eq!(stripes[1].0.load(Ordering::Relaxed), 13);
    }
}
