//! Prints the checked Topic 52 cost substitutions and cut-point oracle.
//!
//! The byte counts and times use hypothetical constants and are model outputs,
//! not host measurements. Cut-point rows model observations after deterministic
//! process exits on a live kernel; they are not power-loss recovery results.

use filesystem_crash_semantics::{
    CutPoint, cow_issued_bytes, expected_live_observation, journal_issued_bytes,
    replacement_latency_ms, sync_log_latency_ms,
};

fn main() {
    let kib = 1024_u128;
    let ordered =
        journal_issued_bytes(1024 * kib, 64 * kib, 8 * kib, false).expect("valid constants");
    let data_journal =
        journal_issued_bytes(1024 * kib, 64 * kib, 8 * kib, true).expect("valid constants");
    let cow_small =
        cow_issued_bytes(4 * kib, 4, 16 * kib, 32 * kib, 4 * kib).expect("valid constants");
    let cow_large =
        cow_issued_bytes(1024 * kib, 4, 16 * kib, 32 * kib, 4 * kib).expect("valid constants");
    let log_ms = sync_log_latency_ms(64 * kib, 500.0, 0.8).expect("valid constants");
    let replace_ms = replacement_latency_ms([0.35, 4.80, 0.06, 0.75]).expect("valid constants");

    println!(
        "model=metadata-journal mode=ordered issued_kib={}",
        ordered / kib
    );
    println!(
        "model=metadata-journal mode=data-journal issued_kib={}",
        data_journal / kib
    );
    println!(
        "model=tree-cow payload_kib=4 issued_kib={}",
        cow_small / kib
    );
    println!(
        "model=tree-cow payload_kib=1024 issued_kib={}",
        cow_large / kib
    );
    println!("model=sync-log log_kib=64 latency_ms={log_ms:.3}");
    println!("model=replace latency_ms={replace_ms:.2}");

    for cut in [
        CutPoint::AfterWrite,
        CutPoint::AfterFileSync,
        CutPoint::AfterRename,
        CutPoint::AfterDirectorySync,
        CutPoint::Complete,
    ] {
        println!(
            "cut={cut:?} observation={:?}",
            expected_live_observation(cut)
        );
    }

    println!("boundary=all byte counts and times are model outputs, not host measurements");
}
