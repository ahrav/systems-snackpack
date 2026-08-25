# Cache coherence, false sharing, and cache-line ownership

Two threads can update different fields and still slow each other down. The
processor keeps cached copies coherent at cache-line granularity, not at Rust
field or object granularity. If both write-hot fields occupy one line, each
writer can disturb the other writer's copy. This is **false sharing**: the
program shares a coherence block even though it does not share the logical
values.

## Build the mental model

A cache line is the fixed-size block that a cache tracks for coherence. Both
measured Linux hosts reported 64-byte coherence lines. The focused probe aligns
objects to 128 bytes and gives a split counter a 128-byte stride, then rejects a
publication host that reports any other line size. This makes the packed pair
share one measured line and the split pair occupy separate measured lines.

The word *ownership* is shorthand for permission to write a line without first
obtaining a stronger coherence permission. It is not the `O` state in one named
protocol. Modified, Exclusive, Shared, and Invalid (MESI) is useful vocabulary,
but it is not a portable description of every processor's implementation. The
measured Neoverse V1 core can issue an atomic near its L1 cache or as a far
atomic through its Coherent Hub Interface (CHI). The experiment does not expose
which path each operation used. Line-granular permission also does not mean that
every protocol message carries an entire line.

Coherence and language memory ordering answer different questions. Coherence
keeps cached copies of one location compatible. Rust's `Relaxed` ordering keeps
each `fetch_add` atomic but creates no ordering edge between the two counters.
It does not disable coherence. False sharing also affects disjoint ordinary
writes; this probe deliberately uses atomic read-modify-write operations to
make every update observable and to prevent the compiler from removing work.

## Price a layout decision

First ask how many useful updates one ownership epoch serves. A cached-write
decision model spreads handoff cost over all completed updates:

```text
average_update_cost = local_cost + (handoffs / updates) * handoff_cost
```

`handoffs` and `updates` cover one interval. A hypothetical 1,000 updates with
20 handoffs, 2 nanoseconds of local work, and an 80-nanosecond handoff cost give
`2 + (20 / 1,000) * 80 = 3.6` nanoseconds per update. The result says batching
50 updates per handoff makes the handoff contribute 1.6 nanoseconds per update.
It does not prove that a measured atomic followed that path.

Padding is useful only when avoided sharing costs more than the larger layout:

```text
split_layout_saving
    = (packed_handoffs - split_handoffs) * handoff_cost - footprint_cost
```

In a hypothetical interval, avoiding 90 handoffs at 80 nanoseconds saves 7,200
nanoseconds. If the larger footprint costs the workload 1,000 nanoseconds, the
net modeled saving is 6,200 nanoseconds. `footprint_cost` is a measured or
explicitly modeled cache, translation, or bandwidth cost. It is not the number
of padding bytes. [`average_update_cost_ns`] and [`split_layout_saving_ns`]
evaluate these models.

Both models are first-order decision aids. They omit overlap, retries,
topology-dependent latency, true-sharing serialization, and Arm far-atomic
routing. Linux `perf c2c` sample counts are not ownership-handoff counts and
must not be substituted for `handoffs`.

## Choose the smallest intervention that changes ownership

| Technique | Problem it solves | How it works | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|---|
| Separate hot fields | Two independent writers share one line | Align or pad the fields onto measured separate lines | True sharing of one value | Extra footprint can increase cache and address-translation pressure | A layout intervention removes a measured exact-host slowdown |
| Shard per worker | Many writers update one aggregate | Give each worker private state and reduce later | Immediate global visibility | Reduction work and stale intermediate totals | Reads can tolerate delayed aggregation |
| Batch or combine writes | Ownership changes too often | Perform several useful updates during one acquired epoch | A layout that mixes unrelated owners | Queues add latency and can become hot | The interface permits batching or one combining owner |
| Keep the compact layout | Padding costs more than contention | Accept sharing and preserve density | A proven ownership bottleneck | Tail latency can collapse as writers increase | Updates are rare, mostly read-only, or footprint dominates |

Padding after a type, `#[repr(align(N))]` without a verified stride, and allocator
placement without an offset check do not establish separation. Inspect actual
field addresses and the deployed line size.

## Focused experiment

[`examples/cache_coherence_probe.rs`](examples/cache_coherence_probe.rs) starts
two workers on distinct physical cores in one package. `packed` places two
`AtomicU64` counters eight bytes apart. `padded` places them 128 bytes apart.
Both workers perform the same number of `fetch_add(Relaxed)` operations on
different counters. Three barriers keep affinity setup and thread teardown out
of the timer. The probe validates the final counts, field offsets, and beginning
and ending logical processors.

[`experiment/run_processes.py`](experiment/run_processes.py) launches fresh
processes in four-process ABBA and BAAB blocks. One complete block is one
replication; threads and loop iterations are subsamples. The geometric mean of
block log contrasts is the packed-to-padded ratio. A deterministic percentile
bootstrap describes variation across complete blocks from one host, binary,
CPU placement, and run window. A padded-versus-padded A/A control checks labels
and positions mechanically; it is not a noise floor.

[`experiment/run_host.sh`](experiment/run_host.sh) binds the run to a Git
archive, the authorized target and resolved hostname, the exact binary, the
selected topology, and the observed line size. It retains every attempt, fails
the whole block on any invalid record, and captures the stable
`topic46_increment` symbol from the same binary. See
[`experiment/README.md`](experiment/README.md) for runnable commands and
[`rounds/01.md`](rounds/01.md) for the acceptance contract.

## Keep the evidence boundary explicit

Elapsed time can show that changing only layout changed this fixed workload on
one host. Generated code can show a locked atomic instruction on x86-64 or an
AArch64 atomic lowering. Neither proves a particular cache-to-cache path,
invalidation count, or ownership-handoff count. On both required hosts, `perf
c2c` reported that memory events were unsupported, so this round makes no direct
Performance Monitoring Unit (PMU) traffic claim.

Snoop hit modified (HITM) samples, where available, can locate accesses to a
line held modified elsewhere. They can arise from true or false sharing. They
are sampled access evidence, not a complete transaction count or proof of a
source-level cause. Confirm offsets, writers, topology, and a controlled layout
intervention before changing production structures.

## Selection guide

1. Prove that the writers touch distinct logical values concurrently.
2. Record actual addresses, cache-line size, processor topology, and migrations.
3. Change only placement; keep operations, work, and placement fixed.
4. Use process-level, order-balanced replication and an A/A path check.
5. Inspect the exact binary, then use model-specific PMU evidence when available.
6. Compare saved sharing cost with the measured cost of extra footprint.
7. Remeasure at the production writer count, topology, and data-set size.

Primary sources and their scope boundaries are in [`references.md`](references.md).
Checked-source Linux observations belong under [`measurements/`](measurements/).

[`average_update_cost_ns`]: src/lib.rs
[`split_layout_saving_ns`]: src/lib.rs
