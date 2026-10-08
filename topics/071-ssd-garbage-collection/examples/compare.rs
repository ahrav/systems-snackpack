//! Replays one deterministic trace and reports model work plus simulator time.
use ssd_gc::{Flash, Policy, next_random};
use std::{env, time::Instant};
fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(
        args.len(),
        8,
        "policy blocks occupancy pattern writes warmup seed"
    );
    let policy = match args[1].as_str() {
        "rr" => Policy::RoundRobin,
        "greedy" => Policy::Greedy,
        "sample4" => Policy::Sample4,
        _ => panic!("policy"),
    };
    let blocks: usize = args[2].parse().unwrap();
    let occupancy: usize = args[3].parse().unwrap();
    assert!((1..=95).contains(&occupancy));
    let logical = blocks * 32 * occupancy / 100;
    let writes: usize = args[5].parse().unwrap();
    let warmup: usize = args[6].parse().unwrap();
    let seed: u64 = args[7].parse().unwrap();
    let mut random = seed;
    let trace: Vec<usize> = (0..warmup + writes)
        .map(|i| {
            let r = next_random(&mut random);
            match args[4].as_str() {
                "uniform" => r as usize % logical,
                "hot" => {
                    let key = next_random(&mut random) as usize;
                    if r % 10 < 9 {
                        key % (logical / 10).max(1)
                    } else {
                        key % logical
                    }
                }
                "cyclic" => i % logical,
                _ => panic!("pattern"),
            }
        })
        .collect();
    let setup = Instant::now();
    let mut f = Flash::new(blocks, 32, logical, policy, seed ^ 0x9e3779b97f4a7c15);
    let mut oracle = vec![0; logical];
    for key in 0..logical {
        f.write(key, 0);
    }
    let setup_ns = setup.elapsed().as_nanos();
    for (i, &key) in trace[..warmup].iter().enumerate() {
        f.write(key, i as u64 + 1);
        oracle[key] = i as u64 + 1;
    }
    f.check();
    f.reset_stats();
    let free_start = f.writable_pages();
    let start = Instant::now();
    for (i, &key) in trace[warmup..].iter().enumerate() {
        f.write(key, (warmup + i) as u64 + 1);
    }
    let elapsed_ns = start.elapsed().as_nanos();
    for (i, &key) in trace[warmup..].iter().enumerate() {
        oracle[key] = (warmup + i) as u64 + 1;
    }
    f.check();
    for (key, expected) in oracle.iter().enumerate() {
        assert_eq!(f.read(key), Some(*expected));
    }
    let free_end = f.writable_pages();
    let s = f.stats();
    assert_eq!(
        free_end as i64 - free_start as i64,
        32 * s.erases as i64 - s.host as i64 - s.copies as i64
    );
    assert_eq!(s.host, writes as u64);
    println!(
        "{{\"policy\":\"{}\",\"blocks\":{},\"occupancy\":{},\"pattern\":\"{}\",\"writes\":{},\"warmup\":{},\"seed\":{},\"elapsed_ns\":{},\"setup_ns\":{},\"copies\":{},\"erases\":{},\"probes\":{},\"free_start\":{},\"free_end\":{},\"oracle\":true}}",
        args[1],
        blocks,
        occupancy,
        args[4],
        writes,
        warmup,
        seed,
        elapsed_ns,
        setup_ns,
        s.copies,
        s.erases,
        s.probes,
        free_start,
        free_end
    );
}
