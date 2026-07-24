# 2026-07-24 AArch64 host record

The run used source commit
`8301b344287c674f559dbbd22718a7c6cd49921d` and archive SHA-256
`9af2fe9e343353f3086d4c57f499f5ac19f722f5cfa0bc19d31a8d276db5d59b`.
The runner verified the archive's embedded commit and identical source hashes
before and after the run. After relocation into this repository, all 29 entries
in the evidence manifest passed `sha256sum -c`.

## Host boundary

| Field | Observed value |
| --- | --- |
| Requested and resolved host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` |
| Probe time | `2026-07-24T16:05:17.301279793Z` |
| `uname` and kernel | Linux AArch64; `6.12.94-123.180.amzn2023.aarch64` |
| CPU evidence | ARM implementer `0x41`, architecture `8`, part `0xd40`, variant `0x1`, revision `1` |
| Online CPUs and affinity | 64 online CPUs; timed processes pinned to CPU 0 |
| Reported host features | `asimd`, SVE, and the other features in the raw host record |
| Rust target configuration | `aarch64`; baseline `neon` present |
| Rust toolchain | rustc 1.93.1, LLVM 21.1.8; Cargo 1.93.1 |
| C and binary toolchain | GCC 11.5.0; GNU binutils 2.41 |
| Release flags | `-C target-cpu=generic -C debuginfo=1 -C codegen-units=1 -C llvm-args=-vectorize-loops=false -C llvm-args=-vectorize-slp=false` |
| Selected variant | `neon` |
| Benchmark SHA-256 | `8f940f1eaefc19db5328307d7b6d98f01f99c1ed08223207be7a3f74ad12d1e1` |

Feature presence establishes legality, not the instructions emitted or the
variant's profitability. The linked-code observations below provide the
code-generation evidence for this binary.

## Process results

Each comparison used 12 AB/BA fresh-process pairs, with six pairs in each
order. Every process created and checked a deterministic 64 MiB input, then
timed eight complete passes. Chunked modes used 256-byte chunks. The steady
interval excludes setup, scalar-oracle evaluation, and final verification.
One CPU-0-pinned process is one replicate; the eight passes are not independent
samples.

The interval below is the descriptive IQR across 12 process observations in
one run window, not a confidence interval.

| Comparison and mode | Steady median | Process IQR |
| --- | ---: | ---: |
| scalar versus SIMD: `scalar_whole` | 354.917679 ms | 354.349672–355.081213 ms |
| scalar versus SIMD: `simd_whole` | 69.420895 ms | 69.396936–69.455050 ms |
| whole versus chunks: `dispatch_once` | 69.402648 ms | 69.367809–69.418835 ms |
| whole versus chunks: `cached_chunks` | 71.472527 ms | 71.462861–71.540418 ms |
| cached versus detect: `cached_chunks` | 71.478720 ms | 71.464359–71.502230 ms |
| cached versus detect: `detect_chunks` | 71.402265 ms | 71.393578–71.428374 ms |

Paired ratios divide the first named mode's steady time by the second's:

| Paired steady-time ratio | Median | Paired-ratio IQR |
| --- | ---: | ---: |
| scalar whole / SIMD whole | 5.110466x | 5.094078–5.114599x |
| dispatch once / cached chunks | 0.970531x | 0.970156–0.971282x |
| cached chunks / detect chunks | 1.001167x | 1.000839–1.001327x |

The selected Advanced SIMD path took about one-fifth of the scalar path's
steady time in this workload. Dispatching once per 64 MiB buffer was faster
than invoking the cached function pointer for each 256-byte chunk.

Repeated detection was slightly faster than cached chunk dispatch in this run:
the paired cached/detect median was `1.001167x`. That small result is
host-, binary-, and run-window-specific. It is not evidence that repeated
detection is generally beneficial.

## Generated code and interpretation

The scalar control used a byte `ldrb`, `cmp`, and conditional increment loop.
The Advanced SIMD implementation used vector loads, `cmeq`, `cnt`, and `addv`.
The retained `resolve_best` body returned the NEON function address and kind
without a feature-cache branch. `count_eq_dispatch_once` tail-branched directly
to the proven NEON entry. These are observations of the linked binary, not
source-level expectations.

The run did not collect performance-monitoring-unit events, frequency
residency, CPU isolation, or concurrent-load measurements. It therefore does
not identify the hardware cause of a timing difference. The constant resolver
and the target configuration's baseline `neon` are observed; attributing the
small cached/detect difference to any one instruction sequence would be
inference.

All required workspace gates and the correctness example passed in the
extracted source tree. Raw process rows, summaries, host and toolchain details,
build flags, gate logs, source verification, binary, symbols, and disassembly
are in the [AArch64 evidence directory](raw/8301b34/arm/).
