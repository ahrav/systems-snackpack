//! Line protocol for an independent Python sum and effect-sequence oracle.
use std::io::{self, BufRead};
use topic095_jit_specialization::{Row, specialized};
fn main() {
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let rows: Vec<_> = line
            .split_whitespace()
            .map(|s| {
                let (shape, value) = s.split_once(':').unwrap();
                let v = value.parse().unwrap();
                match shape {
                    "A" => Row::A(v),
                    "B" => Row::B(v),
                    _ => panic!("shape"),
                }
            })
            .collect();
        let r = specialized(&rows);
        println!(
            "{};{};{}",
            r.total,
            r.deopt_at.map_or_else(|| "none".into(), |i| i.to_string()),
            r.effects
                .iter()
                .map(usize::to_string)
                .collect::<Vec<_>>()
                .join(",")
        );
    }
}
