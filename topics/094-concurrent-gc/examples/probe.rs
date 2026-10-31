//! Batch oracle interface and fixed-schedule simulator benchmark.
use std::{
    hint::black_box,
    io::{self, BufRead},
    time::Instant,
};
use topic094_concurrent_gc::{Marker, Mode};
fn mode(s: &str) -> Mode {
    match s {
        "stw" => Mode::Stw,
        "insertion" => Mode::Insertion,
        "satb" => Mode::Satb,
        "none" => Mode::None,
        _ => panic!("mode"),
    }
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args[1] == "batch" {
        for line in io::stdin().lock().lines() {
            let line = line.unwrap();
            let a: Vec<&str> = line.split_whitespace().collect();
            let edge = |s: &str| {
                let x: isize = s.parse().unwrap();
                if x < 0 { None } else { Some(x as usize) }
            };
            let mut m = Marker::new(
                a[1..4].iter().map(|s| edge(s)).collect(),
                &[0, 1],
                mode(a[0]),
            );
            for j in [4, 7] {
                for _ in 0..a[j].parse::<usize>().unwrap() {
                    m.scan();
                }
                m.store(a[j + 1].parse().unwrap(), edge(a[j + 2]));
            }
            m.finish();
            let mask: usize = m
                .marked()
                .iter()
                .enumerate()
                .map(|(i, &v)| usize::from(v) << i)
                .sum();
            println!("{mask}");
        }
    } else {
        let policy = mode(&args[2]);
        let workload = &args[3];
        let n = 16384;
        let rounds = 64;
        let start = Instant::now();
        let mut totals = [0usize; 3];
        for _ in 0..rounds {
            let heap: Vec<_> = (0..n)
                .map(|i| if i + 1 < n { Some(i + 1) } else { None })
                .collect();
            let mut m = Marker::new(black_box(heap), &[0], policy);
            for i in 0..n {
                let new = match workload.as_str() {
                    "keep" => {
                        if i + 1 < n {
                            Some(i + 1)
                        } else {
                            None
                        }
                    }
                    "delete" => None,
                    "replace" => Some(0),
                    _ => panic!("workload"),
                };
                m.store(i, black_box(new));
                if i % 16 == 0 {
                    m.scan();
                }
            }
            m.finish();
            totals[0] += m.scans;
            totals[1] += m.barriers;
            totals[2] += m.marked().iter().filter(|&&x| x).count();
            black_box(&m);
        }
        println!(
            "{} {} {} {}",
            start.elapsed().as_nanos(),
            totals[0],
            totals[1],
            totals[2]
        );
    }
}
