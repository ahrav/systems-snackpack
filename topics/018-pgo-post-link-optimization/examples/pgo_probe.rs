//! Standalone indirect-call fixture for instrumentation PGO and code inspection.

use std::env;
use std::hint::black_box;
use std::time::Instant;

type Kernel = fn(u64) -> u64;

#[inline(never)]
fn alpha(mut value: u64) -> u64 {
    value ^= value.rotate_left(17);
    value = value.wrapping_mul(0x9e37_79b9_7f4a_7c15);
    value ^ (value >> 29)
}

#[inline(never)]
fn beta(mut value: u64) -> u64 {
    value ^= value.rotate_right(11);
    value = value.wrapping_mul(0xd6e8_feb8_6659_fd93);
    value ^ (value >> 31)
}

#[inline(never)]
fn dispatch(kernel: Kernel, value: u64) -> u64 {
    black_box(kernel)(black_box(value))
}

fn parse_u64(value: Option<&String>, default: u64, name: &str) -> u64 {
    value
        .map(|text| {
            text.parse::<u64>()
                .unwrap_or_else(|_| panic!("{name} must be an integer"))
        })
        .unwrap_or(default)
}

fn main() {
    let arguments: Vec<String> = env::args().collect();
    let mode = arguments.get(1).map(String::as_str).unwrap_or("alpha");
    let iterations = parse_u64(arguments.get(2), 20_000_000, "iterations");
    let seed = parse_u64(arguments.get(3), 0x1234_5678_9abc_def0, "seed");

    if mode == "noop" {
        println!("mode=noop iterations=0 seed={seed} elapsed_ns=0 checksum={seed:016x}");
        return;
    }

    let kernel: Kernel = match mode {
        "alpha" => alpha,
        "beta" => beta,
        _ => panic!("mode must be alpha, beta, or noop"),
    };

    let mut state = seed;
    let started = Instant::now();
    for index in 0..iterations {
        state = dispatch(kernel, state ^ index);
    }
    println!(
        "mode={mode} iterations={iterations} seed={seed} elapsed_ns={} checksum={state:016x}",
        started.elapsed().as_nanos()
    );
}
