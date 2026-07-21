# 2026-07-21 corrected Arm record

## Boundary

- Source and archive commit: `5117e64d5c5df6ef1615749cacb95eabe38956c0`
- Archive SHA-256: `8a8ce53a63029ad3b6512b4f3787ae12a57d326af71a0d97420045ff8da3b6cc`
- Benchmark binary SHA-256: `1bc8a76e31280df64c1d255829d86e215b2402473b91f0fb283ef220d0cd6b73`
- Host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Kernel: `6.12.94-123.180.amzn2023.aarch64`
- CPU evidence: 64 online AArch64 CPUs; ARM model `1`, stepping `r1p1`;
  supplemental MIDR `0x411fd401` (`implementer=0x41`, `part=0xd40`,
  `variant=1`, `revision=1`); product `c7g.16xlarge`
- Toolchain: rustc `1.93.1`, LLVM `21.1.8`, Cargo `1.93.1`, GCC `11.5.0`,
  GNU binutils `2.41-50.amzn2023.0.5`
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`

The [environment record](raw/5117e64/arm/host-env.txt) contains `uname`, CPU
topology and flags, compiler versions, native Rust target features, clocksource,
and perf policy. The [MIDR supplement](raw/5117e64/arm/host-cpu-model-supplement.txt)
was captured read-only from the same resolved host after the benchmark at
`2026-07-21T16:03:57.553105526Z`.

## Counter and clock

The linked endpoint is `ISB; MRS CNTVCT_EL0; ISB`. `CNTFRQ_EL0` reported
`1,050,000,000 Hz`. One million ordered reads had no equal or backward values;
the minimum positive adjacent-read delta was `38` ticks. The raw clock reported
`1 ns` resolution; 200,000 reads had no equal or backward values and a `35 ns`
minimum positive delta. Both probes remained on CPU 0. The clocksource was
`arch_sys_counter`; `perf_event_paranoid=2` and `perf_user_access=0`.

The 200-times empirical guard used `7600` ticks and `7000 ns`; every
65,536-operation process median passed. These thresholds are host-and-harness
observations, not timestamp-error bounds.

## Process-level result

Each cell is median / MAD / range across 12 fresh-process medians. Each process
was pinned to CPU 0, retained 500 raw samples per timer and batch, and reported
zero rejections. Six processes used each timer order in three ABBA blocks.

| Batch | Reference-derived ns/op | Raw-clock ns/op | Reference/clock ratio |
| ---: | --- | --- | --- |
| 1 | `37.619047619 / 0.476190476 / [36.190476190, 39.047619048]` | `37 / 1 / [36, 39]` | `1.003861004 / 0.026078710 / [0.952380952, 1.058201058]` |
| 16 | `5.238095238 / 0 / [5.119047619, 5.238095238]` | `5.187500000 / 0 / [5.062500000, 5.187500000]` | `1.009753299 / 0.011194604 / [0.986804360, 1.034685479]` |
| 256 | `3.210565476 / 0.002790179 / [3.206845238, 3.214285714]` | `3.205078125 / 0.001953125 / [3.199218750, 3.210937500]` | `1.002292465 / 0.001254253 / [0.998725524, 1.004709576]` |
| 65,536 | `3.077450707 / 0 / [3.077436175, 3.077450707]` | `3.077438354 / 0 / [3.077438354, 3.077621460]` | `1.000004014 / 0 / [0.999944518, 1.000004014]` |

At batch 65,536, both order strata had a `3.077450707 ns/op` reference median
and `3.077438354 ns/op` clock median. External process wall time was
`210.354986 ms` median, `0.116328 ms` MAD, range
`[210.200002, 210.891114] ms`. It includes detection, warmup, all batches, and
output; those costs are outside each timed batch.

## Generated code and interpretation

The linked `read_counter` body contains `isb; mrs cntvct_el0; isb`. The linked
recurrence is one dependent loop with two `mul` instructions. Raw counter ticks,
raw-clock durations, and external wall times are measured. Counter-to-time,
per-operation values, process summaries, and ratios are derived.

The convergence near `3.0774 ns/op` is consistent with fixed bracket
amortization for this binary and host. It does not isolate instruction latency,
prove the counter's update granularity, or support an AArch64-wide claim.

Raw evidence: [`raw/5117e64/arm`](raw/5117e64/arm).
