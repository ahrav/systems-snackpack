//! Runs the Release/Acquire publication correctness example.

use atomic_lowering::publication_roundtrip;

fn main() {
    let rounds = std::env::args()
        .nth(1)
        .map(|value| value.parse::<u64>().expect("ROUNDS must be an integer"))
        .unwrap_or(100_000);
    println!("published={}", publication_roundtrip(rounds));
}
