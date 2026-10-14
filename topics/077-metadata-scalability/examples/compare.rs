//! Measure cache application only; prebuilt inputs and one cache per process.
use metadata_scalability::{Cache, Change};
use std::{hint::black_box, time::Instant};

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(
        args.len(),
        4,
        "compare snapshot|delta sparse|dense|hot ITERATIONS"
    );
    let variant = &args[1];
    assert!(variant == "snapshot" || variant == "delta");
    let n = 65_536;
    let (updates, keys) = match args[2].as_str() {
        "sparse" => (64, n),
        "dense" => (n, n),
        "hot" => (4 * n, 64),
        _ => panic!("unknown workload"),
    };
    let iterations: u64 = args[3].parse().unwrap();
    assert!(iterations > 0 && iterations <= 1_000_000);
    let mut snapshots = Vec::new();
    let mut batches = Vec::new();
    for phase in 0..2 {
        let mut snapshot = vec![Some(0); n];
        let changes: Vec<_> = (0..updates)
            .map(|i| {
                // Odd multiplication permutes power-of-two key spaces.
                let key = (i * 4051) % keys;
                let value = if (i + phase) % 7 == 0 {
                    None
                } else {
                    Some((phase + 1) as u64)
                };
                snapshot[key] = value;
                Change { key, value }
            })
            .collect();
        snapshots.push(snapshot);
        batches.push(changes);
    }
    // Verify both alternating transitions before timing, including sparse keys.
    let mut check = Cache::new(vec![Some(0); n]);
    for i in 0..4 {
        check
            .apply(
                i * updates as u64,
                (i + 1) * updates as u64,
                &batches[i as usize % 2],
            )
            .unwrap();
        assert_eq!(check.slots(), snapshots[i as usize % 2]);
    }
    let mut cache = Cache::new(vec![Some(0); n]);
    let start = Instant::now();
    for i in 0..iterations {
        let phase = i as usize % 2;
        let from = i * updates as u64;
        let to = from + updates as u64;
        if variant == "delta" {
            black_box(&mut cache)
                .apply(from, to, black_box(&batches[phase]))
                .unwrap();
        } else {
            black_box(&mut cache)
                .install(to, black_box(&snapshots[phase]))
                .unwrap();
        }
        black_box(cache.cursor());
    }
    let ns = start.elapsed().as_nanos();
    assert_eq!(cache.slots(), snapshots[(iterations as usize - 1) % 2]);
    assert_eq!(cache.cursor(), iterations * updates as u64);
    println!(
        "{},{},{},{},{},{:.3},{},{}",
        variant,
        args[2],
        iterations,
        updates,
        ns,
        ns as f64 / iterations as f64,
        n * std::mem::size_of::<Option<u64>>(),
        updates * std::mem::size_of::<Change>()
    );
}
