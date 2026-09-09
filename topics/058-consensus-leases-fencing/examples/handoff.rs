//! Run the paused-owner and joint-membership counterexamples.

use consensus_leases_fencing::{FencedValue, joint_majority, majority};

fn main() {
    let mut sink = FencedValue::default();
    assert!(sink.install(41));
    assert!(sink.write(41, 10));
    let checked_at_ms = 90;
    let expires_at_ms = 100;
    assert!(checked_at_ms < expires_at_ms);
    assert!(sink.install(42));
    assert!(sink.write(42, 20));
    let stale_accepted = sink.write(41, 99);
    assert!(!stale_accepted);
    assert_eq!(sink.value(), 20);
    let old = [0, 1, 2];
    let new = [2, 3, 4];
    let acknowledgers = [0, 1, 2];
    let union = majority(&[0, 1, 2, 3, 4], &acknowledgers);
    let joint = joint_majority(&old, &new, &acknowledgers);
    assert!(union && !joint);
    println!(
        "stale_accepted={stale_accepted} final_value={}",
        sink.value()
    );
    println!("union_majority={union} joint_majority={joint}");
}
