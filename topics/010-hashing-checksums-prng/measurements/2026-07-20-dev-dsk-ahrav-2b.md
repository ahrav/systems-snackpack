# Arm host measurement, 2026-07-20

## Identity and source

- SSH target and resolved host:
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Kernel: Linux `6.12.94-123.180.amzn2023.aarch64`
- CPU evidence: 64 online CPUs; CPU 0 MIDR `0x411fd401`
  (implementer `0x41`, part `0xd40`, variant 1, revision 1)
- Toolchain: rustc 1.95.0, LLVM 22.1.2, cargo 1.95.0, GCC 11.5.0;
  Clang absent
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`
- Source candidate: `2ef02391a7f2e68587cbf8f18494b73331f9a4d8`
- Source archive SHA-256:
  `3b0c06b53e402bf9bb74ac24da77e326419607f9f37af47b7ca3a78e45d91598`

The native rustc configuration included CRC, NEON, and SVE. The host CPU flags
also included PMULL. These lists record compiler input and CPU capability. They
do not prove that every feature appears in the benchmark.

## Correctness and gates

The example matched the independent bitwise oracle across 16,800 offset and
length cases and 33,411 fragmentation splits. The benchmark verifier matched
16,400 alignment and length cases. Both checked the CRC-32C value
`0xE3069283`; the example also distinguished the CRC-32/ISO-HDLC value
`0xCBF43926`.

The exact source passed formatting, library and example tests, doctests,
Clippy with warnings denied, benchmark compilation, and rustdoc with warnings
denied. The recorded source hashes match the checked-in candidate.

## Timing

Each mode ran in 12 fresh CPU-0-pinned processes. Adjacent table and hardware
processes form a pair, with six pairs in each order. Every process hashed the
same 4,096-byte slice at offset 3 for 262,144 iterations after a 64 MiB warmup.
The steady timer covered 1,073,741,824 bytes. It excluded input construction,
runtime dispatch, the independent check, and warmup.

| Metric | Table | Hardware |
| --- | ---: | ---: |
| Median elapsed | 2,886.315 ms | 52.688 ms |
| Median absolute deviation | 0.317 ms | 0.071 ms |
| Range | 2,885.970 to 2,968.622 ms | 52.439 to 53.543 ms |
| Median throughput | 0.372011 GB/s | 20.379436 GB/s |

The paired table/hardware elapsed ratio had median `54.830321x`, median
absolute deviation `0.081290x`, and range `54.190399x` to `56.097519x`.
The six table-hardware pairs had median `54.845781x` and exact 96.875%
median interval `[54.697889x, 56.097519x]`. The six hardware-table pairs
had median `54.781672x` and interval `[54.190399x, 55.014445x]`. Each
interval is the stratum minimum and maximum and assumes independent,
identically distributed continuous ratios within that order.

Median launch-to-exit time was 3,070.065 ms for table and 58.998 ms for
hardware. That interval includes process startup, setup, warmup, the timed
loop, and teardown. It does not isolate startup cost.

## Generated code and boundary

The linked hardware boundary contained `crc32cx` for eight-byte chunks and
`crc32cb`, `crc32ch`, and `crc32cw` for tails. The compiler unrolled
several updates but kept one CRC-state dependency chain. The table boundary
used byte loads and indexed 32-bit loads from the 1 KiB table.

Measured: correctness, elapsed time, process dispersion, target features, and
linked code. Inferred but not measured: instruction latency, frontend effects,
frequency, cache residency during each call, and causes of the timing ratio.
The harness pinned CPU 0 but did not configure or capture CPU isolation,
governor state, or fixed-frequency state.

Evidence: [raw host directory](raw/2ef0239/dev-dsk-ahrav-2b/).
