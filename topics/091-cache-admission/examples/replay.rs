//! Replay a little-endian u32 request trace through a selected policy.
use cache_admission::{Cache, Policy};
use std::{env, fs, hint::black_box, time::Instant};

fn main() {
    let args: Vec<_> = env::args().collect();
    assert_eq!(
        args.len(),
        8,
        "replay POLICY TRACE CAPACITY UNIVERSE AGE REPEATS EXPECTED_HITS"
    );
    let policy = Policy::parse(&args[1]);
    let raw = fs::read(&args[2]).unwrap();
    assert!(raw.len() % 4 == 0 && !raw.is_empty());
    let trace: Vec<_> = raw
        .chunks_exact(4)
        .map(|c| u32::from_le_bytes(c.try_into().unwrap()) as usize)
        .collect();
    let cap = args[3].parse().unwrap();
    let universe = args[4].parse().unwrap();
    let age = args[5].parse().unwrap();
    let repeats: usize = args[6].parse().unwrap();
    let expected: usize = args[7].parse().unwrap();
    assert!(repeats > 0);
    let mut caches: Vec<_> = (0..repeats)
        .map(|_| Cache::new(cap, universe, policy, age))
        .collect();
    let mut totals = vec![0_usize; repeats];
    let start = Instant::now();
    for (cache, hits) in caches.iter_mut().zip(&mut totals) {
        for &key in black_box(&trace) {
            *hits += usize::from(cache.access(key));
        }
    }
    let elapsed = start.elapsed().as_nanos();
    black_box(&caches);
    assert!(totals.iter().all(|&n| n == expected));
    println!(
        "{{\"policy\":\"{}\",\"requests\":{},\"hits\":{},\"repeats\":{},\"elapsed_ns\":{},\"residents\":{:?}}}",
        args[1],
        trace.len(),
        totals[0],
        repeats,
        elapsed,
        caches.last().unwrap().residents()
    );
}
