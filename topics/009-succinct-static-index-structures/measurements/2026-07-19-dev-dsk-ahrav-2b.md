# Arm host measurement, 2026-07-19

## Identity and source

- Alias: `dev-dsk-ahrav-2b`
- SSH target and resolved host:
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Kernel: Linux `6.12.94-123.180.amzn2023.aarch64`
- CPU evidence: 64 online Arm CPUs; CPU 0 MIDR `0x411fd401`
  (implementer `0x41`, part `0xd40`, variant 1, revision 1)
- Toolchain: rustc 1.95.0, LLVM 22.1.2, cargo 1.95.0, GCC 11.5.0
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`
- Source: `03b9067f7a24bfc717d0237e4b41599d30178a03`
- Archive SHA-256: `a0d3f5ead392eb9a1739b9f08ffc2c96fad74cc572618dfc9d7fc60c2d0620f9`

The native rustc configuration included NEON, SVE, LSE, CRC, dot-product,
I8MM, and BF16 features. This list records compiler input. It does not prove
that every feature appears in the benchmark.

## Correctness and space

The exhaustive example checked all 67,108,865 prefix positions for a
67,108,864-bit deterministic input containing 33,558,635 one bits. The compact
representation used 11,010,048 logical bytes. The prefix oracle used
268,435,460 bytes, or 24.381 times as much.

The remote Topic 9 workspace passed formatting, library and example tests,
doctests, Clippy with warnings denied, benchmark compilation, and rustdoc with
warnings denied. The exact source-file hashes match candidate `03b9067`.

## Timing

Each of 12 fresh CPU-0-pinned processes timed both variants over 4,000,000
identical positions from `[0, N)`. Each variant received 262,144 warmup
queries. Dataset generation, input cloning, both builds, query generation, and
warmup were outside the query timers.

| Metric | Compact | Prefix |
| --- | ---: | ---: |
| Mean | 13.131 ns/query | 10.950 ns/query |
| Standard deviation | 0.313 | 0.100 |
| Median | 13.190 ns/query | 10.962 ns/query |
| Median absolute deviation | 0.306 | 0.081 |
| Range | 12.740 to 13.506 | 10.804 to 11.124 |

Across all 12 balanced pairs, the descriptive prefix/compact ratio median was
`0.840882`, its median absolute deviation was `0.022981`, and its range was
`0.799937` to `0.864540`. The six compact-prefix pairs had median `0.852307`
and exact 96.875% median interval `0.846308` to `0.864540`. The six
prefix-compact pairs had median `0.813999` and interval `0.799937` to
`0.835455`. Each stratum interval is its minimum and maximum and assumes IID,
continuous ratios within that order stratum. No common-distribution interval
is assigned to the pooled ratios.

Median construction time was 2.987 ms for the compact directory and 125.658 ms
for the prefix oracle. Construction was not part of the query timer.

## Generated code and boundary

The linked compact inspection symbol retained endpoint and bounds checks,
three indexed data loads, mask selection, and an SVE `cnt` population count.
The prefix symbol retained one indexed 32-bit load after its bounds check.

Measured: correctness, structural bytes, build and query elapsed time, process
dispersion, target features, and linked code. Inferred but not measured: cache,
TLB, bandwidth, or instruction-throughput causes. Both structures remained
allocated in each process; page residency was not measured. CPU pinning did not
isolate CPU 0 or fix its frequency.

Evidence: [raw host directory](raw/03b9067/dev-dsk-ahrav-2b/).
