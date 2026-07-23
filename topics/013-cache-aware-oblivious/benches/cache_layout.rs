//! Runs one transpose kernel and emits one tab-separated experiment record.
//!
//! The caller selects exactly one layout and kernel with `RUN_ID`, `BLOCK`,
//! `POSITION`, and `MODE`. `setup_ns` covers allocation, initialization,
//! virtual-address capture, and the 128 MiB conditioning pass. `kernel_ns`
//! covers the timed dispatch and transpose invocation; `verify_ns` covers
//! post-kernel correctness checks.
//!
//! Verification compares every active element, checks the padding sentinel when
//! present, and compares source and destination checksums. This binary neither
//! pins itself nor iterates the schedule; any process isolation, affinity, or
//! schedule iteration must come from the caller. It validates the ranges and
//! `RUN_ID`, but the caller must verify that `MODE` is the canonical schedule
//! entry for the supplied `BLOCK` and `POSITION`.

use std::hint::black_box;
use std::process::ExitCode;
use std::time::Instant;

use systems_snackpack_topic_013::{
    RECORDED_BASE_PAGE_BYTES, RECORDED_CACHE_LINE_BYTES, RECORDED_CONDITION_BYTES,
    RECORDED_MATRIX_EDGE, RECORDED_TILE_EDGE, RECURSIVE_LEAF_ELEMENTS, transpose_naive,
    transpose_recursive, transpose_tiled,
};

const EMBEDDED_SOURCE_COMMIT: &str = match option_env!("TOPIC13_SOURCE_COMMIT") {
    Some(commit) => commit,
    None => "unrecorded",
};
const SENTINEL: u64 = u64::MAX;

#[derive(Clone, Copy)]
enum Kernel {
    Naive,
    Tiled,
    Recursive,
}

#[derive(Clone, Copy)]
struct Mode {
    name: &'static str,
    variant: &'static str,
    leading_dimension: usize,
    kernel: Kernel,
}

fn parse_mode(name: &str) -> Option<Mode> {
    let n = RECORDED_MATRIX_EDGE;
    match name {
        "pow2-naive" => Some(Mode {
            name: "pow2-naive",
            variant: "naive",
            leading_dimension: n,
            kernel: Kernel::Naive,
        }),
        "pow2-tiled" => Some(Mode {
            name: "pow2-tiled",
            variant: "tiled",
            leading_dimension: n,
            kernel: Kernel::Tiled,
        }),
        "pow2-recursive" => Some(Mode {
            name: "pow2-recursive",
            variant: "recursive",
            leading_dimension: n,
            kernel: Kernel::Recursive,
        }),
        "padded-naive" => Some(Mode {
            name: "padded-naive",
            variant: "naive",
            leading_dimension: n + 1,
            kernel: Kernel::Naive,
        }),
        "padded-tiled" => Some(Mode {
            name: "padded-tiled",
            variant: "tiled",
            leading_dimension: n + 1,
            kernel: Kernel::Tiled,
        }),
        "padded-recursive" => Some(Mode {
            name: "padded-recursive",
            variant: "recursive",
            leading_dimension: n + 1,
            kernel: Kernel::Recursive,
        }),
        _ => None,
    }
}

#[inline(never)]
fn condition_cache(storage: &mut [u64]) -> u64 {
    // Touch one word per modeled cache line twice. This conditions a footprint
    // but does not establish a specific post-touch cache state.
    let words_per_line = RECORDED_CACHE_LINE_BYTES / size_of::<u64>();
    for index in (0..storage.len()).step_by(words_per_line) {
        storage[index] = (index as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15);
    }
    let mut checksum = 0_u64;
    for index in (0..storage.len()).step_by(words_per_line) {
        checksum = checksum.wrapping_add(black_box(storage[index]));
    }
    checksum
}

fn fail(message: &str) -> ExitCode {
    eprintln!("{message}");
    ExitCode::from(2)
}

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().collect();
    let cargo_bench_suffix =
        arguments.len() == 6 && arguments.last().is_some_and(|value| value == "--bench");
    if arguments.len() != 5 && !cargo_bench_suffix {
        return fail("usage: cache_layout RUN_ID BLOCK POSITION MODE");
    }
    let run_id = &arguments[1];
    let block = match arguments[2].parse::<usize>() {
        Ok(value @ 1..=12) => value,
        _ => return fail("BLOCK must be in 1..=12"),
    };
    let position = match arguments[3].parse::<usize>() {
        Ok(value @ 1..=6) => value,
        _ => return fail("POSITION must be in 1..=6"),
    };
    let expected_run_id = format!("b{block:02}-p{position}");
    if run_id != &expected_run_id {
        return fail("RUN_ID does not match BLOCK and POSITION");
    }
    let mode = match parse_mode(&arguments[4]) {
        Some(mode) => mode,
        None => return fail("MODE is not one of the six recorded modes"),
    };

    let setup_started = Instant::now();
    let n = RECORDED_MATRIX_EDGE;
    let leading_dimension = mode.leading_dimension;
    let element_count = match n.checked_mul(leading_dimension) {
        Some(value) => value,
        None => return fail("matrix allocation length overflowed"),
    };
    let mut source = vec![SENTINEL; element_count];
    let mut expected_checksum = 0_u64;
    for row in 0..n {
        for column in 0..n {
            let value = (row as u64) * 131 + (column as u64) * 17 + 7;
            source[row * leading_dimension + column] = value;
            expected_checksum = expected_checksum.wrapping_add(value);
        }
    }
    let mut destination = vec![SENTINEL; element_count];
    let source_virtual_base = source.as_ptr() as usize;
    let destination_virtual_base = destination.as_ptr() as usize;
    let source_mod64 = source_virtual_base % RECORDED_CACHE_LINE_BYTES;
    let destination_mod64 = destination_virtual_base % RECORDED_CACHE_LINE_BYTES;
    let source_page_offset = source_virtual_base % RECORDED_BASE_PAGE_BYTES;
    let destination_page_offset = destination_virtual_base % RECORDED_BASE_PAGE_BYTES;
    let mut conditioning = vec![0_u64; RECORDED_CONDITION_BYTES / size_of::<u64>()];
    let conditioning_checksum = condition_cache(black_box(&mut conditioning));
    black_box(conditioning_checksum);
    black_box(&conditioning);
    let setup_ns = setup_started.elapsed().as_nanos();

    let kernel_started = Instant::now();
    let result = match mode.kernel {
        Kernel::Naive => transpose_naive(
            black_box(&source),
            black_box(&mut destination),
            n,
            leading_dimension,
        ),
        Kernel::Tiled => transpose_tiled(
            black_box(&source),
            black_box(&mut destination),
            n,
            leading_dimension,
            RECORDED_TILE_EDGE,
        ),
        Kernel::Recursive => transpose_recursive(
            black_box(&source),
            black_box(&mut destination),
            n,
            leading_dimension,
        ),
    };
    let kernel_ns = kernel_started.elapsed().as_nanos();
    if let Err(error) = result {
        return fail(&format!("transpose failed: {error}"));
    }

    let verify_started = Instant::now();
    let mut checksum = 0_u64;
    for row in 0..n {
        for column in 0..n {
            let observed = destination[column * leading_dimension + row];
            let expected = source[row * leading_dimension + column];
            if observed != expected {
                return fail(&format!(
                    "transpose mismatch at source row {row}, column {column}"
                ));
            }
            checksum = checksum.wrapping_add(observed);
        }
    }
    if leading_dimension > n {
        for row in 0..n {
            if destination[row * leading_dimension + n] != SENTINEL {
                return fail("transpose wrote into row padding");
            }
        }
    }
    if checksum != expected_checksum {
        return fail("full verification checksum differs from the source checksum");
    }
    let verify_ns = verify_started.elapsed().as_nanos();

    println!(
        "{run_id}\t{block}\t{position}\t{}\t{}\t{n}\t{leading_dimension}\t{}\t{}\t{}\t{}\t{source_virtual_base}\t{destination_virtual_base}\t{source_mod64}\t{destination_mod64}\t{source_page_offset}\t{destination_page_offset}\t{setup_ns}\t{kernel_ns}\t{verify_ns}\t{checksum}\t{expected_checksum}",
        mode.name,
        mode.variant,
        RECORDED_TILE_EDGE,
        RECURSIVE_LEAF_ELEMENTS,
        RECORDED_CONDITION_BYTES,
        EMBEDDED_SOURCE_COMMIT,
    );
    ExitCode::SUCCESS
}
