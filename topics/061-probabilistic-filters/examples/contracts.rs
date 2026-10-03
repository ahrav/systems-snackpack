//! Deterministic empirical counts, not timing or a hash-family theorem.
use topic061_probabilistic_filters::{Bloom, CountMin};

fn main() {
    println!("seed,inserted,occupied,false_positives,absent_probes");
    for seed in 0..16 {
        let mut filter = Bloom::new(95_851, 7, seed);
        for key in 0..10_000 {
            filter.insert(key);
        }
        for key in 0..10_000 {
            assert!(filter.may_contain(key));
        }
        let first = (1_000_000..1_100_000)
            .filter(|&key| filter.may_contain(key))
            .count();
        println!("{seed},10000,{},{first},100000", filter.occupied());
        for key in 10_000..20_000 {
            filter.insert(key);
        }
        for key in 0..20_000 {
            assert!(filter.may_contain(key));
        }
        let second = (1_000_000..1_100_000)
            .filter(|&key| filter.may_contain(key))
            .count();
        assert!(second >= first);
        println!("{seed},20000,{},{second},100000", filter.occupied());
    }
    let mut left = CountMin::new(272, 7, 42);
    let mut right = left.clone();
    let mut serial = left.clone();
    for key in 0..1000 {
        let weight = key % 7 + 1;
        serial.add(key, weight).unwrap();
        if key % 2 == 0 {
            left.add(key, weight).unwrap();
        } else {
            right.add(key, weight).unwrap();
        }
    }
    left.merge(&right).unwrap();
    assert_eq!(left, serial);
    let max_error = (0..1000)
        .map(|key| {
            let exact = key % 7 + 1;
            let estimate = left.estimate(key);
            assert!(estimate >= exact);
            estimate - exact
        })
        .max()
        .unwrap();
    println!(
        "cms_total={} max_error={max_error} merged_equals_serial=true",
        left.total()
    );
    left.merge(&right).unwrap();
    println!(
        "cms_duplicate_snapshot_total={} original_total={}",
        left.total(),
        serial.total()
    );
}
