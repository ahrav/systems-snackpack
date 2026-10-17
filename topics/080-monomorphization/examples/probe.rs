//! Standalone compiler input; the campaign selects mode and policy count via cfg.
#![allow(dead_code)]
#![allow(unexpected_cfgs)]
#[path = "../src/lib.rs"]
mod kernels;
use kernels::{Format, input};
use std::{hint::black_box, time::Instant};

#[cfg(not(outlined))]
use kernels::generic as selected;
#[cfg(outlined)]
use kernels::outlined as selected;

type Kernel = fn(&[u8]) -> u64;

fn functions() -> Vec<Kernel> {
    #[cfg(not(many))]
    {
        vec![selected::<Format<1>>]
    }
    #[cfg(many)]
    {
        vec![
            selected::<Format<1>>,
            selected::<Format<2>>,
            selected::<Format<3>>,
            selected::<Format<4>>,
            selected::<Format<5>>,
            selected::<Format<6>>,
            selected::<Format<7>>,
            selected::<Format<8>>,
            selected::<Format<9>>,
            selected::<Format<10>>,
            selected::<Format<11>>,
            selected::<Format<12>>,
            selected::<Format<13>>,
            selected::<Format<14>>,
            selected::<Format<15>>,
            selected::<Format<16>>,
        ]
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let len: usize = args
        .get(1)
        .expect("length")
        .parse()
        .expect("integer length");
    let calls: usize = args
        .get(2)
        .expect("calls (0 for oracle)")
        .parse()
        .expect("integer calls");
    let bytes = input(len);
    let funcs = functions();
    if calls == 0 {
        for (i, f) in funcs.iter().enumerate() {
            println!("{} {}", i + 1, f(&bytes));
        }
        return;
    }
    let mut checksum = 0u64;
    let start = Instant::now();
    for i in 0..calls {
        let f = black_box(funcs[i % funcs.len()]);
        checksum = checksum.wrapping_add(black_box(f(black_box(&bytes))));
    }
    let nanos = start.elapsed().as_nanos();
    println!("{len},{calls},{},{nanos},{checksum}", funcs.len());
}
