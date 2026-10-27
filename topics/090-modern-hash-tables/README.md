# Modern hash-table engineering

Compare two scalar fixed-capacity tables and Rust `HashMap` with one integer
mixer. The scalar variants share control-byte and payload arrays, stride-one
probing and tombstone rules. The tagged variant checks seven high hash bits
before full equality. The standard map also changes the probing implementation.
These measurements isolate scalar tag overhead and compare whole lookup paths.
They do not measure a custom SIMD implementation.

```bash
cargo test -p modern-hash-tables
cargo build --release -p modern-hash-tables --example lookup
python3 topics/090-modern-hash-tables/scripts/campaign.py \
  --binary target/release/examples/lookup --out /tmp/hash-table-results
python3 topics/090-modern-hash-tables/scripts/demo.py
```

Five unit tests and one doctest must pass. Two differential tests check 128,000
mixed operations and 12,288,000 key lookups against `BTreeMap`. Other tests
cover wraparound collisions, replacement beyond a tombstone, full/all-deleted
termination, same-capacity rebuilding and equal-probe/different-equality work.
The demonstration prints a preserved lookup and an intentional false miss.

Every benchmark query is checked against `BTreeMap` before timing. A checksum
is checked after timing. Setup, deletes, rebuild, oracle work, probe counters
and destruction are excluded. Every timed sample repeats 65,536 queries eight
times. The correctness pass warms the queried table. Hit keys follow a fixed
coprime stride through the numeric key domain, independent of insertion order;
large hits sample 65,536 of 131,072 keys. Misses use keys above the slot count.
Seeded insertion/query shuffles are matched across variants in each block.

Six workloads use 4,096 or 262,144 scalar slots: hits at 50% live load, misses
at 87.5%, and large-table misses after deleting even keys from an 87.5% table,
with or without rebuilding. The latter two have 43.75% live load. Tombstones
leave 87.5% probe occupancy before rebuilding. The standard map reserves the
original live count even for the rebuilt case. Its reported `capacity()` is
usable capacity, not physical slots or bytes; erasure can change that value.
Each custom slot uses 16 payload bytes plus one control byte, excluding Vec
headers and allocator overhead. No process memory or library internal byte
count is inferred from the capacity field.

The runner executes all six permutations of three variants, one fresh process
per sample: six samples per variant/workload, 108 measured processes and 18
warmups per host. Linux pins to the first allowed CPU. macOS has no CPU pinning.
Frequency, thermals, competing work and SMT sibling activity are uncontrolled.
Build with repository Rust 1.93.1, default release optimization and target CPU.
No custom RUSTFLAGS are used.

A descriptive winner must beat both other variants by more than 5% in every
matched block. A pair is a practical tie only if every ratio lies in
[1/1.05, 1.05]. Other comparisons remain unresolved. This is a finite-sample
rule, not a statistical confidence claim or production recommendation.

Use a keyed/adversarially resistant hasher for exposed keys according to the
threat model. This deterministic mixer provides no HashDoS protection. Growth,
erasure latency, rebuild cost, allocation, large/string keys, cold-cache
lookups and concurrent access remain outside this experiment.

See [sources](sources.md) and [results](measurements/results.md). The complete
lesson and inspected visual are retained separately from this compact crate.
