# Topic 11: Cycle-accurate measurement

Cycle-accurate measurement starts by naming the quantity. Architectural
timestamp counters measure reference ticks. Performance monitoring unit (PMU)
events measure scoped hardware events. Monotonic clocks measure elapsed time in
an operating-system clock domain.

## Measurement contract

Every result records five independent properties:

| Property | Question |
| --- | --- |
| Quantity | Reference ticks, elapsed nanoseconds, core cycles, or instructions? |
| Boundary | Instruction completion, load completion, or store visibility? |
| Conversion | Which frequency or fixed-point parameters map ticks to time? |
| Scope | Are values comparable across CPUs, sockets, guests, or hosts? |
| Perturbation | How much work comes from reads, fences, loops, and the harness? |

The Linux benchmark compares an ordered architectural reference counter with
`CLOCK_MONOTONIC_RAW`. It does not read a PMU cycle event. The x86-64 path
requires TSC, RDTSCP, and invariant-TSC feature evidence. Every endpoint uses
`RDTSCP; CPUID`: RDTSCP waits for earlier instruction execution and load
visibility, while the following serializing CPUID prevents later work from
crossing the endpoint. This is not a prior-store visibility boundary. The read
also captures `TSC_AUX`; the harness rejects an endpoint pair when it changes
and independently checks `sched_getcpu`. Neither check detects every virtual
machine migration.

When CPUID leaf `0x15` lacks usable ratio or crystal-frequency fields, the
benchmark derives frequency from the median of ten 100 ms comparisons with
`CLOCK_MONOTONIC_RAW`, five in each nesting order. The AArch64 path tests
`CNTVCT_EL0` access in a child before the parent executes it, brackets the read
with `ISB`, then reads `CNTFRQ_EL0` for the scale. These are deliberately strong
instruction boundaries; their fixed cost is part of the batching experiment.

## Cost model

For timer `j` and batch size `n`:

```text
M_j(n) = fixed_bracket_j + n * target + loop_j(n) + quantization_j(n) + disturbance_j
```

The experiment uses batch sizes 1, 16, 256, and 4096. A converging per-operation
estimate supports the fixed-cost model. It does not isolate the recurrence's
instruction latency.

For a defensible upper bound `q` on each endpoint's timestamp error and relative
quantization budget `e`, a conservative minimum batch duration is:

```text
batch_duration >= 2q / e
```

[`minimum_batch_duration`](src/lib.rs) computes the rounded-up bound with `e`
in parts per million. The probe's minimum positive adjacent-read delta is
precision evidence, not an upper error bound. The summarizer applies a separate
empirical guard: every 4096-operation process median must reach 200 times that
observed delta. Passing this guard does not prove a 1% timestamp-error bound.

## Fixed-point conversion

The library tests a generic fixed-point map, not a complete perf mmap-page
reader. Convert both endpoints with one coherent parameter snapshot, then
subtract. Scaling an already-subtracted delta loses the endpoints' distinct
rounding phases. A common time origin cancels.

The rounding test uses `start=1`, `end=2`, `mult=3`, and `shift=1`:

```text
scale(end) - scale(start) = floor(6 / 2) - floor(3 / 2) = 2
scale(end - start)        = floor(3 / 2) = 1
```

The library verifies this case and rejects backward or overflowing intervals.
Linux perf has separate contracts. `cap_user_time` supplies a delta used to
update enabled/running time. `cap_user_time_zero` supplies the `time_zero`
origin for an absolute timestamp. `cap_user_time_short` requires reconstructing
the full cycle value with `time_cycles` and `time_mask` before scaling. A real
reader must snapshot those fields under an unchanged even metadata sequence.

## Experiment boundary

The recurrence forms one loop-carried dependency chain. It measures a
latency-shaped workload plus loop effects. Independent chains would measure
throughput and answer a different question.

Each recorded host run uses 12 fresh CPU-0-pinned processes. Six processes run
the architectural counter first; six run the monotonic clock first. Each
process retains all 500 counter-tick and clock-nanosecond samples at every batch
size. It records each median doubled, as the exact sum of the two middle values,
so an even sample count loses no half-unit. Per-operation decimals derive from
those integer fields. The process is the replication unit. Batch size amortizes
the fixed timer brackets. Inner samples expose the within-process distribution
but are not independent replications.

Counter and clock probes fail when their start and end CPU identities differ,
when values move backward, or when no read advances. A timed sample is rejected
when its CPU identity changes or its timer moves backward; the summarizer
requires zero rejections. Setup, warmup, calibration, and process launch remain
outside the per-batch interval.

The summarizer validates the full log against three ABBA order blocks. It also
checks unique process IDs, identical final recurrence checksums, raw sample
counts, raw-derived minima and doubled medians, and per-operation fields. One
symbol-bounded linked-code gate matches the full selected counter bracket inside
`read_counter`. A separate symbol-bounded gate checks that `dependent_chain`
contains a multiplication.

The summarizer converts each process's median ticks per operation with that
process's reported counter frequency. These values are derived time estimates,
not PMU cycle counts.

## Failure boundaries

- A TSC or `CNTVCT_EL0` delta is a reference-tick count, not a core-cycle count.
- Invariant TSC describes rate behavior. It does not prove cross-socket phase
  alignment or safe comparison after virtual-machine migration.
- `CNTFRQ_EL0` defines a scale. It does not prove the counter updates at every
  numerical unit.
- CPU fences do not replace compiler ordering. Perf metadata sequence counters
  solve a third, separate consistency problem.
- A multiplexed PMU count estimates a long aggregate. It cannot reconstruct an
  uncounted short interval.
- One-shot subtraction exposes fixed bracket cost. Independent empty-harness
  minima do not provide an exact correction.
- Host results describe one binary, workload, kernel, and machine. They do not
  rank an instruction-set architecture or processor vendor.

## Recorded result

Candidate `4b00356` is retained as superseded evidence. Its Arm record used the
intended `ISB; MRS CNTVCT_EL0; ISB` boundary, but its AMD path relied on an
`MFENCE; RDTSC; MFENCE` instruction-ordering claim that the cited AMD manual
does not provide. Its measurements are not the final cross-host pair. Read the
[supersession note](measurements/superseded-4b00356.md) before using that raw
record. The corrected exact-source measurements are recorded after both hosts
pass the revised bracket, correctness, code-generation, and replication gates.

## Run

Check portable arithmetic and workload contracts:

```bash
cargo run -p systems-snackpack-topic-011 --example check_contracts
cargo bench -p systems-snackpack-topic-011 --bench cycle_probe -- --verify
```

On Linux, probe the counter and run one process:

```bash
taskset -c 0 cargo bench -p systems-snackpack-topic-011 --bench cycle_probe -- --probe
taskset -c 0 cargo bench -p systems-snackpack-topic-011 --bench cycle_probe -- raw-first 500
```

Create the source archive and run the exact-source harness from the repository
root:

```bash
git archive --format=tar HEAD Cargo.toml Cargo.lock rust-toolchain.toml \
  topics/011-cycle-accurate-measurement | gzip -9 \
  > /tmp/systems-snackpack-topic-011-source.tar.gz
topic11_source_sha=$(sha256sum \
  /tmp/systems-snackpack-topic-011-source.tar.gz | cut -d ' ' -f 1)
SOURCE_ARCHIVE=/tmp/systems-snackpack-topic-011-source.tar.gz \
  topics/011-cycle-accurate-measurement/experiment/run_processes.sh \
  /tmp/systems-snackpack-topic-011 local "$(git rev-parse HEAD)" \
  "$topic11_source_sha"
```

[`experiment/run_processes.sh`](experiment/run_processes.sh) requires
`SOURCE_ARCHIVE` to name an absolute gzip-compressed Git archive. It verifies
the SHA-256 and embedded commit, extracts a scratch tree, and builds only that
tree. It removes the scratch tree on exit. Before building, it clears
`CARGO_ENCODED_RUSTFLAGS`, `RUSTC_WRAPPER`, and `RUSTC_WORKSPACE_WRAPPER`, then
sets the recorded native `RUSTFLAGS`. The harness runs workspace gates, selects
the Cargo-produced benchmark from JSON, executes the 12-process design,
validates the log, and captures code generation.

Read [Round 1](rounds/01.md), the [measurement boundary](measurements/README.md),
the [recorded result](measurements/2026-07-21-cross-host.md), and the
[primary sources](references.md) before interpreting a result.
