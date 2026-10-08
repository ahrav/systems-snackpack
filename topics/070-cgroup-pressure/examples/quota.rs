//! Linux batch probe. Reads its own cgroup; never changes a controller.
use cgroup_pressure::{batch, delta, oracle};
use std::os::unix::fs::MetadataExt;
use std::{
    collections::BTreeMap,
    fs,
    path::Path,
    time::{Duration, Instant},
};

fn counters(path: &Path) -> BTreeMap<String, u64> {
    let mut result = BTreeMap::new();
    for file in [
        "cpu.stat",
        "cpu.pressure",
        "memory.events",
        "memory.pressure",
    ] {
        if let Ok(text) = fs::read_to_string(path.join(file)) {
            for line in text.lines() {
                let words: Vec<_> = line.split_whitespace().collect();
                if words.len() == 2 {
                    if let Ok(value) = words[1].parse() {
                        result.insert(format!("{file}.{}", words[0]), value);
                    }
                } else if let Some(total) = words.iter().find_map(|s| s.strip_prefix("total=")) {
                    result.insert(format!("{file}.{}", words[0]), total.parse().unwrap());
                }
            }
        }
    }
    for key in [
        "cpu.stat.usage_usec",
        "cpu.stat.throttled_usec",
        "cpu.pressure.some",
    ] {
        assert!(
            result.contains_key(key),
            "{key} missing under {}",
            path.display()
        );
    }
    result
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 4, "usage: quota WORKERS JOBS STEPS");
    let workers: usize = args[1].parse().unwrap();
    let jobs: usize = args[2].parse().unwrap();
    let steps: u32 = args[3].parse().unwrap();
    assert!((1..=4).contains(&workers) && jobs <= 4096 && steps <= 1_000_000);
    let membership = fs::read_to_string("/proc/self/cgroup").expect("Linux cgroup v2 required");
    let relative = membership
        .lines()
        .find_map(|s| s.strip_prefix("0::/"))
        .unwrap();
    assert!(!relative.split('/').any(|s| s == ".."));
    let path = Path::new("/sys/fs/cgroup").join(relative);
    let cpu_max = fs::read_to_string(path.join("cpu.max")).unwrap();
    println!("cgroup={}", path.display());
    println!("cpu_max={}", cpu_max.trim());
    let mut ancestor = Some(path.as_path());
    while let Some(p) = ancestor {
        if !p.starts_with("/sys/fs/cgroup") {
            break;
        }
        for file in [
            "cpu.max",
            "cpu.max.burst",
            "cpu.weight",
            "cpuset.cpus.effective",
            "memory.high",
            "memory.max",
            "cgroup.pressure",
        ] {
            if let Ok(value) = fs::read_to_string(p.join(file)) {
                println!("config {} {file} {}", p.display(), value.trim());
            }
        }
        ancestor = p.parent();
    }
    let warm = batch(workers, 16, 1000);
    for (i, value) in warm.iter().enumerate() {
        assert_eq!(*value, oracle((i + 1) as u64, 1000));
    }
    std::thread::sleep(Duration::from_millis(200));
    let identity = fs::metadata(&path).unwrap();
    println!("cgroup_device={}", identity.dev());
    println!("cgroup_inode={}", identity.ino());
    let before = counters(&path);
    let begin = Instant::now();
    let output = batch(workers, jobs, steps);
    let elapsed = begin.elapsed();
    let after = counters(&path);
    let final_identity = fs::metadata(&path).unwrap();
    assert_eq!(
        (identity.dev(), identity.ino()),
        (final_identity.dev(), final_identity.ino())
    );
    assert_eq!(membership, fs::read_to_string("/proc/self/cgroup").unwrap());
    for (i, value) in output.iter().enumerate() {
        assert_eq!(*value, oracle((i + 1) as u64, steps));
    }
    println!("wall_ns={}", elapsed.as_nanos());
    for (key, value) in before {
        let increment = delta(value, *after.get(&key).unwrap()).expect("counter reset");
        println!("delta_{key}={increment}");
    }
    println!(
        "checksum={}",
        output.iter().fold(0_u64, |a, b| a.wrapping_add(*b))
    );
    println!("correct=true");
}

#[cfg(test)]
mod tests {
    use super::counters;
    use std::fs;

    fn cgroup_dir(name: &str, cpu_pressure: Option<&str>) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("quota-{name}-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        fs::write(
            dir.join("cpu.stat"),
            "usage_usec 1500\nuser_usec 1000\nsystem_usec 500\nnr_throttled 2\nthrottled_usec 300\n",
        )
        .unwrap();
        if let Some(text) = cpu_pressure {
            fs::write(dir.join("cpu.pressure"), text).unwrap();
        }
        dir
    }

    #[test]
    fn counters_parse_stat_and_pressure_totals() {
        let dir = cgroup_dir(
            "present",
            Some(
                "some avg10=0.00 avg60=0.00 avg300=0.00 total=123\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=45\n",
            ),
        );
        let result = counters(&dir);
        fs::remove_dir_all(&dir).unwrap();
        assert_eq!(result["cpu.stat.usage_usec"], 1500);
        assert_eq!(result["cpu.stat.throttled_usec"], 300);
        assert_eq!(result["cpu.pressure.some"], 123);
    }

    #[test]
    #[should_panic(expected = "cpu.pressure.some")]
    fn counters_require_cpu_pressure() {
        let dir = cgroup_dir("absent", None);
        let result = std::panic::catch_unwind(|| counters(&dir));
        fs::remove_dir_all(&dir).unwrap();
        if let Err(payload) = result {
            std::panic::resume_unwind(payload);
        }
    }
}
