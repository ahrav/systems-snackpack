//! Fixed-window throughput probe. See the topic README for its workload contract.
use sequence_locks::{Read, Snapshot, busy_for};
use std::hint::black_box;
use std::sync::{Barrier, RwLock};
use std::time::{Duration, Instant};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        5,
        "usage: sequence-locks seq|fallback|rw none|paced|held|hot readers milliseconds"
    );
    let mode = args[1].as_str();
    let workload = args[2].as_str();
    assert!(["seq", "fallback", "rw"].contains(&mode));
    assert!(["none", "paced", "held", "hot"].contains(&workload));
    let readers: usize = args[3].parse().unwrap();
    let millis: u64 = args[4].parse().unwrap();
    assert!((1..=64).contains(&readers) && (50..=10_000).contains(&millis));
    let duration = Duration::from_millis(millis);
    let hold = if workload == "held" {
        Duration::from_micros(20)
    } else {
        Duration::ZERO
    };
    let period = Duration::from_micros(100);
    let s = Snapshot::new();
    let rw = RwLock::new((0_u64, 0_u64));
    let gate = Barrier::new(readers + 2);
    // The second barrier publishes one shared start after every worker exists.
    let epoch = std::sync::OnceLock::new();
    let (writes, skipped, elapsed) = std::thread::scope(|scope| {
        let mut counts = Vec::new();
        for _ in 0..readers {
            let (s, rw, gate, epoch) = (&s, &rw, &gate, &epoch);
            counts.push(scope.spawn(move || {
                gate.wait();
                gate.wait();
                let end = *epoch.get().unwrap() + duration;
                let (mut reads, mut odd, mut changed, mut fallback, mut checksum) =
                    (0_u64, 0_u64, 0_u64, 0_u64, 0_u64);
                while Instant::now() < end {
                    let r = match mode {
                        "seq" => s.read(None),
                        "fallback" => s.read(Some(8)),
                        "rw" => Read {
                            value: *rw.read().unwrap(),
                            ..Read::default()
                        },
                        _ => unreachable!(),
                    };
                    assert_eq!(r.value.1, r.value.0 * 2);
                    checksum = checksum.wrapping_add(black_box(r.value.0));
                    reads += 1;
                    odd += r.odd;
                    changed += r.changed;
                    fallback += u64::from(r.fallback);
                }
                black_box(checksum);
                (reads, odd, changed, fallback)
            }));
        }
        let writer = scope.spawn(|| {
            gate.wait();
            gate.wait();
            let end = *epoch.get().unwrap() + duration;
            let mut next = *epoch.get().unwrap();
            let (mut writes, mut skipped) = (0_u64, 0_u64);
            if workload != "none" {
                loop {
                    let now = Instant::now();
                    if now >= end {
                        break;
                    }
                    if workload != "hot" && now < next {
                        std::hint::spin_loop();
                        continue;
                    }
                    if workload != "hot" {
                        // Keep an absolute cadence; skip missed slots instead of catch-up bursts.
                        let late = now.duration_since(next).as_nanos() / period.as_nanos();
                        skipped += late as u64;
                        next += period * (late as u32 + 1);
                    }
                    writes += 1;
                    if mode == "rw" {
                        let mut v = rw.write().unwrap();
                        v.0 = writes;
                        busy_for(hold);
                        v.1 = writes * 2;
                    } else {
                        s.publish(writes, hold).unwrap();
                    }
                }
            }
            (writes, skipped)
        });
        gate.wait();
        epoch.set(Instant::now()).unwrap();
        gate.wait();
        let (writes, skipped) = writer.join().unwrap();
        let rows: Vec<_> = counts.drain(..).map(|h| h.join().unwrap()).collect();
        let elapsed = epoch.get().unwrap().elapsed().as_secs_f64();
        let total = rows.iter().fold((0_u64, 0_u64, 0_u64, 0_u64), |a, b| {
            (a.0 + b.0, a.1 + b.1, a.2 + b.2, a.3 + b.3)
        });
        let min_reads = rows.iter().map(|r| r.0).min().unwrap();
        println!(
            "{{\"mode\":\"{mode}\",\"workload\":\"{workload}\",\"readers\":{readers},\"seconds\":{elapsed},\"reads\":{},\"odd\":{},\"changed\":{},\"fallback\":{},\"min_reader_reads\":{min_reads},\"writes\":{writes},\"skipped_slots\":{skipped}}}",
            total.0, total.1, total.2, total.3
        );
        (writes, skipped, elapsed)
    });
    let final_value = if mode == "rw" {
        *rw.read().unwrap()
    } else {
        s.read(Some(8)).value
    };
    assert_eq!(final_value, (writes, writes * 2));
    black_box((skipped, elapsed));
}
