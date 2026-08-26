//! Command-line entry point for the Topic 47 Linux contention experiment.
//!
//! The program emits one `atomics-contention.v1` JSON object only after exact
//! affinity, arithmetic, and final-count checks pass. The optional
//! `BENCH_LABEL` environment variable sets its `label`; the default is
//! `primary`. Run each observation in a fresh process:
//!
//! ```text
//! cargo run --release --package atomics-under-contention \
//!   --example atomic_contention -- shared 4 10000000 200000 64 8 0,2,4,6
//! ```
//!
//! CPU numbers above are examples, not topology advice. Select them from the
//! target's allowed CPU set and verify that workers use distinct physical cores
//! in the intended package and non-uniform memory access (NUMA) node.
//!
//! Argument, parse, configuration, platform, affinity, and count-check errors
//! produce no standard output, write one message to standard error, and exit
//! with status 2.

use atomics_under_contention::{
    BenchmarkConfig, BenchmarkResult, Mode, STRIPE_ALIGNMENT, run_benchmark,
};
use std::env;
use std::fmt::Write as _;
use std::process;

fn fail(message: impl std::fmt::Display) -> ! {
    eprintln!("{message}");
    process::exit(2);
}

fn parse_u64(text: &str, name: &str) -> u64 {
    text.parse()
        .unwrap_or_else(|_| fail(format_args!("invalid {name}: {text:?}")))
}

fn parse_usize(text: &str, name: &str) -> usize {
    text.parse()
        .unwrap_or_else(|_| fail(format_args!("invalid {name}: {text:?}")))
}

fn parse_worker_cpus(text: &str) -> Vec<usize> {
    text.split(',')
        .map(|cpu| parse_usize(cpu, "worker CPU"))
        .collect()
}

fn json_string(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len() + 2);
    escaped.push('"');
    for character in value.chars() {
        match character {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\u{08}' => escaped.push_str("\\b"),
            '\u{0c}' => escaped.push_str("\\f"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            character if character <= '\u{1f}' => {
                write!(&mut escaped, "\\u{:04x}", character as u32)
                    .expect("writing to String cannot fail");
            }
            character => escaped.push(character),
        }
    }
    escaped.push('"');
    escaped
}

fn json_array(values: &[usize]) -> String {
    let mut output = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index != 0 {
            output.push(',');
        }
        write!(&mut output, "{value}").expect("writing to String cannot fail");
    }
    output.push(']');
    output
}

fn result_json(label: &str, result: &BenchmarkResult) -> String {
    format!(
        concat!(
            "{{",
            "\"schema\":\"atomics-contention.v1\",",
            "\"label\":{},",
            "\"mode\":\"{}\",",
            "\"threads\":{},",
            "\"iterations_per_thread\":{},",
            "\"warmup_iterations_per_thread\":{},",
            "\"batch_size\":{},",
            "\"logical_ops\":{},",
            "\"rmw_attempts\":{},",
            "\"cas_retries\":{},",
            "\"final_count\":{},",
            "\"correct\":true,",
            "\"affinity_ok\":true,",
            "\"startup_ns\":{},",
            "\"warmup_ns\":{},",
            "\"steady_ns\":{},",
            "\"teardown_ns\":{},",
            "\"total_ns\":{},",
            "\"coordinator_cpu\":{},",
            "\"worker_cpus\":{},",
            "\"worker_start_cpus\":{},",
            "\"worker_end_cpus\":{},",
            "\"stripe_alignment\":{}",
            "}}"
        ),
        json_string(label),
        result.mode,
        result.threads,
        result.iterations_per_thread,
        result.warmup_iterations_per_thread,
        result.batch_size,
        result.logical_operations,
        result.rmw_attempts,
        result.cas_retries,
        result.final_count,
        result.startup_ns,
        result.warmup_ns,
        result.steady_ns,
        result.teardown_ns,
        result.total_ns,
        result.coordinator_cpu,
        json_array(&result.worker_cpus),
        json_array(&result.worker_start_cpus),
        json_array(&result.worker_end_cpus),
        STRIPE_ALIGNMENT,
    )
}

fn main() {
    let arguments: Vec<String> = env::args().collect();
    if arguments.len() != 8 {
        fail(format_args!(
            "usage: {} <shared|cas|striped|batched> <threads> \
             <iterations_per_thread> <warmup_iterations_per_thread> \
             <batch_size> <coordinator_cpu> <worker_cpu_csv>",
            arguments
                .first()
                .map(String::as_str)
                .unwrap_or("atomic_contention")
        ));
    }

    let mode: Mode = arguments[1].parse().unwrap_or_else(|error| fail(error));
    let config = BenchmarkConfig {
        mode,
        threads: parse_usize(&arguments[2], "thread count"),
        iterations_per_thread: parse_u64(&arguments[3], "iteration count"),
        warmup_iterations_per_thread: parse_u64(&arguments[4], "warmup iteration count"),
        batch_size: parse_u64(&arguments[5], "batch size"),
        coordinator_cpu: parse_usize(&arguments[6], "coordinator CPU"),
        worker_cpus: parse_worker_cpus(&arguments[7]),
    };
    let result = run_benchmark(&config).unwrap_or_else(|error| fail(error));
    let label = env::var("BENCH_LABEL").unwrap_or_else(|_| "primary".to_string());
    println!("{}", result_json(&label, &result));
}
