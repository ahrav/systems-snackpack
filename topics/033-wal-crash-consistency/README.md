# WAL, durability, and crash consistency

A successful write is not necessarily durable. It may exist only in process,
kernel, controller, or device cache. A write-ahead log (WAL) makes recovery
possible by recording an ordered description of each change before the system
acknowledges that change as committed.

This artifact models the byte-level recovery rule and measures one narrow
batching tradeoff. It is not a database implementation or a power-cut test.

## One running example

A transfer debits account A and credits account B. The system appends records
with log sequence numbers (LSNs) 1 and 2. An LSN names an ordered log position.
It acknowledges LSN 2 only after a successful durability barrier covers both
records.

Recovery accepts the longest contiguous sequence that has the right format,
generation, length, LSN, and CRC-32C checksum. CRC-32C is the Castagnoli cyclic
redundancy check; it detects accidental byte changes but cannot repair them.
Damage before the externally recorded commit LSN fails closed. Damage after it
may be discarded as an uncommitted tail.

```text
append record 1 -> append record 2 -> fdatasync -> publish durable_lsn=2 -> ACK
```

`fdatasync` asks Linux to synchronize file data and the metadata needed to
retrieve it. Correctness still depends on every lower storage layer honoring
the flush contract.

## The ordering invariants

For an inserted, written, and durable WAL frontier:

```text
inserted_lsn >= written_lsn >= durable_lsn
```

A transaction may be acknowledged only when its commit record ends at or
before `durable_lsn`. A dirty data page may reach storage only after WAL through
that page's LSN is durable. These rules prevent data from naming history that
recovery cannot replay.

## Technique boundaries

| Technique | Solves | Does not solve | Main catch |
| --- | --- | --- | --- |
| Synchronous commit | Bounds acknowledged loss to the storage contract | Corruption or a lying device cache | Every commit observes barrier latency |
| Group commit | Shares one barrier across several ready commits | Fewer WAL bytes or zero latency | Waiters need an exact durable-LSN watermark |
| Asynchronous commit | Removes a barrier from foreground latency | Durability at acknowledgement | A clean-looking success may disappear after a crash |
| Full-page image | Repairs a torn data page during redo | WAL corruption or ordering | More WAL, especially after checkpoints |
| Record checksum | Finds a damaged or incomplete WAL record | Repair, persistence, or authenticity | It must cover identity, length, order, and payload |
| Page checksum | Detects stored page damage and misdirected writes | Reconstructing the page | Repair needs WAL, a replica, or another copy |

## Cost model

Let `s` be the elapsed time of one durability barrier, `g` the commits covered
by it, and `lambda` the arrival rate of ready commits. The flush-limited
throughput ceiling is approximately:

```text
throughput <= g / s
utilization rho = lambda * s / g < 1
```

Batching helps when commits overlap. A deliberate collection delay can raise
`g`, but at low load it becomes pure latency. Measure commits per WAL sync and
tail latency rather than assuming a fixed delay is useful.

Let `P` be a page size, `d_i` the pages transaction `i` would force at commit,
`w_i` its WAL bytes, and `Q` the later data-page writebacks after repeated
updates coalesce. A simplified byte comparison is:

```text
force-data bytes ~= P * sum(d_i)
WAL/no-force bytes ~= sum(w_i) + P * Q
```

WAL wins on byte volume when avoided repeated page writes exceed WAL bytes. It
can still win on foreground latency when the byte inequality is false because
commits share one mostly sequential log barrier. Large bulk rewrites are a
common counterexample to “WAL is always cheaper.”

## Failure boundaries

- `write` completion is not a durability promise.
- `fdatasync` failure poisons the attempted durability generation. Do not
  release waiters using an optimistic frontier.
- A `SIGKILL` experiment keeps the kernel and filesystem alive. Later writeback
  remains possible, so it is process-crash evidence, not power-loss evidence.
- A checksum is integrity evidence, not a commit marker or ordering barrier.
- A valid record checksum cannot prove that a separate commit witness was
  persisted first or last.
- Full-page images repair torn data pages; they do not make WAL records atomic.
- A segment boundary is file-management granularity, not commit durability
  granularity. Records and durable LSNs may cross it.
- Frequent checkpoints shorten redo but can increase full-page-image traffic
  and dirty-page write pressure.

## Run locally

Build and run the deterministic model:

```bash
cargo run --locked --release --package topic-033-wal-crash-consistency \
  --bin wal-crash-probe -- model
```

On Linux, put disposable WAL files on a real filesystem rather than `/tmp` if
`/tmp` is a memory-backed `tmpfs`:

```bash
scratch=/var/tmp/topic33-local-$USER
mkdir -p "$scratch"

target/release/wal-crash-probe process-crash "$scratch/crash"
target/release/wal-crash-probe bench-run \
  "$scratch/bench" "$scratch/results.csv" 8 128 256 1 8 330033
```

The benchmark uses eight complete order-balanced blocks, 32 fresh child
processes, and two observations per treatment inside each block. Treatment A
syncs every record. Treatment B syncs each group of eight. The timed region is
record writes plus `fdatasync`; process spawn, setup, and recovery are recorded
separately. The result is a host-and-window-specific batching comparison, not a
storage-family or instruction-set claim.

The local build smoke check on 2026-08-12 used this exact command on the
workspace's macOS Arm host with Rust 1.93.1. It completed eight blocks and 32
fresh processes. The observed B/A ratio was 0.135487 with block-log-ratio
standard deviation 0.157584. This local result checks the runner and validator;
it is not retained Linux evidence and does not test power loss.

See [`rounds/01.md`](rounds/01.md) for the acceptance contract,
[`measurements/README.md`](measurements/README.md) for promotion rules, and
[`references.md`](references.md) for primary sources.
