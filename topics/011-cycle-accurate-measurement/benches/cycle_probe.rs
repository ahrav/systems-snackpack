//! Linux reference-counter and monotonic-clock batching experiment.

use std::{env, process};

use systems_snackpack_topic_011::{
    dependent_chain, endpoint_delta_ns, minimum_batch_duration, recurrence_step,
};

#[cfg(target_os = "linux")]
const DEFAULT_SAMPLES: usize = 500;
#[cfg(target_os = "linux")]
const DEFAULT_PROBE_READS: usize = 1_000_000;
#[cfg(target_os = "linux")]
const WARMUP_STEPS: usize = 1_000_000;
#[cfg(target_os = "linux")]
const BATCHES: [usize; 4] = [1, 16, 256, 65_536];
const SEED: u64 = 0x243f_6a88_85a3_08d3;

fn verify() {
    assert_eq!(endpoint_delta_ns(100, 223, 1, 0), Ok(123));
    assert_eq!(endpoint_delta_ns(1024, 2048, 1000, 10), Ok(1000));
    assert_eq!(endpoint_delta_ns(5, 9, 3, 1), Ok(6));
    assert_eq!(endpoint_delta_ns(1, 2, 3, 1), Ok(2));
    assert_eq!(minimum_batch_duration(40, 10_000), Ok(8_000));

    let mut expected = SEED;
    for _ in 0..37 {
        expected = recurrence_step(expected);
    }
    assert_eq!(dependent_chain(SEED, 37), expected);
    println!("VERIFY conversion_vectors=4 dependency_steps=37 status=ok");
}

#[cfg(target_os = "linux")]
fn parse_positive(value: &str, name: &str) -> Result<usize, String> {
    let parsed = value
        .parse::<usize>()
        .map_err(|error| format!("invalid {name} {value:?}: {error}"))?;
    if parsed == 0 {
        return Err(format!("{name} must be positive"));
    }
    Ok(parsed)
}

#[cfg(target_os = "linux")]
mod linux {
    use std::{arch::asm, cmp, hint::black_box, process};

    #[cfg(target_arch = "aarch64")]
    use std::process::Command;
    #[cfg(target_arch = "x86_64")]
    use std::{thread, time::Duration};

    use super::{BATCHES, DEFAULT_PROBE_READS, DEFAULT_SAMPLES, SEED, WARMUP_STEPS};
    use systems_snackpack_topic_011::dependent_chain;

    const CLOCK_MONOTONIC_RAW: i32 = 4;

    #[repr(C)]
    struct Timespec {
        tv_sec: i64,
        tv_nsec: i64,
    }

    unsafe extern "C" {
        fn clock_gettime(clock_id: i32, value: *mut Timespec) -> i32;
        fn clock_getres(clock_id: i32, value: *mut Timespec) -> i32;
        fn sched_getcpu() -> i32;
    }

    fn raw_clock_ns() -> Result<u64, String> {
        let mut value = Timespec {
            tv_sec: 0,
            tv_nsec: 0,
        };
        // SAFETY: `value` points to writable storage for one `timespec`.
        let rc = unsafe { clock_gettime(CLOCK_MONOTONIC_RAW, &raw mut value) };
        if rc != 0 || value.tv_sec < 0 || value.tv_nsec < 0 {
            return Err(format!(
                "clock_gettime(CLOCK_MONOTONIC_RAW) failed: {}",
                std::io::Error::last_os_error()
            ));
        }
        u64::try_from(value.tv_sec)
            .ok()
            .and_then(|seconds| seconds.checked_mul(1_000_000_000))
            .and_then(|base| u64::try_from(value.tv_nsec).ok()?.checked_add(base))
            .ok_or_else(|| "CLOCK_MONOTONIC_RAW value overflowed u64".to_owned())
    }

    fn raw_clock_resolution_ns() -> Result<u64, String> {
        let mut value = Timespec {
            tv_sec: 0,
            tv_nsec: 0,
        };
        // SAFETY: `value` points to writable storage for one `timespec`.
        let rc = unsafe { clock_getres(CLOCK_MONOTONIC_RAW, &raw mut value) };
        if rc != 0 || value.tv_sec < 0 || value.tv_nsec < 0 {
            return Err(format!(
                "clock_getres(CLOCK_MONOTONIC_RAW) failed: {}",
                std::io::Error::last_os_error()
            ));
        }
        u64::try_from(value.tv_sec)
            .ok()
            .and_then(|seconds| seconds.checked_mul(1_000_000_000))
            .and_then(|base| u64::try_from(value.tv_nsec).ok()?.checked_add(base))
            .ok_or_else(|| "CLOCK_MONOTONIC_RAW resolution overflowed u64".to_owned())
    }

    fn current_cpu() -> Result<u32, String> {
        // SAFETY: `sched_getcpu` has no pointer arguments or caller obligations.
        let cpu = unsafe { sched_getcpu() };
        u32::try_from(cpu)
            .map_err(|_| format!("sched_getcpu failed: {}", std::io::Error::last_os_error()))
    }

    #[derive(Clone, Copy)]
    enum CounterKind {
        #[cfg(target_arch = "aarch64")]
        ArmGenericTimer,
        #[cfg(target_arch = "x86_64")]
        X86RdtscpCpuid,
    }

    #[derive(Clone, Copy)]
    struct CounterRead {
        ticks: u64,
        aux: Option<u32>,
    }

    struct Counter {
        kind: CounterKind,
        frequency_hz: u64,
        frequency_source: &'static str,
        bracket: &'static str,
        features: String,
    }

    impl Counter {
        fn detect() -> Result<Self, String> {
            #[cfg(target_arch = "aarch64")]
            {
                let output =
                    Command::new(std::env::current_exe().map_err(|error| error.to_string())?)
                        .arg("--counter-smoke-child")
                        .output()
                        .map_err(|error| format!("failed to start counter smoke child: {error}"))?;
                if !output.status.success() {
                    return Err(format!(
                        "CNTVCT_EL0 access failed in smoke child: status={}",
                        output.status
                    ));
                }
                let text = String::from_utf8(output.stdout)
                    .map_err(|error| format!("counter smoke output was not UTF-8: {error}"))?;
                let frequency_hz = text
                    .split_whitespace()
                    .find_map(|field| field.strip_prefix("frequency_hz="))
                    .ok_or_else(|| "counter smoke child omitted frequency_hz".to_owned())?
                    .parse::<u64>()
                    .map_err(|error| format!("invalid counter smoke frequency: {error}"))?;
                if frequency_hz == 0 {
                    return Err("CNTFRQ_EL0 reported zero".to_owned());
                }
                return Ok(Self {
                    kind: CounterKind::ArmGenericTimer,
                    frequency_hz,
                    frequency_source: "cntfrq_el0",
                    bracket: "isb-mrs-cntvct-isb",
                    features: "cntvct_smoke=ok".to_owned(),
                });
            }

            #[cfg(target_arch = "x86_64")]
            {
                use std::arch::x86_64::{__cpuid, __cpuid_count};

                // SAFETY: CPUID is available in x86-64 user mode.
                let vendor_leaf = unsafe { __cpuid(0) };
                let mut vendor_bytes = [0_u8; 12];
                vendor_bytes[0..4].copy_from_slice(&vendor_leaf.ebx.to_le_bytes());
                vendor_bytes[4..8].copy_from_slice(&vendor_leaf.edx.to_le_bytes());
                vendor_bytes[8..12].copy_from_slice(&vendor_leaf.ecx.to_le_bytes());
                let vendor = std::str::from_utf8(&vendor_bytes)
                    .map_err(|error| format!("invalid CPUID vendor string: {error}"))?;

                // SAFETY: CPUID is available in x86-64 user mode.
                let max_extended = unsafe { __cpuid(0x8000_0000) }.eax;
                if max_extended < 0x8000_0007 {
                    return Err("CPUID does not enumerate invariant TSC".to_owned());
                }
                // SAFETY: The maximum extended leaf covers 0x8000_0007.
                let invariant = unsafe { __cpuid(0x8000_0007) }.edx & (1 << 8) != 0;
                // SAFETY: CPUID leaf 1 is available on x86-64.
                let tsc = unsafe { __cpuid(1) }.edx & (1 << 4) != 0;
                if !tsc || !invariant {
                    return Err(format!(
                        "required x86 features unavailable: tsc={tsc} invariant_tsc={invariant}"
                    ));
                }

                // SAFETY: The maximum extended leaf covers 0x8000_0001.
                let rdtscp = unsafe { __cpuid(0x8000_0001) }.edx & (1 << 27) != 0;
                if !rdtscp {
                    return Err("required x86 feature unavailable: rdtscp=false".to_owned());
                }
                let kind = CounterKind::X86RdtscpCpuid;
                let bracket = "rdtscp-cpuid";

                let max_basic = vendor_leaf.eax;
                let (frequency_hz, frequency_source, calibration_features) = if max_basic >= 0x15 {
                    // SAFETY: The maximum basic leaf covers leaf 0x15.
                    let leaf = unsafe { __cpuid_count(0x15, 0) };
                    if leaf.eax != 0 && leaf.ebx != 0 && leaf.ecx != 0 {
                        let frequency =
                            u128::from(leaf.ecx) * u128::from(leaf.ebx) / u128::from(leaf.eax);
                        (
                            u64::try_from(frequency)
                                .map_err(|_| "CPUID 0x15 frequency overflowed u64")?,
                            "cpuid_0x15",
                            "calibration=not_required".to_owned(),
                        )
                    } else {
                        let (frequency, details) = runtime_calibration(kind)?;
                        (frequency, "runtime_monotonic_raw_10x100ms_median", details)
                    }
                } else {
                    let (frequency, details) = runtime_calibration(kind)?;
                    (frequency, "runtime_monotonic_raw_10x100ms_median", details)
                };

                return Ok(Self {
                    kind,
                    frequency_hz,
                    frequency_source,
                    bracket,
                    features: format!(
                        "vendor={vendor} tsc={tsc} rdtscp={rdtscp} invariant_tsc={invariant} {calibration_features}"
                    ),
                });
            }

            #[allow(unreachable_code)]
            Err("architectural reference-counter path is unsupported".to_owned())
        }

        fn read(&self) -> CounterRead {
            read_counter(self.kind)
        }
    }

    #[cfg(target_arch = "aarch64")]
    #[inline(never)]
    fn read_counter(_kind: CounterKind) -> CounterRead {
        let value: u64;
        // Omitting `nomem` keeps compiler memory accesses outside the bracket.
        // SAFETY: `Counter::detect` first executes this instruction in a child;
        // a parent benchmark reaches this path only after EL0 access succeeds.
        unsafe {
            asm!(
                "isb",
                "mrs {value}, cntvct_el0",
                "isb",
                value = out(reg) value,
                options(nostack)
            );
        }
        CounterRead {
            ticks: value,
            aux: None,
        }
    }

    #[cfg(target_arch = "aarch64")]
    fn arm_frequency() -> u64 {
        let value: u64;
        // SAFETY: CNTFRQ_EL0 is readable at EL0 when the smoke child reaches
        // this function; the parent rejects a trapped child.
        unsafe {
            asm!("mrs {value}, cntfrq_el0", value = out(reg) value, options(nomem, nostack));
        }
        value
    }

    #[cfg(target_arch = "x86_64")]
    #[inline(never)]
    fn read_counter(_kind: CounterKind) -> CounterRead {
        let ticks: u64;
        let aux: u32;
        // Omitting `nomem` keeps compiler memory accesses outside the bracket.
        // RDTSCP waits for earlier instruction execution and load visibility;
        // it is not a store-visibility boundary. CPUID prevents later work from
        // executing before the endpoint completes. RDI temporarily preserves
        // RBX because LLVM reserves RBX on some x86-64 targets.
        // SAFETY: `Counter::detect` checks TSC, RDTSCP, and invariant TSC.
        unsafe {
            asm!(
                "rdtscp",
                "shl rdx, 32",
                "or rax, rdx",
                "mov r8, rax",
                "mov r9d, ecx",
                "mov rdi, rbx",
                "xor eax, eax",
                "cpuid",
                "mov rbx, rdi",
                out("r8") ticks,
                out("r9") aux,
                lateout("rax") _,
                lateout("rcx") _,
                lateout("rdx") _,
                lateout("rdi") _,
            );
        }
        CounterRead {
            ticks,
            aux: Some(aux),
        }
    }

    #[cfg(target_arch = "x86_64")]
    fn runtime_calibration(kind: CounterKind) -> Result<(u64, String), String> {
        const ROUNDS: usize = 10;
        let mut frequencies = Vec::with_capacity(ROUNDS);
        for round in 0..ROUNDS {
            let cpu_before = current_cpu()?;
            let (start_tick, start_ns, end_tick, end_ns) = if round % 2 == 0 {
                let start_ns = raw_clock_ns()?;
                let start_tick = read_counter(kind);
                thread::sleep(Duration::from_millis(100));
                let end_tick = read_counter(kind);
                let end_ns = raw_clock_ns()?;
                (start_tick, start_ns, end_tick, end_ns)
            } else {
                let start_tick = read_counter(kind);
                let start_ns = raw_clock_ns()?;
                thread::sleep(Duration::from_millis(100));
                let end_ns = raw_clock_ns()?;
                let end_tick = read_counter(kind);
                (start_tick, start_ns, end_tick, end_ns)
            };
            let cpu_after = current_cpu()?;
            if cpu_before != cpu_after {
                return Err("process migrated during TSC calibration".to_owned());
            }
            let elapsed_ns = end_ns
                .checked_sub(start_ns)
                .ok_or_else(|| "raw clock moved backward during calibration".to_owned())?;
            if start_tick.aux != end_tick.aux {
                return Err("TSC_AUX changed during TSC calibration".to_owned());
            }
            let elapsed_ticks = end_tick
                .ticks
                .checked_sub(start_tick.ticks)
                .ok_or_else(|| "TSC moved backward during calibration".to_owned())?;
            if elapsed_ns == 0 {
                return Err("zero-duration TSC calibration".to_owned());
            }
            let frequency = u128::from(elapsed_ticks) * 1_000_000_000_u128 / u128::from(elapsed_ns);
            frequencies.push(
                u64::try_from(frequency)
                    .map_err(|_| "runtime TSC frequency overflowed u64".to_owned())?,
            );
        }

        let frequency_hz = median_rounded(&mut frequencies);
        let minimum_hz = *frequencies.first().expect("ten calibration rounds");
        let maximum_hz = *frequencies.last().expect("ten calibration rounds");
        let mut deviations = frequencies
            .iter()
            .map(|frequency| frequency.abs_diff(frequency_hz))
            .collect::<Vec<_>>();
        let mad_hz = median_rounded(&mut deviations);
        Ok((
            frequency_hz,
            format!(
                "calibration_rounds={ROUNDS} calibration_order=5_counter-inner_5_counter-outer calibration_mad_hz={mad_hz} calibration_range_hz={minimum_hz}-{maximum_hz}"
            ),
        ))
    }

    fn smoke_child() -> Result<(), String> {
        #[cfg(target_arch = "aarch64")]
        {
            let frequency_hz = arm_frequency();
            let first = read_counter(CounterKind::ArmGenericTimer);
            let second = read_counter(CounterKind::ArmGenericTimer);
            if frequency_hz == 0 || second.ticks < first.ticks {
                return Err("Arm counter smoke check failed".to_owned());
            }
            println!(
                "COUNTER_SMOKE frequency_hz={frequency_hz} delta_ticks={}",
                second.ticks - first.ticks
            );
            return Ok(());
        }

        #[allow(unreachable_code)]
        Err("counter smoke child is only used on aarch64".to_owned())
    }

    fn median_twice(values: &mut [u64]) -> u128 {
        // Preserve even-length medians as exact doubled integers.
        values.sort_unstable();
        let middle = values.len() / 2;
        if values.len() % 2 == 1 {
            u128::from(values[middle]) * 2
        } else {
            u128::from(values[middle - 1]) + u128::from(values[middle])
        }
    }

    #[cfg(target_arch = "x86_64")]
    fn median_rounded(values: &mut [u64]) -> u64 {
        // Calibration frequency is integral Hz, so round its exact median once.
        u64::try_from(median_twice(values).div_ceil(2)).expect("median of u64 values fits u64")
    }

    fn comma_separated(values: &[u64]) -> String {
        values
            .iter()
            .map(u64::to_string)
            .collect::<Vec<_>>()
            .join(",")
    }

    fn display_aux(aux: Option<u32>) -> String {
        aux.map_or_else(|| "none".to_owned(), |value| value.to_string())
    }

    struct BatchResult {
        ticks: Vec<u64>,
        nanoseconds: Vec<u64>,
        rejected_counter: usize,
        rejected_clock: usize,
        checksum: u64,
    }

    fn measure_counter(counter: &Counter, state: u64, batch: usize) -> Result<(u64, u64), String> {
        let cpu_before = current_cpu()?;
        let start = counter.read();
        let next = dependent_chain(black_box(state), batch);
        let end = counter.read();
        let cpu_after = current_cpu()?;
        if cpu_before != cpu_after || start.aux != end.aux || end.ticks < start.ticks {
            return Err("counter sample migrated or moved backward".to_owned());
        }
        Ok((end.ticks - start.ticks, next))
    }

    fn measure_clock(state: u64, batch: usize) -> Result<(u64, u64), String> {
        let cpu_before = current_cpu()?;
        let start = raw_clock_ns()?;
        let next = dependent_chain(black_box(state), batch);
        let end = raw_clock_ns()?;
        let cpu_after = current_cpu()?;
        if cpu_before != cpu_after || end < start {
            return Err("clock sample migrated or moved backward".to_owned());
        }
        Ok((end - start, next))
    }

    fn run_batch(
        counter: &Counter,
        order: &str,
        batch: usize,
        samples: usize,
        mut state: u64,
    ) -> BatchResult {
        let mut ticks = Vec::with_capacity(samples);
        let mut nanoseconds = Vec::with_capacity(samples);
        let mut rejected_counter = 0;
        let mut rejected_clock = 0;

        for sample in 0..samples {
            state = state.wrapping_add(sample as u64);
            let counter_first = order == "raw-first";
            if counter_first {
                match measure_counter(counter, state, batch) {
                    Ok((elapsed, next)) => {
                        ticks.push(elapsed);
                        state = next;
                    }
                    Err(_) => rejected_counter += 1,
                }
                match measure_clock(state, batch) {
                    Ok((elapsed, next)) => {
                        nanoseconds.push(elapsed);
                        state = next;
                    }
                    Err(_) => rejected_clock += 1,
                }
            } else {
                match measure_clock(state, batch) {
                    Ok((elapsed, next)) => {
                        nanoseconds.push(elapsed);
                        state = next;
                    }
                    Err(_) => rejected_clock += 1,
                }
                match measure_counter(counter, state, batch) {
                    Ok((elapsed, next)) => {
                        ticks.push(elapsed);
                        state = next;
                    }
                    Err(_) => rejected_counter += 1,
                }
            }
        }

        BatchResult {
            ticks,
            nanoseconds,
            rejected_counter,
            rejected_clock,
            checksum: state,
        }
    }

    fn probe(reads: usize) -> Result<(), String> {
        let counter = Counter::detect()?;
        let start_cpu = current_cpu()?;
        let mut previous = counter.read();
        let start_aux = previous.aux;
        let mut aux_changes = 0_usize;
        let mut zero = 0_usize;
        let mut backward = 0_usize;
        let mut minimum = u64::MAX;
        let mut maximum = 0_u64;
        let mut gcd = 0_u64;
        for _ in 0..reads {
            let current = counter.read();
            if current.aux != previous.aux {
                aux_changes += 1;
            }
            if current.ticks < previous.ticks {
                backward += 1;
            } else if current.ticks == previous.ticks {
                zero += 1;
            } else {
                let delta = current.ticks - previous.ticks;
                minimum = cmp::min(minimum, delta);
                maximum = cmp::max(maximum, delta);
                gcd = gcd_u64(gcd, delta);
            }
            previous = current;
        }
        let end_cpu = current_cpu()?;
        println!(
            "PROBE_COUNTER arch={} bracket={} features={} frequency_hz={} frequency_source={} reads={} zero={} backward={} aux_changes={} start_aux={} end_aux={} min_nonzero_ticks={} max_ticks={} gcd_ticks={} start_cpu={} end_cpu={}",
            std::env::consts::ARCH,
            counter.bracket,
            counter.features.replace(' ', "_"),
            counter.frequency_hz,
            counter.frequency_source,
            reads,
            zero,
            backward,
            aux_changes,
            display_aux(start_aux),
            display_aux(previous.aux),
            if minimum == u64::MAX { 0 } else { minimum },
            maximum,
            gcd,
            start_cpu,
            end_cpu
        );
        if start_cpu != end_cpu {
            return Err("counter probe migrated between CPUs".to_owned());
        }
        if backward != 0 {
            return Err(format!("counter probe observed {backward} backward reads"));
        }
        if aux_changes != 0 {
            return Err(format!(
                "counter probe observed {aux_changes} TSC_AUX changes"
            ));
        }
        if minimum == u64::MAX {
            return Err("counter probe observed no advancing read".to_owned());
        }

        let resolution = raw_clock_resolution_ns()?;
        let clock_start_cpu = current_cpu()?;
        let mut previous = raw_clock_ns()?;
        let mut zero = 0_usize;
        let mut backward = 0_usize;
        let mut minimum = u64::MAX;
        let mut maximum = 0_u64;
        for _ in 0..cmp::min(reads, 200_000) {
            let current = raw_clock_ns()?;
            if current < previous {
                backward += 1;
            } else if current == previous {
                zero += 1;
            } else {
                let delta = current - previous;
                minimum = cmp::min(minimum, delta);
                maximum = cmp::max(maximum, delta);
            }
            previous = current;
        }
        let clock_end_cpu = current_cpu()?;
        println!(
            "PROBE_CLOCK clock=monotonic_raw advertised_resolution_ns={} reads={} zero={} backward={} min_nonzero_ns={} max_ns={} start_cpu={} end_cpu={}",
            resolution,
            cmp::min(reads, 200_000),
            zero,
            backward,
            if minimum == u64::MAX { 0 } else { minimum },
            maximum,
            clock_start_cpu,
            clock_end_cpu
        );
        if clock_start_cpu != clock_end_cpu {
            return Err("clock probe migrated between CPUs".to_owned());
        }
        if backward != 0 {
            return Err(format!("clock probe observed {backward} backward reads"));
        }
        if minimum == u64::MAX {
            return Err("clock probe observed no advancing read".to_owned());
        }
        Ok(())
    }

    fn gcd_u64(mut left: u64, mut right: u64) -> u64 {
        while right != 0 {
            let next = left % right;
            left = right;
            right = next;
        }
        left
    }

    fn run(order: &str, samples: usize) -> Result<(), String> {
        if order != "raw-first" && order != "clock-first" {
            return Err("order must be raw-first or clock-first".to_owned());
        }
        let counter = Counter::detect()?;
        let start_cpu = current_cpu()?;
        let start_aux = counter.read().aux;
        let mut state = dependent_chain(SEED, WARMUP_STEPS);
        println!(
            "RUN pid={} order={} samples={} warmup_steps={} frequency_hz={} frequency_source={} bracket={} arch={} start_cpu={} start_aux={} features={}",
            process::id(),
            order,
            samples,
            WARMUP_STEPS,
            counter.frequency_hz,
            counter.frequency_source,
            counter.bracket,
            std::env::consts::ARCH,
            start_cpu,
            display_aux(start_aux),
            counter.features.replace(' ', "_")
        );

        let mut total_rejected_counter = 0;
        let mut total_rejected_clock = 0;
        for batch in BATCHES {
            let result = run_batch(&counter, order, batch, samples, state);
            if result.ticks.is_empty() || result.nanoseconds.is_empty() {
                return Err(format!("batch {batch} produced no valid samples"));
            }
            state = result.checksum;
            total_rejected_counter += result.rejected_counter;
            total_rejected_clock += result.rejected_clock;
            let min_ticks = *result.ticks.iter().min().expect("checked nonempty");
            let min_ns = *result.nanoseconds.iter().min().expect("checked nonempty");
            let valid_counter = result.ticks.len();
            let valid_clock = result.nanoseconds.len();
            let median_ticks_x2 = median_twice(&mut result.ticks.clone());
            let median_ns_x2 = median_twice(&mut result.nanoseconds.clone());
            println!(
                "BATCH pid={} order={} batch={} requested_samples={} valid_counter={} valid_clock={} rejected_counter={} rejected_clock={} min_ticks={} median_ticks_x2={} min_ns={} median_ns_x2={} min_ticks_per_op={:.9} median_ticks_per_op={:.9} min_ns_per_op={:.9} median_ns_per_op={:.9}",
                process::id(),
                order,
                batch,
                samples,
                valid_counter,
                valid_clock,
                result.rejected_counter,
                result.rejected_clock,
                min_ticks,
                median_ticks_x2,
                min_ns,
                median_ns_x2,
                min_ticks as f64 / batch as f64,
                median_ticks_x2 as f64 / (2.0 * batch as f64),
                min_ns as f64 / batch as f64,
                median_ns_x2 as f64 / (2.0 * batch as f64)
            );
            println!(
                "SAMPLES pid={} order={} batch={} counter_ticks={} clock_ns={}",
                process::id(),
                order,
                batch,
                comma_separated(&result.ticks),
                comma_separated(&result.nanoseconds)
            );
        }
        let end_aux = counter.read().aux;
        println!(
            "END pid={} checksum={state:016x} end_cpu={} end_aux={} rejected_counter={} rejected_clock={}",
            process::id(),
            current_cpu()?,
            display_aux(end_aux),
            total_rejected_counter,
            total_rejected_clock
        );
        Ok(())
    }

    pub(super) fn main(args: &[String]) -> Result<(), String> {
        match args {
            [mode] if mode == "--counter-smoke-child" => smoke_child(),
            [mode] if mode == "--probe" => probe(DEFAULT_PROBE_READS),
            [mode, reads] if mode == "--probe" => probe(super::parse_positive(reads, "reads")?),
            [order] if order == "raw-first" || order == "clock-first" => {
                run(order, DEFAULT_SAMPLES)
            }
            [order, samples] if order == "raw-first" || order == "clock-first" => {
                run(order, super::parse_positive(samples, "samples")?)
            }
            _ => Err(
                "usage: cycle_probe --verify | --probe [reads] | <raw-first|clock-first> [samples]"
                    .to_owned(),
            ),
        }
    }
}

fn main() {
    let args = env::args()
        .skip(1)
        .filter(|argument| argument != "--bench")
        .collect::<Vec<_>>();
    if args.as_slice() == ["--verify"] {
        verify();
        return;
    }

    #[cfg(target_os = "linux")]
    let result = linux::main(&args);
    #[cfg(not(target_os = "linux"))]
    let result: Result<(), String> = Err(
        "the counter and CLOCK_MONOTONIC_RAW experiment requires Linux; --verify is portable"
            .to_owned(),
    );

    if let Err(error) = result {
        eprintln!("{error}");
        process::exit(2);
    }
}
