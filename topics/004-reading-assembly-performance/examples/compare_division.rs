//! Compares constant and runtime division chains for divisor seven.

use std::num::NonZeroU64;

use systems_snackpack_topic_004::{divide_constant_chain, divide_runtime_chain};

const DEFAULT_ITERATIONS: u64 = 1_000_000;
const SEED: u64 = 0x1234_5678_9abc_def0;

fn main() {
    let iterations = std::env::args()
        .nth(1)
        .map(|value| {
            value
                .parse::<u64>()
                .expect("iteration count must be an unsigned 64-bit integer")
        })
        .unwrap_or(DEFAULT_ITERATIONS);
    let divisor = NonZeroU64::new(7).expect("seven is nonzero");

    let constant = divide_constant_chain(SEED, iterations);
    let runtime = divide_runtime_chain(SEED, divisor, iterations);

    assert_eq!(constant, runtime);
    println!("iterations={iterations} result={constant}");
}
