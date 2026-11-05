//! Read E input timestamp amount, W input frontier, I input, A input, or R lateness.
use std::io::{self, BufRead};
use topic099_event_time::Windows;
fn pairs(m: &std::collections::BTreeMap<i64, i64>) -> String {
    let s = m
        .iter()
        .map(|(k, v)| format!("{k}:{v}"))
        .collect::<Vec<_>>()
        .join(",");
    if s.is_empty() { "-".into() } else { s }
}
fn main() {
    let mut w = Windows::new(5);
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.is_empty() {
            continue;
        }
        let n = |i: usize| fields[i].parse::<i64>().unwrap();
        match fields[0] {
            "R" => w = Windows::new(n(1)),
            "E" => w.event(n(1).try_into().unwrap(), n(2), n(3)),
            "W" => w.progress(n(1).try_into().unwrap(), n(2)),
            "I" => w.idle(n(1).try_into().unwrap(), true),
            "A" => w.idle(n(1).try_into().unwrap(), false),
            _ => panic!("unknown command"),
        }
        println!(
            "{} {} {} {} {}",
            w.frontier,
            w.dropped,
            w.writes,
            pairs(&w.live),
            pairs(&w.sink)
        );
    }
}
