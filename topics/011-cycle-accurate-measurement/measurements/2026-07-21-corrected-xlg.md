# 2026-07-21 corrected xlg record

## Boundary

- Source and archive commit: `5117e64d5c5df6ef1615749cacb95eabe38956c0`
- Archive SHA-256: `8a8ce53a63029ad3b6512b4f3787ae12a57d326af71a0d97420045ff8da3b6cc`
- Benchmark binary SHA-256: `6c6b6314650fc39b434a6443464fc52618d8adc068c2997da777ec70b6c63688`
- Alias: `xlg`
- Resolved host: `dev-dsk-ahrav-2c-a9191cb6.us-west-2.amazon.com`
- Kernel: `6.12.94-123.180.amzn2023.x86_64`
- CPU evidence: 128 online CPUs; `AuthenticAMD AMD EPYC 9R14`, family 25,
  model 17, stepping 1; two sockets in a KVM guest
- Toolchain: rustc `1.93.1`, LLVM `21.1.8`, Cargo `1.93.1`, GCC `11.5.0`,
  GNU binutils `2.41-50.amzn2023.0.5`
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`

The [environment record](raw/5117e64/xlg/host-env.txt) contains `uname`, CPU
topology and flags, compiler versions, native Rust target features, clocksource,
virtualization evidence, and perf policy.

## Counter and clock

CPUID reported TSC, RDTSCP, and invariant TSC. The linked endpoint executes
RDTSCP, saves TSC and TSC_AUX, then executes CPUID before returning. It provides
a prior-instruction/load boundary and a later-work serialization point; it is
not a prior-store visibility boundary. TSC_AUX remained `0`, `sched_getcpu`
remained `0`, and there were no rejected samples. Those checks do not detect
every virtual-machine migration.

CPUID leaf `0x15` did not supply a usable frequency. Each process used ten
100 ms comparisons with `CLOCK_MONOTONIC_RAW`, five in each nesting order.
Across 12 processes the estimated frequency was `2,599,989,498.5 Hz` median,
`914 Hz` MAD, range `[2,599,985,866, 2,599,992,621] Hz`.

One million ordered endpoint reads had no equal, backward, or TSC_AUX-changing
values; the minimum positive adjacent-read delta was `2236` ticks. The raw
clock reported `1 ns` resolution; 200,000 reads had no equal or backward values
and a `19 ns` minimum positive delta. The clocksource was `tsc` and
`perf_event_paranoid=-1`; the record makes no RDPMC permission claim.

The 200-times empirical guard used `447,200` ticks and `3800 ns`; every
65,536-operation process median passed. The high counter threshold reflects the
strong endpoint's measured cost. It is not a timestamp-error bound.

## Process-level result

Each cell is median / MAD / range across 12 fresh-process medians. Each process
was pinned to guest CPU 0, retained 500 raw samples per timer and batch, and
reported zero rejections. Six processes used each timer order in three ABBA
blocks.

| Batch | TSC-derived ns/op | Raw-clock ns/op | Reference/clock ratio |
| ---: | --- | --- | --- |
| 1 | `870.003513978 / 0.000305841 / [870.002469134, 870.004729480]` | `30 / 0 / [30, 30]` | `29.000117133 / 0.000010195 / [29.000082304, 29.000157649]` |
| 16 | `57.500232246 / 0.000020214 / [57.500163190, 57.500312581]` | `4.375 / 0 / [4.375, 4.375]` | `13.142910228 / 0.000004620 / [13.142894443, 13.142928590]` |
| 256 | `6.875027769 / 0.000002417 / [6.875019512, 6.875037374]` | `3.593750000 / 0 / [3.593750000, 3.593750000]` | `1.913051205 / 0.000000673 / [1.913048908, 1.913053878]` |
| 65,536 | `3.526778161 / 0.000001240 / [3.526773925, 3.526783088]` | `3.513793945 / 0 / [3.513793945, 3.513793945]` | `1.003695213 / 0.000000353 / [1.003694007, 1.003696615]` |

At batch 65,536, raw-first and clock-first TSC-derived medians were
`3.526778065` and `3.526778161 ns/op`; both clock strata were
`3.513793945 ns/op`. External process wall time was `1244.934887 ms` median,
`0.135011 ms` MAD, range `[1244.724502, 1246.904125] ms`. The ten 100 ms
frequency-calibration intervals dominate this boundary.

## Generated code and interpretation

The linked endpoint has RDTSCP before CPUID and preserves TSC_AUX. The linked
recurrence has an eight-step unrolled dependent main loop. Raw ticks, raw-clock
durations, and external wall times are measured. Frequency conversion,
per-operation values, process summaries, and ratios are derived.

The approach toward `3.52 ns/op` is consistent with fixed endpoint-cost
amortization for this guest, binary, and host. It does not isolate instruction
latency or rank AMD, x86-64, or virtualized systems.

Raw evidence: [`raw/5117e64/xlg`](raw/5117e64/xlg).
