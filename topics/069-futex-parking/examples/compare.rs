//! One candidate in one independent process. See scripts/run.py for the balanced campaign.
#[cfg(all(
    target_os = "linux",
    target_pointer_width = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
))]
fn main() {
    let a: Vec<_> = std::env::args().collect();
    assert_eq!(
        a.len(),
        6,
        "compare POLICY THREADS ITERATIONS WORK SLEEP_US"
    );
    let (threads, n, work, sleep) = (
        a[2].parse().unwrap(),
        a[3].parse().unwrap(),
        a[4].parse().unwrap(),
        a[5].parse().unwrap(),
    );
    let _ = futex_parking::linux::run(&a[1], threads, 20, work, sleep);
    let r = futex_parking::linux::run(&a[1], threads, n, work, sleep);
    println!(
        "{{\"policy\":\"{}\",\"wall_ns\":{},\"cpu_ns\":{},\"operations\":{},\"waits\":{},\"again\":{},\"wakes\":{},\"woken\":{},\"checksum\":{}}}",
        a[1], r.wall_ns, r.cpu_ns, r.operations, r.waits, r.again, r.wakes, r.woken, r.checksum
    );
}
#[cfg(not(all(
    target_os = "linux",
    target_pointer_width = "64",
    any(target_arch = "aarch64", target_arch = "x86_64")
)))]
fn main() {
    eprintln!("This futex experiment requires Linux x86-64 or AArch64.");
    std::process::exit(2);
}
