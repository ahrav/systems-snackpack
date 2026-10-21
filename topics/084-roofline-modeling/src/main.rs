//! Same affine transform, three memory schedules. No dependencies.
use std::{hint::black_box, time::Instant};

#[inline(never)]
fn first(x: &[f64], t: &mut [f64]) {
    assert_eq!(x.len(), t.len());
    for (x, t) in x.iter().zip(t) {
        *t = 3.0 * *x + 1.0;
    }
}
#[inline(never)]
fn second(t: &[f64], y: &mut [f64]) {
    assert_eq!(t.len(), y.len());
    for (t, y) in t.iter().zip(y) {
        *y = *t * 2.0;
    }
}
#[inline(never)]
fn fused(x: &[f64], y: &mut [f64]) {
    assert_eq!(x.len(), y.len());
    for (x, y) in x.iter().zip(y) {
        *y = (3.0 * *x + 1.0) * 2.0;
    }
}
fn transform(mode: &str, x: &[f64], y: &mut [f64], scratch: &mut [f64]) {
    assert_eq!(x.len(), y.len());
    match mode {
        "fused" => fused(x, y),
        "split" => {
            first(x, scratch);
            second(scratch, y);
        }
        "blocked" => {
            assert!(!scratch.is_empty());
            for (a, b) in x.chunks(scratch.len()).zip(y.chunks_mut(scratch.len())) {
                let t = &mut scratch[..a.len()];
                first(a, t);
                second(t, b);
            }
        }
        _ => panic!("mode must be split, blocked, or fused"),
    }
}
fn input(i: usize) -> f64 {
    ((i % 1024) as i64 - 512) as f64 / 16.0
}
// Independent integer derivation: x=k/16 => (3*x+1)*2=(3*k+16)/8.
fn oracle(i: usize) -> f64 {
    (3 * ((i % 1024) as i64 - 512) + 16) as f64 / 8.0
}
fn scratch_len(mode: &str, n: usize) -> usize {
    match mode {
        "split" => n,
        "blocked" => 1024,
        "fused" => 0,
        _ => panic!("bad mode"),
    }
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    assert!(
        a.len() == 4 || a.len() == 5,
        "usage: demo MODE ELEMENTS PASSES [dump]"
    );
    let mode = &a[1];
    let n: usize = a[2].parse().unwrap();
    let passes: usize = a[3].parse().unwrap();
    assert!(n > 0 && passes > 0);
    let x: Vec<f64> = (0..n).map(input).collect();
    let mut y = vec![0.0; n];
    let mut scratch = vec![0.0; scratch_len(mode, n)];
    for _ in 0..3 {
        transform(mode, &x, &mut y, &mut scratch);
        black_box(&y);
    }
    let start = Instant::now();
    for _ in 0..passes {
        transform(
            black_box(mode),
            black_box(&x),
            black_box(&mut y),
            black_box(&mut scratch),
        );
        black_box(&y);
    }
    let seconds = start.elapsed().as_secs_f64();
    for (i, actual) in y.iter().enumerate() {
        assert_eq!(*actual, oracle(i), "element {i}");
    }
    let checksum: f64 = y.iter().sum();
    let items = n as f64 * passes as f64;
    println!("mode,n,passes,seconds,ns_per_item,algorithm_gflops,checksum");
    println!(
        "{mode},{n},{passes},{seconds:.9},{:.6},{:.6},{checksum}",
        seconds * 1e9 / items,
        3.0 * items / seconds / 1e9
    );
    if a.get(4).is_some_and(|s| s == "dump") {
        for v in y {
            println!("value,{v}");
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn all_schedules_match_integer_oracle() {
        for n in [0, 1, 7, 1023, 1024, 1025, 4099] {
            let x: Vec<_> = (0..n).map(input).collect();
            let expected: Vec<_> = (0..n).map(oracle).collect();
            for mode in ["split", "blocked", "fused"] {
                let mut y = vec![f64::NAN; n];
                let mut s = vec![0.0; scratch_len(mode, n)];
                transform(mode, &x, &mut y, &mut s);
                assert_eq!(y, expected);
            }
        }
    }
    #[test]
    fn block_edges_and_negative_inputs() {
        let x: Vec<_> = (0..2051).map(input).collect();
        for tile in [1, 3, 31, 1024, 4096] {
            let mut y = vec![f64::NAN; x.len()];
            transform("blocked", &x, &mut y, &mut vec![0.0; tile]);
            assert_eq!(y, (0..x.len()).map(oracle).collect::<Vec<_>>());
        }
    }
    #[test]
    #[should_panic(expected = "assertion")]
    fn rejects_output_length_mismatch() {
        fused(&[1.0], &mut []);
    }
    #[test]
    #[should_panic(expected = "assertion")]
    fn rejects_empty_tile() {
        transform("blocked", &[1.0], &mut [0.0], &mut []);
    }
}
