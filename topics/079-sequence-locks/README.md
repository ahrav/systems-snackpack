# Sequence locks and retry economics

This crate compares three coherent reads of `(count, 2 * count)`:

- `seq`: retry until the sequence remains even and unchanged.
- `fallback`: try eight times, then acquire the writer mutex.
- `rw`: copy the same two integers under `std::sync::RwLock`.

All sequence and payload operations are SeqCst. The mutex serializes writers;
checked arithmetic rejects exhaustion before making the sequence odd. With no
wraparound, equal even sequence loads enclose no update in the SC order. Payload
atomics make rejected copies legal. Plain racing loads would invalidate the
implementation even if validation later rejected their values.

Fallback bounds optimistic work, not waiting time or fairness. The retry-only
path can stall behind a descheduled writer. Keep pointers, user callbacks and
fallible computations out of this teaching record. A generic update API needs
an explicit unwind and reclamation contract.

## Run

From the repository root, with Rust 1.93.1 and Python 3.9 or newer:

```sh
cargo test --locked -p sequence-locks
python3 topics/079-sequence-locks/model.py
cargo run --locked --release -p sequence-locks -- fallback held 4 300
python3 topics/079-sequence-locks/run.py --binary target/release/sequence-locks --out results.json
bash topics/079-sequence-locks/linux-run.sh [output-directory]
```

The model enumerates 7,230 sequentially consistent schedules with one reader
and one to four serialized writes. Its oracle is the set of committed pairs
visible during the read interval. It also finds counterexamples when parity or
final validation is removed, and demonstrates wraparound and concurrent writers
without serialization. This model does not verify weaker atomic orderings.
Rust tests check overflow, forced fallback, two writers and all read policies.
Every measured read checks the pair; every process checks its final state.

## Experiment contract

Four readers and one potential writer share a two-u64 record. Each process runs
for a nominal 300 ms, with one synchronized start. The start is stamped after
every worker exists, before the barrier that releases them; the release ramp
from that stamp to the last running worker is part of elapsed time (on the x86
host, median 30 us and worst 4.6 ms over 2,000 trials, under 1.6% of the window).
Elapsed time also includes the final in-flight operations and thread joins; one
operation begun before the boundary may finish afterward. A thread spawn refused
by the OS after earlier workers reached the start barrier stalls the process;
`run.py` kills any process after 20 s and fails the campaign. Each operation
checks the clock. Counts and checksums are thread-local. Timings include
invariant checks and instrumentation.

| Workload | Writer policy |
|---|---|
| `none` | No updates |
| `paced` | One slot every 100 us, short update |
| `held` | One slot every 100 us, at least 20 us busy work while protected |
| `hot` | Continuous closed-loop updates |

Paced writers skip missed slots instead of issuing catch-up bursts. Report
achieved write rate and skipped slots alongside read throughput. `skipped_slots`
counts slots missed before a later write; slots between the last write and the
deadline are unattempted and uncounted, so writes plus skipped slots is at most
the nominal slot count. The hot case
is a joint reader/writer workload; different completed-write counts prevent an
equal-update-rate claim. The held case models a prolonged update, not an actual
scheduler preemption experiment. Spinning consumes CPU; no CPU-efficiency or
tail-latency ranking is inferred from these counters.

Per host: 12 warmups and 72 measured fresh processes. Each workload uses all
six permutations of the three modes, balancing position and pairwise order.
The whole process is restricted to five distinct physical cores on one socket;
threads may migrate within that set. No governor or system-wide tuning changes.
Hosts are measured separately; host differences cannot identify ISA causation.

Report median and min/max across six replicates. A named throughput winner must
exceed each rival by more than 5% in all six paired blocks. Otherwise call the
selection unresolved, not statistical equivalence. This is a declared selection
rule, not a confidence interval. Record writer progress even for a read winner.

See [sources](sources.md) and [measurements](measurements/README.md).
