//! Focused smoke benchmark for the visible and opaque helper forms.
//!
//! Its fixed-order, single-process timings are smoke values that require an
//! external baseline. They do not support comparative performance claims
//! across the three forms.

use compiler_optimization_boundaries::{imported_inline_mix, topic16_opaque_mix};
use std::hint::black_box;
use std::time::Instant;

const ELEMENTS: usize = 1 << 20;
const ROUNDS: u32 = 16;

#[inline(always)]
fn local_mix(x: u32, salt: u32) -> u32 {
    let y = x ^ salt;
    y.rotate_left(5).wrapping_add(y ^ 0x9e37_79b9)
}

fn reduce<F>(words: &[u32], salt: u32, mix: F) -> u32
where
    F: Fn(u32, u32) -> u32 + Copy,
{
    words
        .iter()
        .fold(0u32, |sum, &word| sum.wrapping_add(mix(word, salt)))
}

fn measure<F>(label: &str, words: &[u32], mix: F) -> (u128, u32)
where
    F: Fn(u32, u32) -> u32 + Copy,
{
    let start = Instant::now();
    let mut checksum = 0u32;
    for round in 0..ROUNDS {
        checksum = checksum.wrapping_add(reduce(
            black_box(words),
            round.wrapping_mul(0x9e37_79b9),
            mix,
        ));
    }
    let elapsed = start.elapsed().as_nanos();
    println!("{label}_ns={elapsed} checksum={}", black_box(checksum));
    (elapsed, checksum)
}

fn main() {
    let words: Vec<u32> = (0..ELEMENTS as u32)
        .map(|word| word.wrapping_mul(2_654_435_761))
        .collect();

    let (_, local) = measure("local", &words, local_mix);
    let (_, imported) = measure("imported", &words, imported_inline_mix);
    let (_, opaque) = measure("opaque", &words, |word, salt| {
        topic16_opaque_mix(word, salt)
    });
    assert_eq!(local, imported);
    assert_eq!(local, opaque);
}
