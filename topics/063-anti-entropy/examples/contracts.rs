//! Run the fixed catalog reconciliation scenarios without network or timing.
use std::collections::BTreeMap;
use topic063_anti_entropy::{Version, differing_ranges, exchange, merge, receive, repair_read};

fn main() {
    let old = Version {
        clock: [1, 0, 0],
        value: Some(10),
    };
    let deleted = Version {
        clock: [2, 0, 0],
        value: None,
    };
    let edited = Version {
        clock: [1, 1, 0],
        value: Some(20),
    };
    assert_eq!(merge(&[deleted], &[old]), vec![deleted]);
    assert_eq!(merge(&[], &[old]), vec![old]);
    let mut replicas = [deleted, edited, old].map(|v| BTreeMap::from([(42, vec![v])]));
    for (a, b) in [(0, 1), (0, 1), (1, 2), (2, 0)] {
        exchange(&mut replicas, a, b);
    }
    assert!(replicas.windows(2).all(|pair| pair[0] == pair[1]));
    assert_eq!(replicas[0][&42].len(), 2);
    println!(
        "converged_replicas=3 concurrent_siblings=2 retained_delete_blocks_old=true forgotten_delete_resurrects=true"
    );
    let mut a = BTreeMap::from([(42, vec![deleted]), (43, vec![deleted])]);
    let mut c = BTreeMap::from([(42, vec![old]), (43, vec![old])]);
    repair_read(&mut a, &mut c, 42);
    assert_eq!(a[&42], c[&42]);
    assert_ne!(a[&43], c[&43]);
    receive(&mut c, &a);
    assert_eq!(a, c);
    println!("cold_key_stale_after_read_repair=true cold_key_repaired_after_full_delivery=true");
    let a = vec![vec![old]; 16];
    let mut b = a.clone();
    b[6] = vec![deleted];
    assert_eq!(differing_ranges(&a, &b, 4), vec![1]);
    println!(
        "range_oracle_records=16 changed_records=1 differing_leaf_ranges=1 records_in_selected_range=4"
    );
}
