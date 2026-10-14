# Metadata scalability

Compare full snapshot replacement with ordered delta replay for a fixed routing
catalog. Both produce the same complete cache state at a cursor. The authority
uses one dense sequence per mutation within one epoch. This is a teaching
protocol, not the etcd watch protocol.

## Contract

`Cache::apply(from, to, changes)` covers `(from, to]`. It validates length and key
bounds before mutation, rejects missing history, skips a replayed prefix, and
applies deletions. A snapshot replaces the entire namespace, including absent
keys. Older snapshots are rejected. Equal sequence numbers must identify
immutable content from a trusted authority.

The consumer does not expose intermediate states. Concurrent publication,
authority epoch replacement, network behavior, retained-log management, and
durable writes require additional mechanisms.

## Run

From the repository root:

```sh
cargo test -p metadata-scalability
cargo clippy -p metadata-scalability --all-targets -- -D warnings
cargo build --release -p metadata-scalability --example compare
python3 topics/077-metadata-scalability/demo.py
python3 -m unittest topics/077-metadata-scalability/test_run.py
python3 topics/077-metadata-scalability/run.py \
  --binary target/release/examples/compare \
  --out /tmp/metadata-results --source-commit "$(git rev-parse HEAD)"
```

The standalone source archive also runs with `cargo test` and
`cargo build --release --example compare` from its crate directory.

## Workloads and controls

All cases have 65,536 fixed slots. Sparse has 64 scattered updates, dense has
65,536 updates touching every slot, and hot has 262,144 updates on 64 slots.
Puts and deletions alternate between two prepared end states. Six independent
process pairs use alternating method order. A calibration process targets
80 ms per process, with 128 to 1,000,000 iterations. All calibration and raw
samples are retained. A winner requires every paired speed ratio to exceed
1.05; otherwise the result is unresolved. This is a conservative decision rule,
not a statistical confidence interval.

Timing includes cache validation and application. It excludes allocation,
authority writes, history generation, encoding, network, concurrent readers,
and watcher fanout. Data and code are warm after repeated application. The host
is not pinned and frequency is not controlled. These are host/workload results.

The independent `BTreeMap` oracle checks every prefix of 4,096 six-operation
histories. Other tests cover invalid suffix atomicity, gaps, stale snapshots,
deletion replay, empty batches, and sequence limits. The benchmark checks its
own alternating transitions before timing and validates final state afterward.

For planning, count both total object work and work per recipient. A fleet of
1,000 consumers refreshing 65,536 records/s consumes 65,536,000 records/s.
At 64 changed records/s, a broadcast delta stream delivers 64,000 events/s.
These are arithmetic models, not benchmark results. For continuing writes,
catch-up time is `backlog / (apply_rate - arrival_rate)` when apply exceeds
arrival, under a constant-rate model.

See [sources](sources.md) and [measurements](measurements/README.md).
