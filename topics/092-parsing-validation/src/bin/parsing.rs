//! CLI for differential checks and controlled parser timing.
use parsing_validation::{Strategy, parse};
use std::hint::black_box;
use std::io::{self, BufRead, Write};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("verify") {
        let mut writer = io::BufWriter::new(io::stdout().lock());
        for line in io::stdin().lock().lines() {
            let line = line.unwrap();
            let input: Vec<u8> = line
                .as_bytes()
                .chunks_exact(2)
                .map(|pair| u8::from_str_radix(std::str::from_utf8(pair).unwrap(), 16).unwrap())
                .collect();
            for strategy in [Strategy::Fused, Strategy::Split, Strategy::Indexed] {
                let mut output = Vec::new();
                if parse(&input, strategy, &mut output, &mut Vec::new()).is_err() {
                    writeln!(writer, "ERR").unwrap();
                } else {
                    write!(writer, "OK").unwrap();
                    for value in output {
                        write!(writer, " {value}").unwrap();
                    }
                    writeln!(writer).unwrap();
                }
            }
        }
        return;
    }
    assert_eq!(
        args.len(),
        5,
        "usage: parsing bench fused|split|indexed file iterations"
    );
    assert_eq!(args[1], "bench");
    let strategy = match args[2].as_str() {
        "fused" => Strategy::Fused,
        "split" => Strategy::Split,
        "indexed" => Strategy::Indexed,
        _ => panic!("unknown strategy"),
    };
    let input = std::fs::read(&args[3]).unwrap();
    let iterations: usize = args[4].parse().unwrap();
    assert!(iterations > 0);
    let records = input.iter().filter(|&&b| b == b'\n').count();
    let mut output = Vec::with_capacity(records);
    let mut offsets = Vec::with_capacity(if matches!(strategy, Strategy::Indexed) {
        records
    } else {
        0
    });
    // Equal fixed warmup count. File I/O and capacity allocation precede timing.
    for _ in 0..4 {
        black_box(parse(
            black_box(&input),
            strategy,
            &mut output,
            &mut offsets,
        ))
        .ok();
        black_box(&output);
    }
    let start = Instant::now();
    for _ in 0..iterations {
        black_box(parse(
            black_box(&input),
            strategy,
            &mut output,
            &mut offsets,
        ))
        .ok();
        black_box(&output);
    }
    let elapsed = start.elapsed().as_nanos();
    let accepted = parse(&input, strategy, &mut output, &mut offsets).is_ok();
    let checksum: u64 = output.iter().map(|&v| u64::from(v)).sum();
    println!(
        "{},{},{},{},{},{},{}",
        args[2],
        input.len(),
        iterations,
        elapsed,
        accepted,
        output.len(),
        checksum
    );
}
