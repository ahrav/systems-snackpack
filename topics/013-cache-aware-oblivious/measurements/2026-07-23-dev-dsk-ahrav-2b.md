# 2026-07-23 AArch64 host record

The run used source commit
`053e8f4d269e93276020a7937587762303e0104b` and archive SHA-256
`51a39afc9da86c2a7c070e69b0b714cdb56dd1819cfae6e882bc7730c4721292`.
The runner verified the archive's embedded commit, its own source bytes, the
release binary after measurement, and the source tree after measurement.

## Host boundary

| Field | Observed value |
| --- | --- |
| Requested and resolved host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` |
| Kernel | `6.12.94-123.180.amzn2023.aarch64` |
| CPU evidence | ARM implementer `0x41`, architecture `8`, part `0xd40`, revision `1` |
| Online CPUs and NUMA | 64 CPUs; one NUMA node; automatic NUMA balancing disabled |
| Reported OS base-page size and cache line | 4,096 bytes; 64-byte lines at every reported data or unified cache |
| CPU-0 cache geometry | 64 KiB 4-way L1D with 256 sets; 1 MiB 8-way L2 with 2,048 sets; one 32 MiB 16-way L3 instance with 32,768 sets shared by CPUs 0–63 |
| THP and ASLR policy | THP `madvise`; ASLR mode `2` |
| Rust toolchain | rustc 1.93.1, LLVM 21.1.8; Cargo 1.93.1 |
| C toolchain | GCC 11.5.0; GNU objdump 2.41 |
| Release flags | `-C target-cpu=native -C debuginfo=1 -C codegen-units=1` |
| Benchmark SHA-256 | `920c0d035f2dfd12f40346c278ed7694fcba7362229de5778ae6fa8c52eb684e` |

The host exposed ASIMD, SVE, atomics, and the other features retained in the
[raw host record](raw/053e8f4/arm/host-env.txt). Feature presence does not
establish that a measured loop used those instructions.

## Process results

Each mode used 12 fresh CPU-0-pinned processes. Each process allocated and
initialized a new `2048 x ld` source and destination, swept 128 MiB for
conditioning, executed one transpose, and verified the result. The focused
interval includes mode dispatch and the kernel. Allocation, initialization,
conditioning, verification, and process startup are outside that interval.
It is one post-conditioning invocation per process, not a demonstrated
repeated steady state.

The interval columns below describe the 12 process runs per mode. The
interquartile range is descriptive process-to-process dispersion, not a
confidence interval.

| Mode | Kernel median | Kernel IQR | Sample SD | Whole-process median |
| --- | ---: | ---: | ---: | ---: |
| `pow2-naive` | 19.963515 ms | 0.198731 ms | 0.168407 ms | 124.226050 ms |
| `pow2-tiled` | 8.763907 ms | 0.027995 ms | 0.032894 ms | 113.161589 ms |
| `pow2-recursive` | 9.836988 ms | 0.074937 ms | 0.071782 ms | 114.541703 ms |
| `padded-naive` | 7.217866 ms | 0.076271 ms | 0.071256 ms | 104.007249 ms |
| `padded-tiled` | 6.654559 ms | 0.099648 ms | 0.060631 ms | 103.113246 ms |
| `padded-recursive` | 6.185996 ms | 0.054697 ms | 0.059679 ms | 102.731272 ms |

The paired ratios compare nearby processes within each six-mode block. They
pair time and order, not allocator or physical-page placement.

| Paired kernel ratio | Median | Paired-ratio IQR (12 blocks) |
| --- | ---: | ---: |
| power-of-two naive / tiled | 2.278091x | 2.256209–2.285341x |
| power-of-two naive / recursive | 2.021363x | 2.009180–2.035847x |
| padded naive / tiled | 1.084643x | 1.078231–1.095054x |
| padded naive / recursive | 1.167675x | 1.157004–1.171593x |
| naive power-of-two / padded | 2.759214x | 2.741062–2.772253x |
| tiled power-of-two / padded | 1.317856x | 1.313405–1.327344x |
| recursive power-of-two / padded | 1.586054x | 1.581461–1.596548x |

## Placement and generated code

All 72 processes had distinct recorded source and destination virtual bases.
Every base was offset 16 bytes modulo both 64 and 4,096. The source-destination
virtual distance was fixed at 33,558,528 bytes for power-of-two modes and
33,574,912 bytes for padded modes, so the experiment varied bases but did not
randomize their relative placement. The benchmark did not observe backing-page
sizes, physical frames, or NUMA placement. A separate 256 KiB, 64-base-page
pagemap probe could read present entries but received zero for every PFN. That
probe establishes the process's disclosure boundary, not the benchmark
buffers' placement.

CPU pinning and first touch do not establish the matrices' NUMA placement.
The run did not record PMU events, frequency residency, CPU isolation, or
concurrent host load.

The linked naive loop used scalar `ldr x14, [...]` and `str x14, [...]`, with
the destination index advanced by the leading dimension. The tiled loop used
scalar `ldr x7, [...]` and `str x7, [...]` inside its tile. The recursive public
entry called `transpose_recursive_region` with `bl`. The focused disassembly
contains no vector registers. These observations establish the emitted access
forms for this binary; they do not classify cache misses.

All workspace gates and the correctness example passed in the extracted source
tree. Raw rows, summaries, gate logs, manifests, source verification, pagemap
output, binary, symbols, and disassembly are under the
[AArch64 evidence directory](raw/053e8f4/arm/).
