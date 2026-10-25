//! Print derived address counts for one full warp.
use gpu_execution_mechanics::{bank_depth, sectors};
fn main() {
    for (name, stride, offset) in [
        ("contiguous", 4, 0),
        ("shifted", 4, 4),
        ("strided", 4096, 0),
    ] {
        let addresses: Vec<_> = (0..32).map(|t| offset + stride * t).collect();
        println!("{name}: {} sectors", sectors(&addresses, 4));
    }
    for pitch in [32, 33] {
        let words: Vec<_> = (0..32).map(|t| pitch * t).collect();
        println!("pitch {pitch}: bank depth {}", bank_depth(&words));
    }
    println!("GPU runtime and throughput require a CUDA device.");
}
