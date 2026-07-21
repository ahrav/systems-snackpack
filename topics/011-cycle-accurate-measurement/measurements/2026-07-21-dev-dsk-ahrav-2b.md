# 2026-07-21: dev-dsk-ahrav-2b

## Boundary

- Source and archive commit: `4b00356711a3934fd92ec62a099991a71ecd6529`
- Archive SHA-256: `d9952eb769dbf1d8716fa32cebca446e87fbf1948d4388645546896d60b05bc9`
- Benchmark binary SHA-256: `70d89f756362af8effc29d98db8975e328f463361f0268006941dec5c1ff5a95`
- Host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Kernel: `6.12.94-123.180.amzn2023.aarch64`
- CPU evidence: 64 online AArch64 CPUs; ARM model `1`, stepping `r1p1`;
  supplemental MIDR `0x411fd401` (`implementer=0x41`, `part=0xd40`,
  `variant=1`, `revision=1`); product `c7g.16xlarge`
- Toolchain: rustc `1.93.1`, LLVM `21.1.8`, GCC `11.5.0`, GNU binutils
  `2.41-50.amzn2023.0.5`
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`

The [CPU model supplement](raw/4b00356/arm/host-cpu-model-supplement.txt) was
captured read-only from the same resolved host at
`2026-07-21T15:07:22.370949341Z`, after the benchmark. The record preserves the
raw MIDR fields rather than assigning a marketing or microarchitecture name.

## Counter and clock

The architectural path was `ISB; MRS CNTVCT_EL0; ISB`. `CNTFRQ_EL0` reported
`1,050,000,000 Hz`. One million ordered reads produced no equal or backward
values; the minimum positive adjacent-read delta was `38` ticks and the GCD was
`1`. `CLOCK_MONOTONIC_RAW` advertised `1 ns`; 200,000 reads produced no equal or
backward values and a minimum positive delta of `34 ns`. Both probes started and
ended on CPU 0. The Linux clocksource was `arch_sys_counter`;
`perf_event_paranoid=2` and `perf_user_access=0`.

The adjacent-read minima are empirical read-spacing evidence. They are not
upper bounds on timestamp error. The 200-times guard used thresholds of `7600`
ticks and `6800 ns`; every 4096-operation process median passed.

## Process-level result

Each cell is median / MAD / range across 12 fresh-process medians. Every process
was pinned to CPU 0, retained 500 raw samples per timer and batch, and completed
with zero rejections. Six processes used each timer order in three ABBA blocks.

| Batch | Reference-derived ns/op | Raw-clock ns/op | Reference/clock ratio |
| ---: | --- | --- | --- |
| 1 | `37.142857143 / 0.952380952 / [34.285714286, 38.095238095]` | `37.000000000 / 0.500000000 / [36.000000000, 40.000000000]` | `1.002506266 / 0.012870013 / [0.880952381, 1.058201058]` |
| 16 | `5.238095238 / 0 / [5.119047619, 5.238095238]` | `5.156250000 / 0.031250000 / [5.062500000, 5.250000000]` | `1.009753299 / 0.000699663 / [0.997732426, 1.034685479]` |
| 256 | `3.208705357 / 0.001860119 / [3.203125000, 3.210565476]` | `3.207031250 / 0 / [3.199218750, 3.210937500]` | `1.001102024 / 0.002320051 / [0.998725524, 1.003546718]` |
| 4096 | `3.085239955 / 0 / [3.084774926, 3.085239955]` | `3.084960938 / 0 / [3.084960938, 3.085205078]` | `1.000090445 / 0 / [0.999860576, 1.000090445]` |

At batch 4096, raw-first and clock-first reference medians were `3.084891183`
and `3.085239955 ns/op`; both clock strata were `3.084960938 ns/op`.

The timed batch excludes process launch, counter detection, and warmup. The
external process wall interval includes those costs, all batches, and output
formatting. It was `20.899653 ms` median, `0.050028 ms` MAD, range
`[20.714560, 21.014413] ms` across 12 processes.

## Generated code and interpretation

The linked `read_counter` body is exactly `isb; mrs x0,cntvct_el0; isb; ret`.
The linked recurrence retains dependent `add`, shifted `eor`, two `mul`
instructions, and a loop branch. Constant setup, the call boundary, and final
value consumption remain part of the measured workload shape.

The reference column converts measured counter ticks with `CNTFRQ_EL0`; it is
derived elapsed time, not measured core cycles. Convergence near `3.085 ns/op`
supports fixed bracket-cost amortization for this binary and host. It does not
isolate instruction latency or support an AArch64-wide claim.

Raw evidence: [`raw/4b00356/arm`](raw/4b00356/arm).
