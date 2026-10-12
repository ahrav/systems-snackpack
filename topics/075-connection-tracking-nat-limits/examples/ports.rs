//! Benchmark a frozen trace against an independent HashSet oracle before timing.
use connection_tracking_nat_limits::{Allocator, Kind};
use std::{collections::HashSet, hint::black_box, time::Instant};
#[derive(Clone, Copy)]
enum Event {
    Add(usize),
    Release(usize, usize),
}
fn config(case: &str) -> (usize, usize, usize, usize, bool) {
    match case {
        "tiny" => (64, 1, 16, 10000, false),
        "crowded" => (4096, 1, 3891, 10000, false),
        "full" => (4096, 1, 4096, 10000, false),
        "spread" => (4096, 16, 1024, 10000, false),
        "skew" => (4096, 16, 3891, 10000, true),
        "short" => (4096, 16, 0, 32, false),
        _ => panic!("case must be tiny/crowded/full/spread/skew/short"),
    }
}
fn trace(case: &str) -> (usize, usize, Vec<Event>, Vec<u64>, usize) {
    let (ports, destinations, occupied, steps, skew) = config(case);
    let mut events = Vec::new();
    let mut expected = Vec::new();
    let mut set = HashSet::new();
    let mut held = vec![Vec::new(); destinations];
    for (d, entries) in held.iter_mut().enumerate() {
        let fill = if skew && d != 0 { 16 } else { occupied };
        for p in 0..fill {
            events.push(Event::Add(d));
            expected.push(p as u64);
            set.insert((d, p));
            entries.push(p);
        }
    }
    let prefix = events.len();
    let mut random = 1u64;
    for i in 0..steps {
        random ^= random << 13;
        random ^= random >> 7;
        random ^= random << 17;
        let d = if skew && i % 10 != 0 {
            0
        } else {
            i % destinations
        };
        // At full occupancy, test failure before releasing a slot.
        if held[d].len() == ports {
            events.push(Event::Add(d));
            expected.push(u64::MAX);
        }
        if !held[d].is_empty() {
            let index = random as usize % held[d].len();
            let p = held[d].swap_remove(index);
            assert!(set.remove(&(d, p)));
            events.push(Event::Release(d, p));
            expected.push(1);
        }
        let p = (0..ports).find(|p| !set.contains(&(d, *p))).unwrap();
        set.insert((d, p));
        held[d].push(p);
        events.push(Event::Add(d));
        expected.push(p as u64);
    }
    (ports, destinations, events, expected, prefix)
}
fn apply(a: &mut Allocator, event: Event) -> u64 {
    match event {
        Event::Add(d) => a.allocate(d).map_or(u64::MAX, |p| p as u64),
        Event::Release(d, p) => u64::from(a.release(d, p)),
    }
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 4, "ports scan|bitmap|tree CASE full|steady");
    let kind = match args[1].as_str() {
        "scan" => Kind::Scan,
        "bitmap" => Kind::Bitmap,
        "tree" => Kind::Tree,
        _ => panic!("bad candidate"),
    };
    assert!(matches!(args[3].as_str(), "full" | "steady"));
    let (ports, destinations, events, expected, prefix) = trace(&args[2]);
    // All outputs, including rejected admissions, must match before timing.
    let mut check = Allocator::new(kind, destinations, ports, usize::MAX);
    for (&event, &want) in events.iter().zip(&expected) {
        assert_eq!(apply(&mut check, event), want);
    }
    drop(check);
    let mut output = Vec::with_capacity(events.len());
    let start;
    let mut a;
    let slice;
    if args[3] == "full" {
        start = Instant::now();
        a = Allocator::new(kind, destinations, ports, usize::MAX);
        slice = &events[..];
    } else {
        a = Allocator::new(kind, destinations, ports, usize::MAX);
        for &event in &events[..prefix] {
            black_box(apply(&mut a, event));
        }
        slice = &events[prefix..];
        start = Instant::now();
    }
    for &event in black_box(slice) {
        output.push(apply(&mut a, event));
    }
    black_box(&output);
    let checksum = output.iter().fold(0u64, |x, y| x.wrapping_add(*y));
    if args[3] == "full" {
        drop(a);
    }
    let elapsed = start.elapsed().as_nanos();
    // Result storage allocation/drop excluded in both modes; writes/checksum included.
    assert_eq!(
        output,
        if args[3] == "full" {
            &expected[..]
        } else {
            &expected[prefix..]
        }
    );
    println!(
        "{},{},{},{},{},{}",
        args[1],
        args[2],
        args[3],
        elapsed,
        slice.len(),
        checksum
    );
}
