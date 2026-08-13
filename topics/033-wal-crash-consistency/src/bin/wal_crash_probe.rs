//! Linux-oriented process-crash and group-commit probe.

use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, BufReader, Read, Write};
use std::os::unix::process::ExitStatusExt;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Instant;

use wal_crash_consistency::{encode_frame, recover_prefix, verify_model};

const MAX_PAYLOAD: usize = 1 << 20;

#[derive(Debug)]
struct BenchResult {
    pid: u32,
    io_ns: u128,
    recovery_ns: u128,
    records: usize,
    payload_bytes: usize,
    batch: usize,
    syncs: usize,
    log_bytes: u64,
}

fn durable_empty_file(path: &Path) -> Result<File, String> {
    let file = OpenOptions::new()
        .create_new(true)
        .read(true)
        .write(true)
        .open(path)
        .map_err(|error| format!("create {}: {error}", path.display()))?;
    file.sync_all()
        .map_err(|error| format!("sync empty file {}: {error}", path.display()))?;
    let parent = path
        .parent()
        .ok_or_else(|| format!("path has no parent: {}", path.display()))?;
    File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|error| format!("sync parent {}: {error}", parent.display()))?;
    Ok(file)
}

fn recover_file(path: &Path, required_lsn: u64) -> Result<u64, String> {
    let bytes = fs::read(path).map_err(|error| format!("read {}: {error}", path.display()))?;
    recover_prefix(&bytes, required_lsn)
        .map(|recovery| recovery.valid_lsn())
        .map_err(|error| error.to_string())
}

fn writer_child(path: &Path, cut: &str) -> Result<(), String> {
    let mut file = durable_empty_file(path)?;
    let mut stdout = io::stdout().lock();
    for lsn in 1..=3_u64 {
        let payload = vec![lsn as u8; 128];
        let encoded = encode_frame(lsn, &payload).map_err(|error| error.to_string())?;
        file.write_all(&encoded)
            .map_err(|error| format!("write lsn {lsn}: {error}"))?;
        let after_write = format!("after_write_{lsn}");
        writeln!(stdout, "EVENT,{after_write}").map_err(|error| error.to_string())?;
        stdout.flush().map_err(|error| error.to_string())?;
        wait_at_cut(cut, &after_write)?;

        file.sync_data()
            .map_err(|error| format!("fdatasync lsn {lsn}: {error}"))?;
        let after_sync = format!("after_sync_{lsn}");
        writeln!(stdout, "EVENT,{after_sync}").map_err(|error| error.to_string())?;
        stdout.flush().map_err(|error| error.to_string())?;
        wait_at_cut(cut, &after_sync)?;

        writeln!(stdout, "ACK,{lsn}").map_err(|error| error.to_string())?;
        stdout.flush().map_err(|error| error.to_string())?;
        let after_ack = format!("after_ack_{lsn}");
        writeln!(stdout, "EVENT,{after_ack}").map_err(|error| error.to_string())?;
        stdout.flush().map_err(|error| error.to_string())?;
        wait_at_cut(cut, &after_ack)?;
    }
    Err(format!("cut_not_reached:{cut}"))
}

fn wait_at_cut(requested: &str, current: &str) -> Result<(), String> {
    if requested == current {
        let mut byte = [0_u8; 1];
        io::stdin()
            .read_exact(&mut byte)
            .map_err(|error| format!("failpoint wait: {error}"))?;
    }
    Ok(())
}

fn run_crash_case(directory: &Path, cut: &str) -> Result<(), String> {
    let executable = env::current_exe().map_err(|error| error.to_string())?;
    let path = directory.join(format!("process-crash-{}-{cut}.wal", std::process::id()));
    let mut child = Command::new(executable)
        .arg("writer-child")
        .arg(&path)
        .arg(cut)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("spawn writer: {error}"))?;
    let child_stdout = child
        .stdout
        .take()
        .ok_or_else(|| "missing child stdout".to_owned())?;
    let mut lines = BufReader::new(child_stdout).lines();
    let mut observed_ack = 0_u64;
    let mut reached = false;
    for line in &mut lines {
        let line = line.map_err(|error| format!("read child event: {error}"))?;
        if let Some(value) = line.strip_prefix("ACK,") {
            observed_ack = value
                .parse::<u64>()
                .map_err(|error| format!("parse ack {value}: {error}"))?;
        }
        if line == format!("EVENT,{cut}") {
            reached = true;
            break;
        }
    }
    if !reached {
        let output = child
            .wait_with_output()
            .map_err(|error| error.to_string())?;
        return Err(format!(
            "failpoint_not_reached:{cut}:status={}:stderr={}",
            output.status,
            String::from_utf8_lossy(&output.stderr)
        ));
    }
    // Child::kill sends SIGKILL directly through the kernel, so no PATH
    // lookup can substitute a different sender, and the waited status must
    // name SIGKILL itself: an exit for any other reason would let the
    // receipt claim a SIGKILL case that never happened.
    child
        .kill()
        .map_err(|error| format!("kill writer: {error}"))?;
    let status = child
        .wait()
        .map_err(|error| format!("wait child: {error}"))?;
    const SIGKILL: i32 = 9;
    if status.signal() != Some(SIGKILL) {
        return Err(format!("writer_not_sigkilled:{status}"));
    }
    let recovered_lsn = recover_file(&path, observed_ack)?;
    if recovered_lsn < observed_ack {
        return Err(format!(
            "acknowledged_history_missing:ack={observed_ack}:recovered={recovered_lsn}"
        ));
    }
    println!(
        "PROCESS_CRASH,status=pass,cut={cut},external_ack_lsn={observed_ack},recovered_lsn={recovered_lsn},model=SIGKILL_live_kernel_not_power_loss"
    );
    Ok(())
}

fn process_crash(directory: &Path) -> Result<(), String> {
    fs::create_dir_all(directory)
        .map_err(|error| format!("create directory {}: {error}", directory.display()))?;
    for cut in ["after_write_2", "after_sync_2", "after_ack_2"] {
        run_crash_case(directory, cut)?;
    }
    println!(
        "PROCESS_CRASH_SCOPE,status=pass,kernel_and_filesystem_remained_live=true,kernel_writeback_after_kill=possible,power_loss=false"
    );
    Ok(())
}

fn bench_one(
    path: &Path,
    records: usize,
    payload_bytes: usize,
    batch: usize,
) -> Result<(), String> {
    if records == 0 || batch == 0 || payload_bytes > MAX_PAYLOAD {
        return Err("records and batch must be positive; payload must be at most 1 MiB".to_owned());
    }
    let mut encoded = Vec::with_capacity(records);
    for index in 0..records {
        let lsn = (index + 1) as u64;
        let payload = vec![(lsn as u8).wrapping_mul(17); payload_bytes];
        encoded.push(encode_frame(lsn, &payload).map_err(|error| error.to_string())?);
    }
    let mut file = durable_empty_file(path)?;
    let start = Instant::now();
    let mut syncs = 0_usize;
    for (index, record) in encoded.iter().enumerate() {
        file.write_all(record)
            .map_err(|error| format!("write record {}: {error}", index + 1))?;
        if (index + 1) % batch == 0 || index + 1 == records {
            file.sync_data()
                .map_err(|error| format!("fdatasync record {}: {error}", index + 1))?;
            syncs += 1;
        }
    }
    let io_ns = start.elapsed().as_nanos();
    drop(file);
    let recovery_start = Instant::now();
    let recovered_lsn = recover_file(path, records as u64)?;
    let recovery_ns = recovery_start.elapsed().as_nanos();
    if recovered_lsn != records as u64 {
        return Err(format!(
            "post_benchmark_recovery_failed:expected={records}:actual={recovered_lsn}"
        ));
    }
    let log_bytes = fs::metadata(path)
        .map_err(|error| format!("metadata {}: {error}", path.display()))?
        .len();
    println!(
        "BENCH,pid={},io_ns={io_ns},recovery_ns={recovery_ns},records={records},payload_bytes={payload_bytes},batch={batch},syncs={syncs},log_bytes={log_bytes}",
        std::process::id()
    );
    Ok(())
}

fn parse_bench(line: &str) -> Result<BenchResult, String> {
    let mut result = BenchResult {
        pid: 0,
        io_ns: 0,
        recovery_ns: 0,
        records: 0,
        payload_bytes: 0,
        batch: 0,
        syncs: 0,
        log_bytes: 0,
    };
    for field in line
        .strip_prefix("BENCH,")
        .ok_or_else(|| format!("not a BENCH line: {line}"))?
        .split(',')
    {
        let (key, value) = field
            .split_once('=')
            .ok_or_else(|| format!("bad BENCH field: {field}"))?;
        match key {
            "pid" => result.pid = parse(value, key)?,
            "io_ns" => result.io_ns = parse(value, key)?,
            "recovery_ns" => result.recovery_ns = parse(value, key)?,
            "records" => result.records = parse(value, key)?,
            "payload_bytes" => result.payload_bytes = parse(value, key)?,
            "batch" => result.batch = parse(value, key)?,
            "syncs" => result.syncs = parse(value, key)?,
            "log_bytes" => result.log_bytes = parse(value, key)?,
            _ => return Err(format!("unknown BENCH field: {key}")),
        }
    }
    if result.pid == 0
        || result.io_ns == 0
        || result.records == 0
        || result.batch == 0
        || result.syncs == 0
        || result.log_bytes == 0
    {
        return Err(format!("incomplete BENCH line: {line}"));
    }
    Ok(result)
}

#[allow(clippy::too_many_arguments)]
fn bench_run(
    directory: &Path,
    csv_path: &Path,
    blocks: usize,
    records: usize,
    payload_bytes: usize,
    batch_a: usize,
    batch_b: usize,
    seed: u64,
) -> Result<(), String> {
    if blocks < 2 || !blocks.is_multiple_of(2) {
        return Err("blocks must be an even number of at least two".to_owned());
    }
    fs::create_dir_all(directory)
        .map_err(|error| format!("create directory {}: {error}", directory.display()))?;
    let executable = env::current_exe().map_err(|error| error.to_string())?;
    let hostname = fs::read_to_string("/proc/sys/kernel/hostname")
        .unwrap_or_else(|_| "unknown".to_owned())
        .trim()
        .to_owned();
    let mut csv = File::create(csv_path)
        .map_err(|error| format!("create CSV {}: {error}", csv_path.display()))?;
    writeln!(
        csv,
        "host,block,period,template,label,batch,pid,io_ns,process_ns,outside_timed_ns,recovery_ns,records,payload_bytes,syncs,log_bytes,path"
    )
    .map_err(|error| error.to_string())?;
    let mut block_log_ratios = Vec::with_capacity(blocks);
    let rotate = (seed as usize) % blocks;

    for block_index in 0..blocks {
        let baab = (block_index + rotate).is_multiple_of(2);
        let template = if baab { "BAAB" } else { "ABBA" };
        let labels = if baab {
            ['B', 'A', 'A', 'B']
        } else {
            ['A', 'B', 'B', 'A']
        };
        let mut a_logs = Vec::with_capacity(2);
        let mut b_logs = Vec::with_capacity(2);
        for (period_index, label) in labels.iter().copied().enumerate() {
            let batch = if label == 'A' { batch_a } else { batch_b };
            let path = directory.join(format!(
                "bench-{}-b{:02}-p{}-{label}.wal",
                std::process::id(),
                block_index + 1,
                period_index + 1
            ));
            let process_start = Instant::now();
            let output = Command::new(&executable)
                .arg("bench-one")
                .arg(&path)
                .arg(records.to_string())
                .arg(payload_bytes.to_string())
                .arg(batch.to_string())
                .output()
                .map_err(|error| format!("spawn bench-one: {error}"))?;
            let process_ns = process_start.elapsed().as_nanos();
            if !output.status.success() {
                return Err(format!(
                    "bench-one failed:block={}:period={}:status={}:stderr={}",
                    block_index + 1,
                    period_index + 1,
                    output.status,
                    String::from_utf8_lossy(&output.stderr)
                ));
            }
            let stdout = String::from_utf8(output.stdout)
                .map_err(|error| format!("bench-one stdout not UTF-8: {error}"))?;
            let result = parse_bench(stdout.trim())?;
            if result.records != records
                || result.payload_bytes != payload_bytes
                || result.batch != batch
            {
                return Err(format!("bench-one settings mismatch:{result:?}"));
            }
            let outside_timed_ns = process_ns.saturating_sub(result.io_ns);
            writeln!(
                csv,
                "{hostname},{},{},{template},{label},{},{},{},{},{},{},{},{},{},{},{}",
                block_index + 1,
                period_index + 1,
                result.batch,
                result.pid,
                result.io_ns,
                process_ns,
                outside_timed_ns,
                result.recovery_ns,
                result.records,
                result.payload_bytes,
                result.syncs,
                result.log_bytes,
                path.display()
            )
            .map_err(|error| error.to_string())?;
            let log_time = (result.io_ns as f64).ln();
            if label == 'A' {
                a_logs.push(log_time);
            } else {
                b_logs.push(log_time);
            }
        }
        let mean_a = a_logs.iter().sum::<f64>() / a_logs.len() as f64;
        let mean_b = b_logs.iter().sum::<f64>() / b_logs.len() as f64;
        block_log_ratios.push(mean_b - mean_a);
    }
    csv.sync_all()
        .map_err(|error| format!("sync CSV {}: {error}", csv_path.display()))?;
    let n = block_log_ratios.len() as f64;
    let mean = block_log_ratios.iter().sum::<f64>() / n;
    let sample_sd = (block_log_ratios
        .iter()
        .map(|value| (value - mean).powi(2))
        .sum::<f64>()
        / (n - 1.0))
        .sqrt();
    println!(
        "RUN,status=pass,host={hostname},blocks={blocks},fresh_process_runs={},templates_abba={},templates_baab={},seed={seed},records={records},payload_bytes={payload_bytes},batch_a={batch_a},batch_b={batch_b},geomean_ratio_b_over_a={:.6},block_log_ratio_sd={:.6},approx_sd_percent={:.3},timed_region=write_plus_fdatasync_only,process_time=spawn_through_exit,csv={}",
        blocks * 4,
        blocks / 2,
        blocks / 2,
        mean.exp(),
        sample_sd,
        (sample_sd.exp() - 1.0) * 100.0,
        csv_path.display()
    );
    Ok(())
}

fn parse<T: std::str::FromStr>(value: &str, name: &str) -> Result<T, String>
where
    T::Err: std::fmt::Display,
{
    value
        .parse::<T>()
        .map_err(|error| format!("parse {name}={value}: {error}"))
}

fn usage() -> &'static str {
    "usage:\n  wal-crash-probe model\n  wal-crash-probe process-crash DIR\n  wal-crash-probe writer-child PATH CUT\n  wal-crash-probe bench-one PATH RECORDS PAYLOAD_BYTES BATCH\n  wal-crash-probe bench-run DIR CSV BLOCKS RECORDS PAYLOAD_BYTES BATCH_A BATCH_B SEED"
}

fn real_main() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("model") if args.len() == 2 => {
            println!("{}", verify_model().map_err(|error| error.to_string())?);
            Ok(())
        }
        Some("process-crash") if args.len() == 3 => process_crash(Path::new(&args[2])),
        Some("writer-child") if args.len() == 4 => writer_child(Path::new(&args[2]), &args[3]),
        Some("bench-one") if args.len() == 6 => bench_one(
            Path::new(&args[2]),
            parse(&args[3], "records")?,
            parse(&args[4], "payload_bytes")?,
            parse(&args[5], "batch")?,
        ),
        Some("bench-run") if args.len() == 10 => bench_run(
            Path::new(&args[2]),
            Path::new(&args[3]),
            parse(&args[4], "blocks")?,
            parse(&args[5], "records")?,
            parse(&args[6], "payload_bytes")?,
            parse(&args[7], "batch_a")?,
            parse(&args[8], "batch_b")?,
            parse(&args[9], "seed")?,
        ),
        _ => Err(usage().to_owned()),
    }
}

fn main() {
    if let Err(error) = real_main() {
        eprintln!("ERROR,{error}");
        std::process::exit(1);
    }
}
