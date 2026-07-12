//! Runs the three byte-count implementations on one short input.

use systems_snackpack_topic_001::{count_eq_neon, count_eq_scalar, count_eq_swar_prefilter};

fn main() {
    let input = b"bananas are not a benchmark";
    let needle = b'a';

    println!("scalar: {}", count_eq_scalar(input, needle));
    println!("swar:   {}", count_eq_swar_prefilter(input, needle));
    println!("neon:   {}", count_eq_neon(input, needle));
}
