//! Reproduce a read inversion and check read write-back and hypothetical costs.

use quorum_consistency_costs::{phase_ns, publish, read, sets};

fn main() {
    let partial = [1, 0, 0];
    let first = read(&partial, 0b011).unwrap();
    let later = read(&partial, 0b110).unwrap();
    assert_eq!((first, later), (1, 0));
    println!("without write-back: {first} then {later}");
    let mut checked = 0;
    for write_back in sets(3, 2) {
        for query in sets(3, 2) {
            let mut replicas = partial;
            assert!(publish(&mut replicas, write_back, first));
            assert!(read(&replicas, query).unwrap() >= first);
            checked += 1;
        }
    }
    println!("write-back protected {checked}/9 quorum pairs");
    let phase = phase_ns(&[1_000_000, 4_000_000, 20_000_000], 2, 200_000).unwrap();
    println!(
        "hypothetical phase={phase} ns; two equal phases={} ns",
        phase * 2
    );
    println!("correctness model only; no transport timing measured");
}
