//! Floating-point reduction contracts, exact-domain timings, and counterexamples.
use std::hint::black_box;
use std::io::{self, BufRead};
use std::time::Instant;

#[inline(never)]
fn ordered(xs: &[f64]) -> f64 {
    xs.iter().fold(0.0, |s, &x| s + x)
}

#[inline(never)]
fn lanes4(xs: &[f64]) -> f64 {
    let mut s = [0.0; 4];
    let mut chunks = xs.chunks_exact(4);
    for x in &mut chunks {
        s[0] += x[0];
        s[1] += x[1];
        s[2] += x[2];
        s[3] += x[3];
    }
    for (i, &x) in chunks.remainder().iter().enumerate() {
        s[i] += x;
    }
    (s[0] + s[1]) + (s[2] + s[3])
}

// Finite inputs and non-overflowing intermediates are required for accuracy claims.
#[inline(never)]
fn compensated(xs: &[f64]) -> f64 {
    let (mut s, mut c) = (0.0_f64, 0.0_f64);
    for &x in xs {
        let t = s + x;
        c += if s.abs() >= x.abs() {
            (s - t) + x
        } else {
            (x - t) + s
        };
        s = t;
    }
    s + c
}

#[inline(never)]
fn separate(a: f64, b: f64, c: f64) -> f64 {
    a * b + c
}

#[inline(never)]
fn fused(a: f64, b: f64, c: f64) -> f64 {
    a.mul_add(b, c)
}

fn dataset(workload: &str, n: usize) -> (Vec<f64>, f64) {
    assert!((1..=1 << 20).contains(&n));
    let numerators: Vec<i64> = (0..n)
        .map(|i| match workload {
            "positive" => (i * 37 % 1024) as i64,
            "signed" => (i * 73 % 2048) as i64 - 1024,
            _ => panic!("unknown workload"),
        })
        .collect();
    let exact = numerators.iter().sum::<i64>() as f64 / 1024.0;
    let xs = numerators.into_iter().map(|x| x as f64 / 1024.0).collect();
    (xs, exact)
}

fn probe() {
    for line in io::stdin().lock().lines() {
        let line = line.expect("input line");
        let mut tokens = line.split_whitespace();
        let op = tokens.next().expect("operation");
        let xs: Vec<f64> = tokens
            .map(|s| f64::from_bits(u64::from_str_radix(s, 16).expect("hex bits")))
            .collect();
        let values = match op {
            "sum" => vec![ordered(&xs), lanes4(&xs), compensated(&xs)],
            "fma" => {
                assert_eq!(xs.len(), 3);
                vec![separate(xs[0], xs[1], xs[2]), fused(xs[0], xs[1], xs[2])]
            }
            _ => panic!("unknown operation"),
        };
        println!(
            "{}",
            values
                .iter()
                .map(|x| format!("{:016x}", x.to_bits()))
                .collect::<Vec<_>>()
                .join(" ")
        );
    }
}

fn demo() {
    let m = 2.0_f64.powi(54);
    let xs = black_box([m, 1.0, -m, 1.0]);
    println!(
        "ordered={} lanes4={} compensated={} exact=2",
        ordered(&xs),
        lanes4(&xs),
        compensated(&xs)
    );
    let a = black_box(1.0 + 2.0_f64.powi(-27));
    let b = black_box(1.0 - 2.0_f64.powi(-27));
    println!(
        "separate={:e} fused={:e}",
        separate(a, b, -1.0),
        fused(a, b, -1.0)
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str).unwrap_or("demo") {
        "demo" => demo(),
        "probe" => probe(),
        "bench" => {
            assert_eq!(args.len(), 6, "bench METHOD WORKLOAD N REPEATS");
            let f: fn(&[f64]) -> f64 = match args[2].as_str() {
                "ordered" => ordered,
                "lanes4" => lanes4,
                "compensated" => compensated,
                _ => panic!("unknown method"),
            };
            let n = args[4].parse::<usize>().expect("n");
            let repeats = args[5].parse::<usize>().expect("repeats");
            assert!((1..=1 << 24).contains(&repeats));
            let (xs, expected) = dataset(&args[3], n);
            // All partial sums are integer multiples of 2^-10 with bounded numerator.
            for _ in 0..3 {
                assert_eq!(black_box(f(black_box(&xs))), expected);
            }
            let start = Instant::now();
            let mut result = 0.0;
            for _ in 0..repeats {
                result = black_box(f(black_box(&xs)));
            }
            let elapsed = start.elapsed().as_nanos();
            assert_eq!(result, expected);
            println!("method,workload,n,repeats,elapsed_ns,result_bits");
            println!(
                "{},{},{n},{repeats},{elapsed},{:016x}",
                args[2],
                args[3],
                result.to_bits()
            );
        }
        _ => panic!("use demo, probe, or bench"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cancellation_changes_contract() {
        let m = 2.0_f64.powi(54);
        let xs = [m, 1.0, -m, 1.0];
        assert_eq!(ordered(&xs), 1.0);
        assert_eq!(lanes4(&xs), 0.0);
        assert_eq!(compensated(&xs), 2.0);
    }
    #[test]
    fn fma_changes_rounding() {
        let a = 1.0 + 2.0_f64.powi(-27);
        let b = 1.0 - 2.0_f64.powi(-27);
        assert_eq!(separate(a, b, -1.0), 0.0);
        assert_eq!(fused(a, b, -1.0), -2.0_f64.powi(-54));
    }
    #[test]
    fn exact_domain_includes_tails() {
        for n in 1..130 {
            for workload in ["positive", "signed"] {
                let (xs, expected) = dataset(workload, n);
                for f in [ordered, lanes4, compensated] {
                    assert_eq!(f(&xs), expected);
                    assert_eq!(f(&[]).to_bits(), 0);
                }
            }
        }
    }
    #[test]
    fn special_values_are_observable() {
        assert_eq!((1.0 / black_box(-0.0_f64)), f64::NEG_INFINITY);
        for f in [ordered, lanes4, compensated] {
            assert!(f(&[f64::NAN]).is_nan());
            assert_eq!(f(&[-0.0]).to_bits(), 0);
            assert_eq!(f(&[f64::from_bits(1), f64::from_bits(1)]).to_bits(), 2);
        }
        assert_eq!(ordered(&[f64::INFINITY]), f64::INFINITY);
        assert!(compensated(&[f64::INFINITY]).is_nan());
        assert!(ordered(&[f64::INFINITY, f64::NEG_INFINITY]).is_nan());
    }
    #[test]
    fn finite_inputs_do_not_prevent_intermediate_overflow() {
        let xs = [f64::MAX, f64::MAX, -f64::MAX];
        assert_eq!(ordered(&xs), f64::INFINITY);
        assert!(compensated(&xs).is_nan());
    }
}
