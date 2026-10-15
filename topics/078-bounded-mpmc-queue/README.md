# Bounded MPMC queue mechanics

Reservation gives a producer exclusive ownership of a slot. Publication makes
its value readable. A later completed push can sit behind an unpublished head.
The Python model reports `pending` for that case; it is a simulator with unbounded
integers, not a concurrent queue or a weak-memory proof.

```sh
python3 topics/078-bounded-mpmc-queue/model.py
cargo test -p bounded-mpmc-queue
python3 -m unittest topics/078-bounded-mpmc-queue/test_run.py
cargo run --release -p bounded-mpmc-queue -- array 4 4 4 100000
cargo run --release -p bounded-mpmc-queue -- mutex 4 4 4 100000
python3 topics/078-bounded-mpmc-queue/run.py target/release/bounded-mpmc-queue results.json
```

The model checks 80,000 operations against an independent deque and all 24
publication permutations of four reservations. Rust checks full rejection,
capacity one and non-power-of-two capacities, repeated reuse, generated sequential
histories, concurrent exact delivery, and per-producer order with one consumer.
Only the library API handles real threads; the lesson introduces no unsafe code.

The mutex baseline enforces its logical capacity explicitly. Both implementations
preserve rejected values and yield after each returned full/empty observation.
The mutex can block on lock acquisition; Crossbeam has its own internal retries.
Their progress mechanisms differ even though both implement bounded FIFO transfer.

Consumers take equal fixed quotas. Every producer submits a disjoint range of
integer IDs. Result vectors are allocated before the ready barrier. Timing starts
before the start barrier and ends after joins; it includes scheduling, transfer,
consumer writes and join bookkeeping. Sorting and exact-ID verification follow
timing. Every measured run fails if an ID is missing, duplicated or out of range.
An external 120-second process timeout bounds a stall during the campaign.

The runner alternates order for six paired process trials in each of four cells:
1P/1C or 4P/4C, capacity 4 or 1,024, 100,000 jobs per producer. One warmup pair per
cell is excluded. A winner requires all six paired elapsed-time ratios to exceed
1.05 in the same direction. Otherwise selection is unresolved. See
[measurements](measurements/README.md) and [sources](sources.md).

These saturated integer transfers do not measure request latency, fairness,
parking channels, payload destruction, failure recovery, or full application
throughput. Stress and sequential oracles do not establish every concurrent
history's linearizability or the library's weak-memory correctness.

Linux replay uses `bash topics/078-bounded-mpmc-queue/linux-run.sh OUTPUT SOURCE_COMMIT`.
OUTPUT must be a new path. SOURCE_COMMIT must resolve to HEAD of a git checkout
whose tracked workspace manifests, toolchain file and topic files match it. The
script clears Cargo rustflags, profile and target environment overrides, records
the effective rustc invocation in `build.txt`, and honors `CARGO_TARGET_DIR`.
It selects eight available physical cores on one socket and runs both variants
inside the same CPU mask. Threads can migrate within that mask. Other host work,
frequency scaling and sibling activity are uncontrolled. Rust is pinned by the
workspace toolchain; dependencies are pinned by the committed lockfile.
