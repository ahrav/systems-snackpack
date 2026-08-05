//! Correctness witness and hot-CAS measurement kernel for Topic 23.
//!
//! The binary's measurement path invokes one kernel from one thread on one
//! caller-owned `AtomicU64`. Each completed iteration performs two successful
//! compare-exchanges and restores index `A`; weak failures can add an unbounded
//! number of attempts. `Relaxed` ordering does not synchronize access to any
//! other memory.
//!
//! The tagged arm advances its 32-bit generation twice per iteration with
//! wrapping arithmetic. The measurement excludes allocation, retirement,
//! reclamation scans, grace periods, destruction, stalled readers, and
//! contention.
//!
//! # Command and platform boundary
//!
//! `aba_lab check` asserts the fixed witness. The optional iteration count in
//! `aba_lab bench <raw|tagged> [iterations]` defaults to 10,000,000. An absent
//! command or benchmark mode, an unknown command or mode, or a noninteger count
//! terminates by panic.
//!
//! The target must support 64-bit atomic load and compare-exchange operations.
//! `#[unsafe(no_mangle)]` fixes each kernel's exported symbol name, and
//! `extern "C"` selects the C calling convention. The parameters remain Rust
//! references; this module specifies no foreign-language lifetime or aliasing
//! contract.

use lock_free_reclamation_aba::{
    A, EMPTY, head_generation, head_index, pack_head, run_aba_witness,
};
use std::hint::black_box;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

/// Measures two successful index-only CAS operations per completed iteration.
///
/// Every value observed by the first retry loop must have a low 32-bit index in
/// `0..2`. With exclusive access, the second CAS restores index `A`, and the
/// return value is the wrapping sum of the post-reset loads. Weak failures or
/// interference can add attempts without a per-call completion bound.
///
/// # Panics
///
/// Panics if the first retry loop observes an index outside `0..2`.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bench_raw_kernel(head: &AtomicU64, next: &[u32; 2], iters: u64) -> u64 {
    let mut checksum = 0_u64;
    for _ in 0..iters {
        let mut old = head.load(Ordering::Relaxed);
        loop {
            let desired = u64::from(next[head_index(old) as usize]);
            match head.compare_exchange_weak(old, desired, Ordering::Relaxed, Ordering::Relaxed) {
                Ok(_) => break,
                Err(observed) => old = observed,
            }
        }

        let mut old = head.load(Ordering::Relaxed);
        loop {
            match head.compare_exchange_weak(
                old,
                u64::from(A),
                Ordering::Relaxed,
                Ordering::Relaxed,
            ) {
                Ok(_) => break,
                Err(observed) => old = observed,
            }
        }
        checksum = checksum.wrapping_add(black_box(head.load(Ordering::Relaxed)));
    }
    checksum
}

/// Measures two successful tagged CAS operations per completed iteration.
///
/// Every value observed by the first retry loop must have a low 32-bit index in
/// `0..2`. With exclusive access, each iteration advances the generation twice
/// modulo `2^32`, restores index `A`, and adds the packed post-reset load to a
/// wrapping checksum. Weak failures or interference can add attempts without a
/// per-call completion bound.
///
/// # Panics
///
/// Panics if the first retry loop observes an index outside `0..2`.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn bench_tagged_kernel(head: &AtomicU64, next: &[u32; 2], iters: u64) -> u64 {
    let mut checksum = 0_u64;
    for _ in 0..iters {
        let mut old = head.load(Ordering::Relaxed);
        loop {
            let desired = pack_head(
                head_generation(old).wrapping_add(1),
                next[head_index(old) as usize],
            );
            match head.compare_exchange_weak(old, desired, Ordering::Relaxed, Ordering::Relaxed) {
                Ok(_) => break,
                Err(observed) => old = observed,
            }
        }

        let mut old = head.load(Ordering::Relaxed);
        loop {
            let desired = pack_head(head_generation(old).wrapping_add(1), A);
            match head.compare_exchange_weak(old, desired, Ordering::Relaxed, Ordering::Relaxed) {
                Ok(_) => break,
                Err(observed) => old = observed,
            }
        }
        checksum = checksum.wrapping_add(black_box(head.load(Ordering::Relaxed)));
    }
    checksum
}

// Warms and measures one kernel; panics if `mode` is neither `raw` nor `tagged`.
fn bench(mode: &str, iters: u64) {
    let next = [EMPTY, EMPTY];
    let warmup_iters = (iters / 100).max(10_000);

    let (elapsed, checksum, final_word) = match mode {
        "raw" => {
            let warmup = AtomicU64::new(u64::from(A));
            black_box(bench_raw_kernel(&warmup, &next, warmup_iters));
            let head = AtomicU64::new(u64::from(A));
            let start = Instant::now();
            let checksum = bench_raw_kernel(&head, &next, iters);
            (start.elapsed(), checksum, head.load(Ordering::Relaxed))
        }
        "tagged" => {
            let warmup = AtomicU64::new(pack_head(0, A));
            black_box(bench_tagged_kernel(&warmup, &next, warmup_iters));
            let head = AtomicU64::new(pack_head(0, A));
            let start = Instant::now();
            let checksum = bench_tagged_kernel(&head, &next, iters);
            (start.elapsed(), checksum, head.load(Ordering::Relaxed))
        }
        _ => panic!("mode must be raw or tagged"),
    };

    println!(
        "bench,mode={mode},iters={iters},elapsed_ns={},ns_per_iter={:.6},checksum={checksum},final_word={final_word}",
        elapsed.as_nanos(),
        elapsed.as_secs_f64() * 1e9 / iters as f64,
    );
}

// Emits the fixture observations and panics if either arm violates its contract.
fn check() {
    let result = run_aba_witness();
    println!(
        "check,raw_stale_cas={},raw_reintroduced_b={},tagged_stale_cas={},tagged_generation={},tagged_index={}",
        result.raw_stale_cas,
        result.raw_reintroduced_b,
        result.tagged_stale_cas,
        result.tagged_generation,
        result.tagged_index,
    );
    assert!(result.raw_stale_cas && result.raw_reintroduced_b);
    assert!(!result.tagged_stale_cas);
    assert_eq!((result.tagged_generation, result.tagged_index), (3, A));
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("check") => check(),
        Some("bench") => {
            let mode = args.get(2).expect("missing mode");
            let iters = args
                .get(3)
                .map(String::as_str)
                .unwrap_or("10000000")
                .parse::<u64>()
                .expect("iterations must be an integer");
            assert!(iters > 0, "iterations must be positive");
            bench(mode, iters);
        }
        _ => panic!("usage: aba_lab check | aba_lab bench <raw|tagged> [iterations]"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn raw_kernel_matches_its_contract() {
        let next = [EMPTY, EMPTY];
        for iters in 1..=8_u64 {
            let head = AtomicU64::new(u64::from(A));
            let checksum = bench_raw_kernel(&head, &next, iters);
            // Each iteration restores index A and adds the post-reset load.
            assert_eq!(checksum, iters);
            assert_eq!(head.load(Ordering::Relaxed), u64::from(A));
        }
    }

    #[test]
    fn tagged_kernel_matches_its_contract() {
        let next = [EMPTY, EMPTY];
        for iters in 1..=8_u64 {
            let head = AtomicU64::new(pack_head(0, A));
            let checksum = bench_tagged_kernel(&head, &next, iters);
            let expected = (1..=iters)
                .map(|i| pack_head((2 * i) as u32, A))
                .fold(0_u64, u64::wrapping_add);
            assert_eq!(checksum, expected);
            assert_eq!(
                head.load(Ordering::Relaxed),
                pack_head((2 * iters) as u32, A)
            );
        }
    }
}
