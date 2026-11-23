//! Emit auditable reconstructions or time one resident-memory repair.
use std::{env, hint::black_box, time::Instant};
use topic117_erasure_repair::{Code, encode};

fn check() {
    for (name, code) in [("rs", Code::ReedSolomon), ("lrc", Code::Local)] {
        let data = std::array::from_fn(|i| {
            (0..17)
                .map(|j| ((i + 1) * (j * j + 17) + 71 * j) as u8)
                .collect()
        });
        let stripe = encode(code, data);
        for (id, bytes) in stripe.iter().enumerate() {
            let hex: String = bytes.iter().map(|b| format!("{b:02x}")).collect();
            println!("encoded {name} {id} {hex}");
        }
        for missing in 0u16..512 {
            let mut recoverable = 0u16;
            for target in 0..9 {
                if missing & (1 << target) == 0 {
                    continue;
                }
                if let Some(plan) = code.repair(target, missing) {
                    let mut out = vec![0; 17];
                    plan.rebuild(&mut out, |i| {
                        assert_eq!(missing & (1 << i), 0);
                        &stripe[i]
                    });
                    assert_eq!(out, stripe[target]);
                    recoverable |= 1 << target;
                }
            }
            println!("mask {name} {missing} {recoverable}");
        }
    }
}

fn bench(code: Code, target: usize) {
    const BYTES: usize = 1 << 20;
    const REPEATS: usize = 8;
    let mut rng = 65_537u64;
    let data = std::array::from_fn(|_| {
        (0..BYTES)
            .map(|_| {
                rng ^= rng << 13;
                rng ^= rng >> 7;
                rng ^= rng << 17;
                rng as u8
            })
            .collect()
    });
    let stripe = encode(code, data);
    let plan = code.repair(target, 1 << target).unwrap();
    let mut out = vec![0; BYTES];
    plan.rebuild(&mut out, |i| &stripe[i]);
    assert_eq!(out, stripe[target]);
    let mut read_bytes = 0;
    let start = Instant::now();
    for _ in 0..REPEATS {
        plan.rebuild(black_box(&mut out), |i| {
            let chunk = &stripe[i];
            read_bytes += chunk.len();
            black_box(chunk)
        });
        black_box(&out);
    }
    let elapsed = start.elapsed();
    assert_eq!(out, stripe[target]);
    println!(
        "{} {} {} {}",
        plan.helpers().count(),
        read_bytes / REPEATS,
        REPEATS,
        elapsed.as_nanos()
    );
}

fn main() {
    let args: Vec<_> = env::args().skip(1).collect();
    match args.as_slice() {
        [cmd] if cmd == "check" => check(),
        [cmd, code, target] if cmd == "bench" => {
            let code = match code.as_str() {
                "rs" => Code::ReedSolomon,
                "lrc" => Code::Local,
                _ => panic!("use rs or lrc"),
            };
            bench(code, target.parse().expect("target ID 0..8"));
        }
        _ => panic!("use check or bench <rs|lrc> <target ID 0..8>"),
    }
}
