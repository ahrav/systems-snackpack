//! Fresh-process CLI for translation reach and permission-change measurements.
//!
//! The reach workload times only the dependent page-ring chase after separate
//! setup and warmup phases. The shootdown workload times `mprotect` pairs while
//! scoped reader threads retain read access to the target page. A successful
//! workload invocation emits one `RESULT` record; `--verify` emits `VERIFY`
//! records instead. `run_to_pre_emit_ns` starts inside `run` and ends before
//! result formatting, output, mapping teardown, and process exit.

use std::{
    env,
    hint::black_box,
    process,
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
    thread,
    time::Instant,
};

use systems_snackpack_topic_008::{
    AnonymousRegion, MappingError, MappingMode, PMD_PAGE_SIZE, pin_current_thread,
};

fn argument<'a>(arguments: &'a [String], name: &str) -> Option<&'a str> {
    arguments
        .windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].as_str())
}

fn parse_u64(arguments: &[String], name: &str, default: u64) -> u64 {
    argument(arguments, name)
        .map(|value| {
            value
                .parse()
                .unwrap_or_else(|_| panic!("invalid {name}: {value}"))
        })
        .unwrap_or(default)
}

fn mapping_mode(arguments: &[String]) -> MappingMode {
    match argument(arguments, "--variant").expect("missing --variant") {
        "base" => MappingMode::BasePages,
        "thp" => MappingMode::TransparentHugePages,
        other => panic!("unknown variant {other}; use base or thp"),
    }
}

fn verify() -> Result<(), MappingError> {
    for mode in [MappingMode::BasePages, MappingMode::TransparentHugePages] {
        let mut region = AnonymousRegion::new(2 * PMD_PAGE_SIZE, mode)?;
        region.build_random_page_ring(0x746c_622d_7269_6e67)?;
        let pages = region.page_count();
        let final_page = region.chase_pages(0, (pages * 3) as u64)?;
        assert_eq!(final_page, 0);
        let evidence = region.smaps_evidence()?;
        println!(
            "VERIFY variant={} status=ok pages={} anon_huge_kib={} kernel_page_kib={} mmu_page_kib={} vm_flags={}",
            mode.name(),
            pages,
            evidence.anon_huge_pages_kib,
            evidence.kernel_page_kib,
            evidence.mmu_page_kib,
            evidence.vm_flags.join(",")
        );
    }
    Ok(())
}

fn reach(arguments: &[String], run_start: Instant) -> Result<(), MappingError> {
    let setup_start = Instant::now();
    let mode = mapping_mode(arguments);
    let mib = parse_u64(arguments, "--mib", 256) as usize;
    let passes = parse_u64(arguments, "--passes", 64);
    let pair = parse_u64(arguments, "--pair", 0);
    let order = parse_u64(arguments, "--order", 0);
    let length = mib.checked_mul(1024 * 1024).expect("--mib overflows usize");
    assert!(passes > 0, "--passes must be nonzero");
    let mut region = AnonymousRegion::new(length, mode)?;
    region.build_random_page_ring(0x746c_622d_7269_6e67)?;
    let evidence_before = region.smaps_evidence()?;
    let pages = region.page_count();
    let setup_ns = setup_start.elapsed().as_nanos();

    let warmup_start = Instant::now();
    let warmup_page = black_box(region.chase_pages(0, pages as u64)?);
    let warmup_ns = warmup_start.elapsed().as_nanos();
    assert_eq!(warmup_page, 0);

    let accesses = (pages as u64)
        .checked_mul(passes)
        .expect("access count overflow");
    let timed_start = Instant::now();
    let final_page = black_box(region.chase_pages(0, accesses)?);
    let timed_ns = timed_start.elapsed().as_nanos();
    assert_eq!(final_page, 0);
    let evidence_after = region.smaps_evidence()?;

    println!(
        "RESULT pid={} workload=reach variant={} mib={} pages={} passes={} accesses={} pair={} order={} setup_ns={} warmup_ns={} timed_ns={} run_to_pre_emit_ns={} ns_per_access={:.9} anon_huge_kib_before={} anon_huge_kib_after={} kernel_page_kib={} mmu_page_kib={} vm_flags={}",
        process::id(),
        mode.name(),
        mib,
        pages,
        passes,
        accesses,
        pair,
        order,
        setup_ns,
        warmup_ns,
        timed_ns,
        run_start.elapsed().as_nanos(),
        timed_ns as f64 / accesses as f64,
        evidence_before.anon_huge_pages_kib,
        evidence_after.anon_huge_pages_kib,
        evidence_after.kernel_page_kib,
        evidence_after.mmu_page_kib,
        evidence_after.vm_flags.join(",")
    );
    Ok(())
}

fn permission_pairs(region: &mut AnonymousRegion, pairs: u64) -> Result<(), MappingError> {
    for _ in 0..pairs {
        region.set_first_page_writable(false)?;
        region.set_first_page_writable(true)?;
    }
    Ok(())
}

struct StopReaders(Arc<AtomicBool>);

impl Drop for StopReaders {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
    }
}

fn shootdown(arguments: &[String], run_start: Instant) -> Result<(), MappingError> {
    let setup_start = Instant::now();
    let readers = parse_u64(arguments, "--readers", 1) as usize;
    let pairs = parse_u64(arguments, "--mprotect-pairs", 20_000);
    let first_cpu = parse_u64(arguments, "--first-cpu", 0) as usize;
    let pair = parse_u64(arguments, "--pair", 0);
    let order = parse_u64(arguments, "--order", 0);
    assert!(readers > 0, "--readers must be nonzero");
    assert!(pairs > 0, "--mprotect-pairs must be nonzero");

    pin_current_thread(first_cpu)?;
    let mut region = AnonymousRegion::new(PMD_PAGE_SIZE, MappingMode::BasePages)?;
    let address = region.start_address();
    let stop = Arc::new(AtomicBool::new(false));
    let start = Arc::new(AtomicBool::new(false));
    let timed_phase = Arc::new(AtomicBool::new(false));
    let ready = Arc::new(AtomicUsize::new(0));
    let active = Arc::new(AtomicUsize::new(0));
    let failed = Arc::new(AtomicUsize::new(0));
    let warmup_pairs = pairs.min(100);
    let (setup_ns, warmup_ns, timed_ns, reader_loads, reader_checksum) = thread::scope(
        |scope| -> Result<(u128, u128, u128, u64, u64), MappingError> {
            // Every exit path signals the readers. `thread::scope` then joins
            // them before the borrowed `region` can be unmapped.
            let _stop_on_exit = StopReaders(Arc::clone(&stop));
            let mut handles = Vec::with_capacity(readers);
            for index in 0..readers {
                let stop = Arc::clone(&stop);
                let start = Arc::clone(&start);
                let timed_phase = Arc::clone(&timed_phase);
                let ready = Arc::clone(&ready);
                let active = Arc::clone(&active);
                let failed = Arc::clone(&failed);
                handles.push(
                    scope.spawn(move || -> Result<(u64, u64, u64), MappingError> {
                        let affinity = pin_current_thread(first_cpu + index + 1);
                        ready.fetch_add(1, Ordering::Release);
                        while !start.load(Ordering::Acquire) && !stop.load(Ordering::Acquire) {
                            thread::yield_now();
                        }
                        if let Err(error) = affinity {
                            failed.fetch_add(1, Ordering::Release);
                            return Err(error);
                        }

                        let mut loads = 0_u64;
                        let mut timed_loads = 0_u64;
                        let mut checksum = 0_u64;
                        // SAFETY: The scoped reader exits before `region` is
                        // unmapped, and both protection states retain reads.
                        let first = unsafe { (address as *const u8).read_volatile() };
                        checksum = checksum.wrapping_add(u64::from(first));
                        loads += 1;
                        active.fetch_add(1, Ordering::Release);
                        while !stop.load(Ordering::Acquire) {
                            // SAFETY: The scoped reader exits before `region` is
                            // unmapped, and both protection states retain reads.
                            let value = unsafe { (address as *const u8).read_volatile() };
                            checksum = checksum.wrapping_add(u64::from(value));
                            loads = loads.wrapping_add(1);
                            if timed_phase.load(Ordering::Acquire) {
                                timed_loads = timed_loads.wrapping_add(1);
                            }
                        }
                        Ok((loads, timed_loads, checksum))
                    }),
                );
            }

            while ready.load(Ordering::Acquire) != readers {
                thread::yield_now();
            }
            start.store(true, Ordering::Release);
            while active.load(Ordering::Acquire) + failed.load(Ordering::Acquire) != readers {
                thread::yield_now();
            }
            let setup_ns = setup_start.elapsed().as_nanos();

            let mut operation_error = None;
            let warmup_start = Instant::now();
            if failed.load(Ordering::Acquire) == 0
                && let Err(error) = permission_pairs(&mut region, warmup_pairs)
            {
                operation_error = Some(error);
            }
            let warmup_ns = warmup_start.elapsed().as_nanos();

            let timed_start = Instant::now();
            if failed.load(Ordering::Acquire) == 0 && operation_error.is_none() {
                timed_phase.store(true, Ordering::Release);
                if let Err(error) = permission_pairs(&mut region, pairs) {
                    operation_error = Some(error);
                }
                timed_phase.store(false, Ordering::Release);
            }
            let timed_ns = timed_start.elapsed().as_nanos();
            stop.store(true, Ordering::Release);

            let mut reader_error = None;
            let mut reader_panicked = false;
            let mut inactive_readers = 0_usize;
            let mut reader_loads = 0_u64;
            let mut reader_checksum = 0_u64;
            for handle in handles {
                match handle.join() {
                    Ok(Ok((loads, timed_loads, checksum))) => {
                        if loads == 0
                            || (operation_error.is_none()
                                && failed.load(Ordering::Acquire) == 0
                                && timed_loads == 0)
                        {
                            inactive_readers += 1;
                        }
                        reader_loads = reader_loads.wrapping_add(loads);
                        reader_checksum = reader_checksum.wrapping_add(checksum);
                    }
                    Ok(Err(error)) => {
                        if reader_error.is_none() {
                            reader_error = Some(error);
                        }
                    }
                    Err(_) => reader_panicked = true,
                }
            }
            assert!(!reader_panicked, "reader thread panicked");
            assert_eq!(
                inactive_readers, 0,
                "every reader must execute during the timed phase"
            );
            if let Some(error) = reader_error.or(operation_error) {
                return Err(error);
            }
            Ok((setup_ns, warmup_ns, timed_ns, reader_loads, reader_checksum))
        },
    )?;

    println!(
        "RESULT pid={} workload=shootdown readers={} mprotect_pairs={} first_cpu={} pair={} order={} setup_ns={} warmup_pairs={} warmup_ns={} timed_ns={} run_to_pre_emit_ns={} ns_per_pair={:.9} reader_loads={} reader_checksum={}",
        process::id(),
        readers,
        pairs,
        first_cpu,
        pair,
        order,
        setup_ns,
        warmup_pairs,
        warmup_ns,
        timed_ns,
        run_start.elapsed().as_nanos(),
        timed_ns as f64 / pairs as f64,
        reader_loads,
        reader_checksum
    );
    Ok(())
}

fn run() -> Result<(), MappingError> {
    let run_start = Instant::now();
    let arguments = env::args().collect::<Vec<_>>();
    if arguments.iter().any(|argument| argument == "--verify") {
        return verify();
    }
    match argument(&arguments, "--workload").expect("missing --workload") {
        "reach" => reach(&arguments, run_start),
        "shootdown" => shootdown(&arguments, run_start),
        other => panic!("unknown workload {other}; use reach or shootdown"),
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("address-translation benchmark failed: {error}");
        process::exit(1);
    }
}
