# Software-cache admission and eviction

Compare FIFO, LRU, persistent frequency admission with LRU, and aged frequency
admission with LRU on identical integer request traces. The cache stores
residency and policy metadata. Equal-size payloads and equal miss costs are
assumed. Each miss completes immediately. Capacity is 128 entries.

```bash
cargo test -p cache-admission
cargo build --release -p cache-admission --example replay
python3 topics/091-cache-admission/scripts/demo.py
python3 topics/091-cache-admission/scripts/campaign.py \
  --binary target/release/examples/replay --out /tmp/cache-policy-results
```

The output directory must be new. Expect four unit tests and one doctest to
pass. The exhaustive test covers 16,384 seven-request traces, five capacities
including zero, four policies, and every prefix: 2,293,760 transition checks
against a timestamp-based BTreeMap oracle. It checks hit decisions, resident
order, and occupancy. Other tests cover saturation, rejected-request counting,
aging after a popularity shift, and invalid keys. The Python campaign uses a
separate timestamp dictionary oracle for full traces and final resident order.

## Exact policy contract

FIFO admits every miss and leaves insertion order unchanged on hits. LRU admits
every miss and moves a hit to the newest end. Both frequency policies use LRU
resident order, count all requests including rejected misses, and admit to a
full cache only when the candidate count exceeds the oldest resident's count.
Ties retain the resident. Available space accepts a candidate immediately.
Counts saturate at 65,535. The aged variant halves all 8,192 counters before
requests 8,193, 16,385, and so on, rounding down. Empty capacity always misses.

The frequency policies demonstrate exact admission with bounded history.
TinyLFU implementations use compact approximate history, and W-TinyLFU includes
additional regions. This experiment measures the stated four implementations.

## Workloads and controls

Each trace has 262,144 requests over at most 8,192 keys:

- `hot`: repeat 64 keys, all fitting after cold misses.
- `scan`: alternate 512 references to 64 hot keys with 512 scan references.
  Scan keys rotate through the other 8,128 keys and eventually repeat.
- `shift`: repeat 128 keys for half the trace, then a disjoint set of 128 keys.
- `cycle`: repeatedly visit 129 keys, one more than capacity.
- `uniform`: fixed xorshift32 stream modulo 8,192, seed `0x12345678`.

Eight cold logical caches are allocated and initialized before the timer.
The trace is read and decoded before timing. Each cache processes the whole
trace once. Timing includes key bounds checks, lookup, ordering changes,
admission, counter increments, and full-array aging. Allocation, file I/O,
oracle work, reporting, and destruction are excluded. Resident trace pages and
initialized state are used. This is single-threaded policy work.

Each workload has one untimed warmup process per policy and eight measured
fresh processes per policy. Four cyclic policy orders followed by their
reversals balance each position and pairwise precedence. There are 160 measured
processes and 20 warmups per host. Rust 1.93.1 uses ordinary release settings.
Linux pins the runner and children to the first allowed CPU. macOS remains
unpinned. Clock rate, thermals, competing work, and SMT siblings are uncontrolled.

A pair has a descriptive timing winner only when all eight matched ratios
exceed a 5% advantage in the same direction. All ratios within [1/1.05, 1.05]
form a practical tie. Other pairs remain unresolved. These are finite-sample
decisions. Deterministic hit counts have no sampling interval for these traces.

On 64-bit targets, each policy allocates two 8-byte link arrays and one 1-byte
presence array over the 8,192-key universe: 139,264 bytes. Frequency policies
add 16,384 counter bytes. These logical backing-array totals exclude vector
headers, allocator rounding, payloads, traces, and process memory. They scale
with the declared key universe. Production maps typically index resident keys
and use compressed history; measure their complete memory separately.

## Interpretation and limits

Compare exact misses and policy CPU separately. A slower policy can reduce
backend work when it avoids expensive misses. The experiment measures neither
backend latency nor concurrent throughput. Hashing, variable sizes, expiry,
invalidation, dirty or pinned objects, in-flight load coalescing, callbacks,
allocator pressure, sharding, and asynchronous maintenance require additional
workloads. Persistent frequency saturation and the aging interval are explicit
parts of the tested policy. Production-library rankings remain unmeasured.

See [LESSON.md](LESSON.md), [SOURCES.md](SOURCES.md), and the retained results.
