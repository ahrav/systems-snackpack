//! Frozen-work reader-scaling probe and line-oriented oracle interface.
use reader_writer_collapse::{Route, admission, compute};
use std::hint::black_box;
use std::io::{self, BufRead};
use std::sync::{Barrier, Mutex, RwLock};
use std::thread;
use std::time::Instant;

fn pin(cpu: Option<usize>) -> Result<(), String> {
    let Some(cpu) = cpu else {
        return Ok(());
    };
    let tid = std::fs::read_link("/proc/thread-self").map_err(|e| format!("thread id: {e}"))?;
    let tid = tid
        .file_name()
        .ok_or("thread id has no file name")?
        .to_owned();
    let result = std::process::Command::new("taskset")
        .args(["-pc", &cpu.to_string()])
        .arg(tid)
        .output()
        .map_err(|e| format!("taskset: {e}"))?;
    if !result.status.success() {
        return Err(format!("affinity failed: {result:?}"));
    }
    let status = std::fs::read_to_string("/proc/thread-self/status")
        .map_err(|e| format!("thread status: {e}"))?;
    let allowed = status
        .lines()
        .find(|line| line.starts_with("Cpus_allowed_list:"))
        .and_then(|line| line.split_whitespace().last())
        .ok_or("Cpus_allowed_list missing from thread status")?;
    if allowed != cpu.to_string() {
        return Err(format!("affinity read back {allowed}, expected {cpu}"));
    }
    Ok(())
}

fn bench(mode: &str, threads: usize, operations: u64, rounds: u32) {
    let cpus: Vec<usize> = std::env::var("BENCH_CPUS")
        .map(|s| s.split(',').map(|x| x.parse().unwrap()).collect())
        .unwrap_or_default();
    bench_on(mode, threads, operations, rounds, &cpus);
}

fn bench_on(mode: &str, threads: usize, operations: u64, rounds: u32, cpus: &[usize]) {
    assert!(["mutex", "rwlock", "snapshot"].contains(&mode));
    assert!((1..=64).contains(&threads) && operations > 0);
    assert!(cpus.is_empty() || cpus.len() >= threads);
    let mutex = Mutex::new(Route::new(7));
    let rwlock = RwLock::new(Route::new(7));
    let ready = Barrier::new(threads + 1);
    let start = Barrier::new(threads + 1);
    let (elapsed, checksums) = thread::scope(|scope| {
        let mut handles = Vec::new();
        for worker in 0..threads {
            let cpu = cpus.get(worker).copied();
            let (mutex, rwlock, ready, start) = (&mutex, &rwlock, &ready, &start);
            handles.push(scope.spawn(move || {
                // Every worker reaches both barriers; a pinning failure
                // surfaces at join after both barriers complete.
                let pinned = pin(cpu);
                ready.wait();
                start.wait();
                pinned.expect("worker affinity");
                let mut sum = 0_u64;
                for item in 0..operations {
                    let request = item ^ u64::try_from(worker).unwrap();
                    let value = match mode {
                        "mutex" => {
                            let guard = mutex.lock().unwrap();
                            let value = compute(black_box(*guard), request, rounds);
                            drop(guard);
                            value
                        }
                        "rwlock" => {
                            let guard = rwlock.read().unwrap();
                            let value = compute(black_box(*guard), request, rounds);
                            drop(guard);
                            value
                        }
                        "snapshot" => {
                            let saved = { *rwlock.read().unwrap() };
                            compute(black_box(saved), request, rounds)
                        }
                        _ => unreachable!(),
                    };
                    sum = sum.wrapping_add(value);
                }
                black_box(sum)
            }));
        }
        ready.wait();
        let before = Instant::now();
        start.wait();
        let sums: Vec<u64> = handles.into_iter().map(|h| h.join().unwrap()).collect();
        (before.elapsed(), sums)
    });
    for (worker, actual) in checksums.iter().enumerate() {
        let expected = (0..operations).fold(0_u64, |sum, item| {
            sum.wrapping_add(compute(
                Route::new(7),
                item ^ u64::try_from(worker).unwrap(),
                rounds,
            ))
        });
        assert_eq!(*actual, expected, "wrong workload result");
    }
    let sum = checksums.iter().fold(0_u64, |a, b| a.wrapping_add(*b));
    println!(
        "{mode},{threads},{operations},{rounds},{},{sum}",
        elapsed.as_nanos()
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("bench") if args.len() == 6 => bench(
            &args[2],
            args[3].parse().unwrap(),
            args[4].parse().unwrap(),
            args[5].parse().unwrap(),
        ),
        Some("model") => {
            for line in io::stdin().lock().lines() {
                let line = line.unwrap();
                let x: Vec<u64> = line
                    .split_whitespace()
                    .map(|s| s.parse().unwrap())
                    .collect();
                assert_eq!(x.len(), 6);
                let result = admission(x[0] != 0, x[1], x[2], x[3], x[4], x[5]);
                println!("{},{}", result.0, result.1);
            }
        }
        Some("compute") => {
            for line in io::stdin().lock().lines() {
                let line = line.unwrap();
                let x: Vec<u64> = line
                    .split_whitespace()
                    .map(|s| s.parse().unwrap())
                    .collect();
                assert_eq!(x.len(), 3);
                println!(
                    "{}",
                    compute(Route::new(x[0]), x[1], u32::try_from(x[2]).unwrap())
                );
            }
        }
        _ => {
            panic!("usage: reader-writer-collapse bench MODE THREADS OPS ROUNDS | model | compute")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::bench_on;
    use std::sync::mpsc;
    use std::thread;
    use std::time::Duration;

    #[test]
    fn unpinnable_worker_fails_the_run_instead_of_hanging() {
        let (done, observed) = mpsc::channel();
        thread::spawn(move || {
            let outcome = thread::spawn(|| bench_on("rwlock", 2, 1, 0, &[1 << 20, 1 << 20])).join();
            done.send(outcome.is_err()).unwrap();
        });
        let failed = observed
            .recv_timeout(Duration::from_secs(10))
            .expect("bench must terminate when a worker cannot be pinned");
        assert!(failed, "bench must report the pinning failure");
    }
}
