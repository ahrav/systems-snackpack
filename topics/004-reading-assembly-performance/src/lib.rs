//! Loop-carried kernels for comparing constant and runtime unsigned division.
//!
//! Both kernels apply the same wrapping multiply-add before each division. Each
//! quotient feeds the next iteration, which creates a dependency across the
//! complete loop.
//!
//! Each measured interval spans one non-inlined kernel call. It includes the
//! call and return plus the loop's multiply-add, division or replacement
//! sequence, and control work. Argument and result `black_box` calls, warmup,
//! validation, sorting, process startup, and output occur outside the two clock
//! reads.
//!
//! Run the equality check with `cargo run -p systems-snackpack-topic-004
//! --example compare_division`.

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

/// Executes the dependency chain with `7` visible as a compile-time constant.
#[inline(never)]
pub fn divide_constant_chain(seed: u64, iterations: u64) -> u64 {
    let mut state = seed;
    for _ in 0..iterations {
        let numerator = state
            .wrapping_mul(0xd134_2543_de82_ef95)
            .wrapping_add(0x9e37_79b9_7f4a_7c15);
        state = numerator / 7;
    }
    state
}

/// Executes the dependency chain with one caller-supplied divisor.
#[inline(never)]
pub fn divide_runtime_chain(seed: u64, divisor: std::num::NonZeroU64, iterations: u64) -> u64 {
    let mut state = seed;
    let divisor = divisor.get();
    for _ in 0..iterations {
        let numerator = state
            .wrapping_mul(0xd134_2543_de82_ef95)
            .wrapping_add(0x9e37_79b9_7f4a_7c15);
        state = numerator / divisor;
    }
    state
}

#[cfg(test)]
mod tests {
    use std::num::NonZeroU64;

    use super::{divide_constant_chain, divide_runtime_chain};

    #[test]
    fn constant_and_runtime_division_match_for_seven() {
        let divisor = NonZeroU64::new(7).expect("seven is nonzero");
        let seeds = [0, 1, u64::MAX, 0x1234_5678_9abc_def0];
        let iteration_counts = [0, 1, 2, 31, 1_000];

        for seed in seeds {
            for iterations in iteration_counts {
                assert_eq!(
                    divide_constant_chain(seed, iterations),
                    divide_runtime_chain(seed, divisor, iterations),
                    "seed={seed:#018x} iterations={iterations}",
                );
            }
        }
    }

    #[test]
    fn zero_iterations_return_the_seed() {
        let seed = 0x1234_5678_9abc_def0;
        let divisor = NonZeroU64::new(7).expect("seven is nonzero");

        assert_eq!(divide_constant_chain(seed, 0), seed);
        assert_eq!(divide_runtime_chain(seed, divisor, 0), seed);
    }
}
