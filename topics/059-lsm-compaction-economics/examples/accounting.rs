//! Deterministic version-retention and transfer-accounting example.
use lsm_compaction_economics::{Job, Version, compact, next_debt, read};
fn main() {
    let versions = vec![
        Version {
            sequence: 10,
            value: Some(100),
        },
        Version {
            sequence: 20,
            value: Some(120),
        },
        Version {
            sequence: 30,
            value: None,
        },
    ];
    let pinned = compact(versions.clone(), 15, false).unwrap();
    let guarded = compact(versions.clone(), 30, true).unwrap();
    let reclaimed = compact(versions, 30, false).unwrap();
    assert_eq!(read(&pinned, 15), Some(100));
    const MIB: u64 = 1 << 20;
    let transfer = Job {
        incoming: 64 * MIB,
        overlap: 256 * MIB,
        output: 288 * MIB,
    }
    .transfer_bytes()
    .unwrap();
    let debt = next_debt(400 * MIB, 10 * MIB, 8, 60 * MIB).unwrap();
    println!(
        "pinned={} guarded={} reclaimed={}",
        pinned.len(),
        guarded.len(),
        reclaimed.len()
    );
    println!("transfer_mib={} debt_mib={}", transfer / MIB, debt / MIB);
}
