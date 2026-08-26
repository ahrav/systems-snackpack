# Atomics under contention

An atomic update prevents lost writes. It does not let several cores modify one
location in parallel. A shared read-modify-write operation still needs one
serialized modification point. Under contention, throughput depends on how
frequently writers meet at that point and how much failed work they create.

## Separate correctness from scalability

`AtomicU64::fetch_add(Relaxed)` gives one counter a modification order. The
`Relaxed` ordering adds no ordering guarantee for unrelated memory. It does not
disable cache coherence or remove writable-line arbitration.

Rust guarantees that available atomic types are lock-free, not wait-free.
Lock-free means the system keeps making progress. It does not bound one
thread's completion time or guarantee fairness. A compare-and-swap (CAS) loop
can therefore remain correct while one worker repeatedly retries.

The compiler and processor add separate boundaries:

- x86-64 can lower a returned `fetch_add` to `lock xadd` and a CAS loop to
  `lock cmpxchg`.
- AArch64 with the Large System Extensions (LSE) can lower the same operations
  to `ldadd` and `cas` variants.
- A baseline AArch64 target can use a load-exclusive/store-exclusive loop or a
  runtime-dispatch helper.

Inspect the final linked binary. Instruction names do not establish throughput,
cache-line transfer counts, or fairness.

## Choose the representation that matches the contract

| Technique | Solves | Does not solve | Main cost | Choose it when |
|---|---|---|---|---|
| Shared `fetch_add` | Exact increment and returned global order | One-location serialization | Writable-line arbitration | Every event needs immediate exact visibility or a ticket |
| CAS loop | Conditional state transition | Retry amplification or starvation | Failed attempts and recomputation | No direct atomic operation expresses the transition |
| Bounded backoff | Synchronized retry storms | Capacity or fairness | Added wait and tuning | Conflicts are short and bursty |
| Shards | One global write hotspot | Instant exact snapshots | Scan, footprint, and lifecycle | Updates dominate aggregate reads |
| Batches | Per-event global updates | Immediate visibility | Bounded lag and final-flush ownership | The interface accepts a stated error window |
| Queue or parking lock | Compound invariants and wasted spinning | Serialized critical work | Handoff and scheduler delay | Waits can span descheduling or fairness matters |

Padding separates independent values. It cannot reduce true sharing when every
writer updates the same atomic.

## Price the design change

One shared location has a first-order offered-load model:

```text
offered_load = combined_update_rate * serialized_service_time
```

An offered load at or above one means demand meets or exceeds the modeled
service rate. Service time belongs to one exact operation, topology, and load;
it is not a processor-family constant.

For `W` successful CAS updates and `F` failed attempts:

```text
attempts_per_success = (W + F) / W
cas_time ~= W * success_cost + F * failure_cost + backoff_time
```

Measure `F`. Weak CAS can fail spuriously, and one failed attempt need not cost
the same as another.

For `p` balanced shards, `W` total updates, `R` aggregate reads, local-update
cost `L`, and per-shard read cost `S`:

```text
sharded_time ~= (W / p) * L + R * p * S
```

The first term captures parallel update streams. The second names the scan
cost. A concurrent scan still needs a separate snapshot contract.

For `p` workers, `n` events per worker, and batch size `B`:

```text
global_flushes = p * ceil(n / B)
maximum_live_lag = p * (B - 1)
```

Eight workers with 400,000 events each and `B = 256` perform 12,504 global
flushes instead of 3.2 million. Their live total can lag by 2,040 events before
final flushes. Cancellation without cleanup can turn bounded lag into loss.

The functions in [`src/lib.rs`](src/lib.rs) evaluate these arithmetic models.
They do not predict elapsed time.

## Focused experiment

[`examples/atomic_contention.rs`](examples/atomic_contention.rs) compares four
fixed-work treatments:

- `shared`: one relaxed `fetch_add` per logical update;
- `cas`: one successful relaxed CAS plus recorded retries;
- `striped`: one relaxed `fetch_add` per update on each worker's 128-byte slot;
- `batched`: one shared relaxed `fetch_add` per completed batch.

The Linux-only harness pins every worker and the coordinator to distinct
processors. It reports startup, warmup-and-reset, steady-state, and teardown
times separately. The steady timer starts after worker placement, warmup, and
reset. Every process checks placement, final totals, operation counts, and
echoed inputs.

[`experiment/run_processes.py`](experiment/run_processes.py) uses 12 complete
Williams-cycle blocks for the primary comparison. One block of four fresh
processes is one replication. A separate A/A control sends byte-identical
shared runs through labels A and B to exercise labels, paths, and position
balance.

[`experiment/run_host.sh`](experiment/run_host.sh) binds a run to a Git archive,
host identity, topology, toolchain, source hash, binary hash, and linked kernel
symbols. [`experiment/validate_receipts.py`](experiment/validate_receipts.py)
recomputes the retained result. See [`experiment/README.md`](experiment/README.md)
for commands and [`rounds/01.md`](rounds/01.md) for the acceptance contract.

## Keep the evidence boundary explicit

Elapsed time establishes a workload result on one host. Retry counts establish
software attempts. Disassembly establishes emitted instructions. None alone
counts ownership transfers or proves the processor's internal serialization
path.

The checked-source host notes under [`measurements/`](measurements/) record the
final observations and cross-host comparison. Treat differences between those
hosts as exact-host results, not as an Arm-versus-x86 conclusion.

## Selection guide

1. State whether the value is a statistic, ticket, reference count, or compound
   state transition.
2. Choose memory ordering from the relationships with other data.
3. Prefer a direct atomic operation over a CAS loop when it matches the update.
4. Count attempts, not only successful operations.
5. Reduce meetings at one location with shards, batches, or combining when the
   interface permits their read and visibility costs.
6. Measure a parking or queueing lock when waits can span descheduling.
7. Freeze source, linked code, topology, process order, and stopping rules before
   comparing treatments.

Primary sources and their scope boundaries are in [`references.md`](references.md).
