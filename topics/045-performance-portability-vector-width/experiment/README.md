# Focused vector-width experiment

This experiment asks how vector width changes one compute-bound recurrence on
one pinned logical central processing unit (CPU). It does not measure memory
bandwidth, a complete service, or a processor family's frequency policy.

## Workload

[`width_bench.c`](width_bench.c) updates 96 independent double-precision chains.
Each logical chain performs the same number of
`x = fused_multiply_add(multiplier, addend, x)` steps. Twelve independent
accumulators keep dependency latency from serializing the loop. The scalar path
disables compiler vectorization. Intrinsics select 128-bit, 256-bit, and 512-bit
paths where the architecture and runtime feature check allow them.

GNU Compiler Collection (GCC) must use these flags:

```text
-O3 -std=c11 -Wall -Wextra -Werror -fno-tree-vectorize
-ffp-contract=fast -fno-omit-frame-pointer
```

The correctness check compares every supported path with the scalar result. It
limits the absolute checksum difference to
`64 × 2^-52 × max(1, |scalar checksum|)`, allowing only bounded floating-point
reduction-order variation. The generated-code gate is separate: on AArch64 it
requires exactly 12 independent `fmla` destinations and no vector copy or
memory instruction in the detected hot loop. That gate rejects a
destination-operand mistake even when the final checksum remains within the
bound.

## Process schedule

[`run_experiment.py`](run_experiment.py) calls the baseline mode A and the
candidate mode B. ABBA and BAAB are order-balanced four-process blocks: each
mode occupies both early and late positions. An A/A control assigns both labels
to the same mode. The script applies this fixed schedule:

1. Reject an existing output directory and record the binary digest.
2. Run every supported mode for the exact 20,000,000-step workload. Use that
   run's scalar result as the timed-process oracle and record supported modes.
3. Use eight equal-count, seed-shuffled ABBA or BAAB blocks per comparison.
4. Launch one fresh, CPU-pinned process per letter. Retain timeout and failed
   attempts without replacement. Flush and synchronize each raw row before the
   next process.
5. Wait 0.2 seconds after each attempt. Each process uses 2,000,000 same-mode
   warmup steps and 20,000,000 measured steps.
6. Run eight same-mode A/A blocks after the treatment comparisons.
7. Recheck the binary digest after the fixed schedule.

The child environment contains only `LANG=C`, `LC_ALL=C`, `PATH` set to the
platform default executable path, and `TZ=UTC`, where UTC means Coordinated
Universal Time. Each process has a 120-second deadline.

For one block, the log contrast is the average logarithm of the two candidate
times minus the average logarithm of the two baseline times. One complete block
is one replication. Exponentiating the mean of eight block contrasts gives the
geometric candidate-to-baseline ratio. The paired Student-t interval describes
uncertainty across those eight fresh-process blocks and uses seven degrees of
freedom. Exponentiating the log-contrast standard deviation gives the
multiplicative standard-deviation factor. Each interval describes only its
named comparison; the set of intervals does not jointly provide 95% coverage.

The primary timer uses Linux `CLOCK_MONOTONIC_RAW`, a monotonic clock not
adjusted by wall-clock corrections, around the main fixed-work kernel. It
excludes process startup and same-mode warmup. Linux `perf stat`, the hardware
counter command, surrounds the whole child, so its user-mode counters include
startup, warmup, and the main kernel. On x86-64, user-mode core and reference
cycles form one simultaneous group. Reference cycles advance independently of
frequency scaling when the platform exposes the event. AArch64 records
user-mode core cycles because the required Arm host does not expose reference
cycles.

## Checked-source host run

Create a Git archive from the exact publication candidate, transfer it through
the authorized Secure Shell (SSH) target, and invoke the archived runner. The
target label and resolved hostname bind the receipt to the SSH route and the
machine that executed it. The output directory must not exist and must remain
outside the repository.

```bash
SOURCE_COMMIT=<40-hex-commit> \
SOURCE_ARCHIVE_SHA256=<64-hex-digest> \
SOURCE_ARCHIVE_PATH=/tmp/topic45-source.tar.gz \
SSH_TARGET_LABEL=<xxl-or-authorized-arm-host> \
SSH_RESOLVED_HOSTNAME=<hostname-from-runtime-resolution> \
topics/045-performance-portability-vector-width/experiment/run_host.sh \
  /tmp/topic45-receipts <CPU> 20000000
```

[`run_host.sh`](run_host.sh) rejects an unsafe archive, verifies its embedded
commit and digest, compares its own bytes with the archived runner, records host
and toolchain state, runs crate tests, builds the C probe, captures code
generation, runs the fixed schedule, and validates the receipts. The checked-in
validator re-derives the archive manifest and block contrasts. Collection must
run that validator again with the expected target label and resolved hostname.

```bash
python3 -I -B experiment/validate_receipts.py /path/to/host-receipts \
  --expected-label xxl \
  --expected-resolved-host dev-dsk-example.us-west-2.amazon.com \
  --expected-source-commit <40-hex-commit> \
  --expected-archive-sha256 <64-hex-digest> \
  --output /tmp/topic45-independent-validation.json
```

Review raw order, the A/A result, counter running time, and per-CPU steal ticks,
which count scheduler-accounting intervals when a virtual CPU wanted to run but
the hypervisor did not schedule it. Also inspect generated loops and host state
before attributing a timing ratio to vector width or clock behavior.
