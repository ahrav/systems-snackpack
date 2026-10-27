//! One fresh-process lookup sample with an ordered-tree oracle.
use modern_hash_tables::{Table, mix};
use std::collections::{BTreeMap, HashMap};
use std::hash::{BuildHasherDefault, Hasher};
use std::hint::black_box;
use std::time::Instant;

#[derive(Default)]
struct IntegerHasher(u64);
impl Hasher for IntegerHasher {
    fn write(&mut self, _: &[u8]) {
        panic!("only u64 keys are admitted");
    }
    fn write_u64(&mut self, k: u64) {
        self.0 = mix(k);
    }
    fn finish(&self) -> u64 {
        self.0
    }
}

trait Lookup {
    fn lookup(&self, key: u64) -> Option<u64>;
}
impl<const F: bool> Lookup for Table<F> {
    fn lookup(&self, key: u64) -> Option<u64> {
        self.get(key)
    }
}
impl Lookup for HashMap<u64, u64, BuildHasherDefault<IntegerHasher>> {
    fn lookup(&self, key: u64) -> Option<u64> {
        self.get(&key).copied()
    }
}

fn shuffle(keys: &mut [u64], mut seed: u64) {
    for i in (1..keys.len()).rev() {
        seed = mix(seed.wrapping_add(0x9e3779b97f4a7c15));
        keys.swap(i, (seed % (i + 1) as u64) as usize);
    }
}

fn measure<T: Lookup>(t: &T, queries: &[u64], oracle: &BTreeMap<u64, u64>) -> (u128, u64) {
    for &k in queries {
        assert_eq!(t.lookup(k), oracle.get(&k).copied());
    }
    let expected: u64 = queries
        .iter()
        .map(|k| oracle.get(k).copied().unwrap_or(0))
        .fold(0, u64::wrapping_add)
        .wrapping_mul(8);
    let start = Instant::now();
    let mut checksum = 0_u64;
    for _ in 0..8 {
        for &key in black_box(queries) {
            checksum = checksum.wrapping_add(black_box(t).lookup(black_box(key)).unwrap_or(0));
        }
    }
    black_box(checksum);
    let elapsed = start.elapsed().as_nanos();
    assert_eq!(checksum, expected);
    (elapsed, checksum)
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 4, "lookup VARIANT WORKLOAD SEED");
    let variant = args[1].as_str();
    let workload = args[2].as_str();
    let seed: u64 = args[3].parse().unwrap();
    let (slots, high, hit, deleted, rebuilt) = match workload {
        "small_hit50" => (4096, false, true, false, false),
        "small_miss87" => (4096, true, false, false, false),
        "large_hit50" => (262144, false, true, false, false),
        "large_miss87" => (262144, true, false, false, false),
        "large_deleted_miss" => (262144, true, false, true, false),
        "large_rebuilt_miss" => (262144, true, false, true, true),
        _ => panic!("unknown workload"),
    };
    let n = if high { slots * 7 / 8 } else { slots / 2 };
    let mut keys: Vec<u64> = (0..n as u64).collect();
    shuffle(&mut keys, seed);
    let mut oracle = BTreeMap::new();
    for &k in &keys {
        oracle.insert(k, mix(k).wrapping_add(1));
    }
    if deleted {
        oracle.retain(|&k, _| k % 2 == 1);
    }
    let mut queries: Vec<u64> = (0..65536)
        .map(|i| {
            if hit {
                ((i * 104729) % n) as u64
            } else {
                slots as u64 + i as u64
            }
        })
        .collect();
    shuffle(&mut queries, seed.wrapping_add(1));
    let (elapsed, checksum, capacity, tombstones, probes, equalities) = match variant {
        "plain" => run_custom::<false>(&keys, &queries, &oracle, slots, deleted, rebuilt),
        "tagged" => run_custom::<true>(&keys, &queries, &oracle, slots, deleted, rebuilt),
        "std" => {
            let mut t =
                HashMap::<_, _, BuildHasherDefault<IntegerHasher>>::with_capacity_and_hasher(
                    n,
                    Default::default(),
                );
            for &k in &keys {
                t.insert(k, mix(k).wrapping_add(1));
            }
            if deleted {
                for &k in &keys {
                    if k % 2 == 0 {
                        t.remove(&k);
                    }
                }
            }
            if rebuilt {
                let mut fresh = HashMap::with_capacity_and_hasher(n, Default::default());
                for (&k, &v) in &t {
                    fresh.insert(k, v);
                }
                t = fresh;
            }
            let (ns, sum) = measure(&t, &queries, &oracle);
            (
                ns,
                sum,
                t.capacity(),
                String::from("NA"),
                String::from("NA"),
                String::from("NA"),
            )
        }
        _ => panic!("unknown variant"),
    };
    println!(
        "{variant},{workload},{seed},{},{capacity},{tombstones},{},{elapsed},{checksum},{probes},{equalities}",
        oracle.len(),
        queries.len() * 8
    );
}

fn run_custom<const F: bool>(
    keys: &[u64],
    queries: &[u64],
    oracle: &BTreeMap<u64, u64>,
    slots: usize,
    deleted: bool,
    rebuilt: bool,
) -> (u128, u64, usize, String, String, String) {
    let mut t = Table::<F>::new(slots);
    for &k in keys {
        t.insert(k, mix(k).wrapping_add(1)).unwrap();
    }
    if deleted {
        for &k in keys {
            if k % 2 == 0 {
                t.remove(k);
            }
        }
    }
    if rebuilt {
        t.rebuild();
    }
    let (ns, sum) = measure(&t, queries, oracle);
    let mut probes = 0_u64;
    let mut equalities = 0_u64;
    for &k in queries {
        let s = t.stats(k);
        probes += s.probes as u64;
        equalities += s.equalities as u64;
    }
    (
        ns,
        sum,
        slots,
        t.occupancy().1.to_string(),
        probes.to_string(),
        equalities.to_string(),
    )
}
