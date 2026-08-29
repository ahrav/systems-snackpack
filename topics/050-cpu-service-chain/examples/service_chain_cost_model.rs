//! Prints the lesson's CPU service-chain accounting values.
//!
//! The hard-coded inputs are teaching values, not host measurements. The
//! helpers expose arithmetic consistency; they do not predict scheduler policy
//! or application latency.

use cpu_service_chain::{
    WakeService, deadline_utilization_sum, fair_share, lock_blocking, response_time,
    smt_aggregate_gain, smt_symmetric_per_thread_slowdown,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let response_ms = response_time(2.0, 0.4, 0.06)?;
    let lock_blocking_us = lock_blocking(60.0, 2_000.0, 0.0, 15.0)?;

    let equal_weight_sum = 1_024.0 + 1_024.0;
    let equal_first = fair_share(1_024.0, equal_weight_sum)?;
    let equal_second = fair_share(1_024.0, equal_weight_sum)?;

    let skewed_weight_sum = 1_024.0 + 110.0;
    let skewed_first = fair_share(1_024.0, skewed_weight_sum)?;
    let skewed_second = fair_share(110.0, skewed_weight_sum)?;

    let smt_gain = smt_aggregate_gain(100.0, 150.0)?;
    let smt_slowdown = smt_symmetric_per_thread_slowdown(100.0, 150.0)?;
    let deadline = deadline_utilization_sum(&[(2.0, 10.0), (3.0, 20.0)])?;
    let wake = WakeService::new(20e-6, 80e-6, 1_500_000.0, 1.5, 2e9)?;

    println!("response time: {response_ms:.3} ms");
    println!("lock blocking: {lock_blocking_us:.0} us");
    println!("equal fair shares: {equal_first:.3}, {equal_second:.3}");
    println!("skewed fair shares: {skewed_first:.9}, {skewed_second:.9}");
    println!(
        "SMT aggregate gain: {smt_gain:.3}x; symmetric per-thread slowdown: {:.1}%",
        smt_slowdown * 100.0
    );
    println!("deadline utilization sum: {deadline:.3}");
    println!(
        "wake service: idle exit {:.0} us + runnable queue {:.0} us + execution {:.0} us = {:.0} us",
        wake.idle_exit_seconds() * 1e6,
        wake.runnable_queue_seconds() * 1e6,
        wake.execution_seconds() * 1e6,
        wake.total_seconds() * 1e6,
    );

    Ok(())
}
