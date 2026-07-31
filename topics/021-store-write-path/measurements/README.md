# Measurement contract

A Topic 21 result applies only to its named source commit, source-file
manifests, benchmark SHA-256, host, CPU, affinity, kernel, toolchain, native
flags, workload, and run window. The before/after per-file manifests identify
the checked-out bytes used for the build and run.

## Treatments and timed boundaries

The write treatment uses a 512 MiB, 4 KiB-aligned destination and complete
64-byte stores. `A` is temporal. `B` is non-temporal: `VMOVNTDQ` plus `SFENCE`
before release publication on x86-64, or advisory `STNP` plus release
publication on AArch64. `timed_ns` begins immediately before calling the write
wrapper and ends after `ready = 1` is published. The interval therefore also
includes the support check, ready reset, dispatch, and call overhead. The
same-thread `SeqCst` fence and full-pattern verification remain outside it.

The STLF treatment uses 500,000,000 iterations of one dependent eight-byte
store/load recurrence. `A` loads the exact stored bytes. `B` loads eight bytes
from `+4`, so half of each load lies beyond the preceding store. `timed_ns`
covers the `run_stlf` wrapper, including its assertions, support check, and
dispatch, followed by the recurrence. The deterministic oracle runs afterward.

Every record reports separate setup, scrub, timed, and verification durations
with `/proc/self/stat` minor- and major-fault deltas. The write scrub prefaults
the destination and an equally sized eviction allocation. The STLF scrub
initializes its 16-byte fixture. A timed page fault invalidates the process;
any major fault invalidates the process regardless of phase.

## Analysis unit

One four-process block is the analysis unit. For block `i`, the driver computes:

```text
L_i = mean(ln(B_i1), ln(B_i2)) - mean(ln(A_i1), ln(A_i2))
```

The reported `B/A` point estimate is `exp(mean(L_i))`. If `s_L` is the sample
standard deviation among `n` block contrasts, its 95% interval endpoints are
`exp(mean(L_i) +/- t * s_L / sqrt(n))`. Primary comparisons use 12 blocks, 11
degrees of freedom, and critical value `2.200985`. A/A controls use four blocks,
three degrees of freedom, and critical value `3.182446`.

A ratio above one means `B` took longer. For the write comparison, `B` is
non-temporal. For the STLF comparison, `B` is partial overlap. Process timings
are within-block observations; 48 process timings do not create 48 independent
units for the primary interval.

The A/A control traverses the same command, allocation, process, parser, and
analysis path with two labels mapped to one implementation. The runner reports
the control interval but enforces no acceptance threshold. Interpret it before
the primary interval and retain it with every result.

## Evidence limits

The interval covers between-block variation for one binary, CPU, workload, and
run window. It does not cover independent builds, future load, other hosts, an
ISA, or a vendor family. Absolute x86-64 and AArch64 timings are not a
cross-architecture treatment comparison.

Mnemonic presence is a necessary code-generation gate, not proof of the
executed path, instruction order, or cache-allocation behavior. Manual review
of the complete focused function bodies establishes the retained kernel shape.
The runner records a bounded, keyword-filtered excerpt of `perf list` but does
not collect counter samples. Attribute a timing difference to write allocation,
store-buffer behavior, or replay only after adding mechanism evidence outside
the timed schedule.

The write workload performs a one-pass overwrite with no consumer read before
publication. It does not represent partial-line writes, small buffers, or data
that must remain cache-resident. The STLF workload isolates one aligned
eight-byte store and two load offsets; it does not characterize every size,
alignment, or overlap geometry.

No retained host evidence exists as of the first visit on 2026-07-31. A future
result note must link the raw evidence and report both primary and A/A intervals
without replacing failed or incomplete attempts.
