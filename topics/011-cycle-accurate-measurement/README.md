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
requires TSC and invariant TSC feature evidence and identifies the vendor. It
uses `MFENCE; RDTSC; MFENCE` on AMD and `LFENCE; RDTSC; LFENCE` on Intel. When
CPUID leaf `0x15` lacks usable ratio or crystal-frequency fields, the benchmark
derives frequency from the median of ten 100 ms comparisons with
`CLOCK_MONOTONIC_RAW`, five in each nesting order. The AArch64 path tests
`CNTVCT_EL0` access in a child before the parent executes it, brackets the read
with `ISB`, then reads `CNTFRQ_EL0` for the scale.

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

Linux perf exposes `time_mult`, `time_shift`, and `time_offset`. Convert both
absolute counter endpoints with one coherent parameter snapshot, then subtract.
Scaling an already-subtracted delta loses the fixed-point rounding phase.

The rounding test uses `start=1`, `end=2`, `mult=3`, `shift=1`, and `offset=50`:

```text
absolute(end) - absolute(start) = 53 - 51 = 2
scale(end - start)              = floor(3 / 2) = 1
```

The library verifies this case and rejects backward or overflowing intervals.
The benchmark does not implement a perf mmap-page reader; the example isolates
the arithmetic contract that such a reader must preserve.

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

Candidate `4b00356` used 12 fresh processes per host on 2026-07-21. At batch
4096, the Arm host's process-median summary reported `3.085239955 ns/op` after
converting reference ticks and `3.084960938 ns/op` after dividing the raw-clock
batch median by 4096. `xlg` reported `3.522954993 ns/op` and
`3.518066406 ns/op` through the same respective derivations. These are medians
across process medians. Within each host, the reference/clock ratio approached
1 as batch size grew, a pattern consistent with fixed-bracket amortization.

The linked workload shape differs across hosts, and the x86 external
process-wall boundary includes runtime TSC calibration. Read the
[cross-host boundary note](measurements/2026-07-21-cross-host.md) before making
comparisons.

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
