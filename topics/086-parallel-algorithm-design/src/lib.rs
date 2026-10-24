//! Exclusive scans over addition modulo 2^64.
//!
//! The blocked algorithms preserve input order and assign disjoint output slices.
//! Each thread scope joins before summaries or output are consumed.
//! Run `cargo run -p parallel-algorithm-design --release -- demo`.
use std::thread;

/// Scan into an equally sized output, returning the total modulo 2^64.
///
/// # Panics
/// Panics if slice lengths differ.
pub fn serial(input: &[u64], output: &mut [u64]) -> u64 {
    assert_eq!(input.len(), output.len());
    let mut sum = 0u64;
    for (&x, y) in input.iter().zip(output) {
        *y = sum;
        sum = sum.wrapping_add(x);
    }
    sum
}

fn width(input: &[u64], output: &[u64], workers: usize) -> usize {
    assert_eq!(input.len(), output.len());
    assert!(workers > 0);
    input.len().div_ceil(workers).max(1)
}

fn offsets(totals: &mut [u64]) -> u64 {
    let mut base = 0u64;
    for total in totals {
        let next = base.wrapping_add(*total);
        *total = base;
        base = next;
    }
    base
}

/// Scan chunks locally, then add the scanned chunk totals to each output.
///
/// Creates at most `workers` threads in each of two joined phases. Scratch
/// storage is O(min(workers, input.len())). Empty input creates no threads.
///
/// # Panics
/// Panics if `workers` is zero, lengths differ, or a worker cannot be spawned.
pub fn local_add(input: &[u64], output: &mut [u64], workers: usize) -> u64 {
    let width = width(input, output, workers);
    let mut totals = vec![0u64; input.len().div_ceil(width)];
    thread::scope(|s| {
        for ((src, dst), total) in input
            .chunks(width)
            .zip(output.chunks_mut(width))
            .zip(totals.iter_mut())
        {
            s.spawn(move || *total = serial(src, dst));
        }
    });
    let total = offsets(&mut totals);
    thread::scope(|s| {
        for (dst, base) in output.chunks_mut(width).zip(totals) {
            s.spawn(move || {
                for y in dst {
                    *y = y.wrapping_add(base);
                }
            });
        }
    });
    total
}

/// Reduce chunks, then rescan input with the scanned totals as initial values.
///
/// Compared with [`local_add`], this reads input twice and writes output once.
/// Threads and scratch allocations are included in each call.
///
/// # Panics
/// Panics if `workers` is zero, lengths differ, or a worker cannot be spawned.
pub fn totals_rescan(input: &[u64], output: &mut [u64], workers: usize) -> u64 {
    let width = width(input, output, workers);
    let mut totals = vec![0u64; input.len().div_ceil(width)];
    thread::scope(|s| {
        for (src, total) in input.chunks(width).zip(totals.iter_mut()) {
            s.spawn(move || {
                *total = src.iter().copied().fold(0u64, u64::wrapping_add);
            });
        }
    });
    let total = offsets(&mut totals);
    thread::scope(|s| {
        for ((src, dst), mut base) in input
            .chunks(width)
            .zip(output.chunks_mut(width))
            .zip(totals)
        {
            s.spawn(move || {
                for (&x, y) in src.iter().zip(dst) {
                    *y = base;
                    base = base.wrapping_add(x);
                }
            });
        }
    });
    total
}

#[cfg(test)]
mod tests {
    use super::*;

    fn check(input: &[u64], workers: usize) {
        // A wider integer and independent prefix slices define the oracle.
        let expected: Vec<u64> = (0..input.len())
            .map(|i| input[..i].iter().map(|&x| u128::from(x)).sum::<u128>() as u64)
            .collect();
        let total = input.iter().map(|&x| u128::from(x)).sum::<u128>() as u64;
        for variant in [local_add, totals_rescan] {
            let mut out = vec![u64::MAX; input.len()];
            assert_eq!(variant(input, &mut out, workers), total);
            assert_eq!(out, expected);
        }
        let mut out = vec![u64::MAX; input.len()];
        assert_eq!(serial(input, &mut out), total);
        assert_eq!(out, expected);
    }

    #[test]
    fn running_example() {
        check(&[3, 1, 4, 1, 5, 9, 2, 6], 4);
    }

    #[test]
    fn empty_uneven_and_more_workers_than_values() {
        for n in [0, 1, 2, 3, 7, 8, 9, 31, 65] {
            let input: Vec<_> = (1..=n).collect();
            for workers in [1, 3, 8, 16] {
                check(&input, workers);
            }
        }
    }

    #[test]
    fn wraps_at_chunk_boundaries() {
        for workers in [1, 2, 3, 8] {
            check(&[u64::MAX, 1, 0, u64::MAX, 2, 9, u64::MAX], workers);
        }
    }

    #[test]
    #[should_panic]
    fn rejects_zero_workers() {
        local_add(&[], &mut [], 0);
    }

    #[test]
    #[should_panic]
    fn rejects_mismatched_output() {
        totals_rescan(&[1], &mut [], 1);
    }
}
