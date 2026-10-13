//! Run correctness, movement audit, or one timed process. See run.py.
use consistent_hashing_movement::{Map, check, mix};
use std::{hint::black_box, time::Instant};
fn main() {
    let a: Vec<_> = std::env::args().collect();
    if a[1] == "check" {
        check();
        println!("oracle and movement contracts PASS");
        return;
    }
    if a[1] == "movement" {
        let keys: Vec<_> = (0..65536).map(mix).collect();
        println!(
            "kind,event,keys,moved,unrelated,max_over_mean,bytes_fraction,request_fraction,hops"
        );
        for kind in ["mod", "hrw", "ring1", "ring64"] {
            let before = Map::new(kind, &(0..8).collect::<Vec<_>>());
            let removed = Map::new(kind, &[0, 1, 2, 4, 5, 6, 7]);
            for event in ["add", "remove", "replace"] {
                let ids = match event {
                    "add" => (0..9).collect::<Vec<_>>(),
                    "remove" => vec![0, 1, 2, 4, 5, 6, 7],
                    _ => vec![0, 1, 2, 4, 5, 6, 7, 8],
                };
                let after = Map::new(kind, &ids);
                let mut load = [0_u64; 9];
                let (
                    mut moved,
                    mut unrelated,
                    mut bytes,
                    mut total,
                    mut requests,
                    mut reqtotal,
                    mut hops,
                ) = (0, 0, 0_u64, 0_u64, 0_u64, 0_u64, 0);
                for (i, &key) in keys.iter().enumerate() {
                    let old = before.owner(key);
                    let new = after.owner(key);
                    load[new as usize] += 1;
                    // Adversarial data correlated with the OLD owner, common in range-derived sizes.
                    let size = if old == 3 { 1024 } else { 1 };
                    let rate = if i == 0 { 65536 } else { 1 };
                    total += size;
                    reqtotal += rate;
                    if old != new {
                        moved += 1;
                        bytes += size;
                        requests += rate;
                        if (event == "add" && new != 8)
                            || (event == "remove" && old != 3)
                            || (event == "replace" && old != 3 && new != 8)
                        {
                            unrelated += 1;
                        }
                    }
                    hops += if event == "replace" {
                        usize::from(old != removed.owner(key))
                            + usize::from(removed.owner(key) != new)
                    } else {
                        usize::from(old != new)
                    };
                }
                println!(
                    "{kind},{event},{},{moved},{unrelated},{:.6},{:.6},{:.6},{hops}",
                    keys.len(),
                    *load.iter().max().unwrap() as f64 / (keys.len() as f64 / ids.len() as f64),
                    bytes as f64 / total as f64,
                    requests as f64 / reqtotal as f64
                );
            }
        }
        return;
    }
    let kind = &a[1];
    let n: u64 = a[2].parse().unwrap();
    let pattern = &a[3];
    let len = if pattern == "small" { 128 } else { 32768 };
    let keys: Vec<_> = (0..len)
        .map(|i| {
            mix(if pattern == "hot" && i % 20 != 0 {
                7
            } else {
                i
            })
        })
        .collect();
    let ids: Vec<_> = (0..n).collect();
    let start = Instant::now();
    let map = Map::new(kind, &ids);
    let mut cold = 0_u64;
    for &h in &keys {
        cold = cold.wrapping_add(black_box(map.owner(black_box(h))));
    }
    let cold_ns = start.elapsed().as_nanos();
    for &h in &keys {
        black_box(map.owner(black_box(h)));
    }
    let loops = 262144 / len;
    let start = Instant::now();
    let mut sum = 0_u64;
    for _ in 0..loops {
        for &h in &keys {
            sum = sum.wrapping_add(black_box(map.owner(black_box(h))));
        }
    }
    let elapsed = start.elapsed().as_nanos();
    assert_eq!(sum, cold.wrapping_mul(loops));
    println!(
        "{{\"kind\":\"{kind}\",\"nodes\":{n},\"pattern\":\"{pattern}\",\"lookups\":{},\"ns\":{elapsed},\"cold_ns\":{cold_ns},\"bytes\":{},\"checksum\":{sum}}}",
        len * loops,
        map.bytes()
    );
}
