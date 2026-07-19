# Arm host measurement, 2026-07-19

## Identity and source

- Alias: `dev-dsk-ahrav-2b`
- Resolved host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Kernel: Linux `6.12.94-123.180.amzn2023.aarch64`
- CPU evidence: 64 online Arm CPUs; CPU 0 MIDR `0x411fd401`
  (implementer `0x41`, part `0xd40`, variant 1, revision 1)
- Toolchain: rustc 1.95.0, LLVM 22.1.2, cargo 1.95.0, GCC 11.5.0
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`
- Source: `4e855a3e9cff664ea6c4de6f7d90f13dabadb999`
- Archive SHA-256: `a83745ddf9ff30b629169315fe2332badf57cdb1a7fdaee231d4b0447c92c4bb`

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
warnings denied. The exact source-file hashes also match the checked-in source.

## Timing

Each of 12 fresh CPU-0-pinned processes timed both variants over 4,000,000
identical positions from `[0, N)`. Each variant received 262,144 warmup
queries. Dataset generation, input cloning, both builds, query generation, and
warmup were outside the query timers.

| Metric | Compact | Prefix |
| --- | ---: | ---: |
| Mean | 12.897 ns/query | 10.999 ns/query |
| Standard deviation | 0.567 | 0.133 |
| Median | 12.861 ns/query | 10.951 ns/query |
| Median absolute deviation | 0.542 | 0.062 |
| Range | 12.294 to 13.618 | 10.850 to 11.285 |

The paired prefix/compact ratio had median `0.849694`, median absolute
deviation `0.037487`, and exact 96.1% paired-median interval `0.814860` to
`0.902087`. The interval is the third through tenth ordered ratio under
independent, identically distributed continuous pair ratios.

The median compact time was 12.319 ns when measured first and 13.435 ns when
measured second. The corresponding paired-ratio medians were 0.895 and 0.815.
Alternating order balanced this observed order effect; it did not remove it.

Median construction time was 2.925 ms for the compact directory and 119.639 ms
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

Evidence: [raw host directory](raw/4e855a3/dev-dsk-ahrav-2b/).
