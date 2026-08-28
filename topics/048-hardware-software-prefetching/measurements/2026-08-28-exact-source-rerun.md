# Topic 48 exact-source verification — 2026-08-28

This run checks whether the final reviewed Topic 48 experiment builds, returns
correct answers, emits the intended machine-code hint, and preserves a measured
comparison on both required Linux hosts. It does not identify the cache that
served a load, prove that hardware issued or used a prefetch request, or
establish a rule for a processor family.

The sealed source is commit
`f367af8954de2626c8d0ef0b26f77eebf4dd6e99`. Its Secure Hash Algorithm 256-bit
(SHA-256) archive digest is
`58834c58bb98d296a1d10d7dc3990a7fca5a0387962f4159b036e209444ac3c2`.
Each target checked this controller-held digest before extracting or executing
the runner. The runner checked the same digest, controller-supplied hostname,
and controller-supplied architecture again before compilation.

At `08:25:44Z`, a pre-transfer `ssh -G xxl` lookup resolved the Secure Shell
(SSH) alias `xxl` to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. At
`08:25:46Z`, that host reported the same hostname and `x86_64`. The literal Arm
target reported its expected hostname and `aarch64` at `08:25:47Z`.

## What the experiment compared

Each fresh process allocated a 256-mebibyte (MiB) array of 64-byte data records
and a 16-MiB permutation array, for 272 MiB of explicit benchmark allocation.
It completed one untimed warmup pass and timed two passes. Random-gather runs
used workload seed `48000048`, campaign seed `480048`, and hint distances 4,
8, 16, 32, and 64. A distance is a number of future loop accesses, not a byte
distance; distance 16 asks for the record named by the permutation entry 16
accesses ahead. The sequential control used campaign seed `480049` and distance
16. Every process was pinned to logical central processing unit (CPU) 0.

A complete four-process order-balanced block is the analysis unit. Its order is
demand-prefetch-prefetch-demand (D-P-P-D) or
prefetch-demand-demand-prefetch (P-D-D-P). Within a block, the analyzer divides
the geometric mean of the two prefetch times by the geometric mean of the two
demand times. Across blocks, it exponentiates the mean of those block log
ratios. Each host supplied 20 primary random blocks, 2 random A/A blocks that
compared demand with identical demand, 2 primary sequential blocks, and 2
sequential A/A blocks. That is 104 measured processes per host and 208 across
both hosts. Inner-loop accesses and the two passes are not independent samples.

The two-sided 95% Student-t intervals cover variation among complete blocks in
this host, binary, workload, and run window. The analyzer uses three-decimal
tabulated Student-t critical values and emits full-precision JSON; this note
rounds ratio endpoints to five decimal places. The intervals do not cover other
processors, software versions, fleet conditions, or future runs. A
prefetch/demand ratio above 1 means the explicit hint took more time; a ratio
below 1 means it took less time.

## Exact host, toolchain, and binary boundary

- Arm: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, `aarch64`, Linux
  `6.12.100-125.179.amzn2023.aarch64`, 64 available CPUs, and a reported
  64-byte cache line. Model identification register `0x411fd401` maps to Arm
  Neoverse V1 r1p1. CPU 0 recorded node 0, socket 0, core 0, online. The host
  used GNU Compiler Collection (GCC) 11.5.0, Python 3.9.25, GNU objdump
  2.41-50.amzn2023.0.5, and Rust 1.95.0. GCC reported native target
  `armv8.4-a+crypto+sha3+sm4+sve+rng+i8mm+bf16` tuned for `neoverse-n1`.
  Binary SHA-256:
  `0e481c797b2b7c107d6ed71e55d7220e395ac28f9978ef4d6f695fe2cecc20e1`.
- `xxl`: resolved host `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`,
  `x86_64`, Linux `6.12.95-124.187.amzn2023.x86_64`, 192 available CPUs,
  and a reported 64-byte cache line. The host reported Intel Xeon Platinum
  8488C, family 6 model 143 stepping 8, microcode `0x2b000670`, two sockets,
  two threads per core, and Kernel-based Virtual Machine (KVM) virtualization.
  CPU 0 recorded node 0, socket 0, core 0, online. The host used GCC 11.5.0,
  Python 3.9.25, GNU objdump 2.41-50.amzn2023.0.5, and Rust 1.98.0. GCC
  reported native target and tuning `sapphirerapids`. Binary SHA-256:
  `e5abef158fef21a9daa0ef996e6c0f59c42c8341fd2eafb225fc88c2b26c2353`.

Both hosts compiled with `-O3 -g -std=c11 -Wall -Wextra -Werror -march=native
-fno-tree-vectorize -fno-tree-slp-vectorize`. Both in-host validators
regenerated disassembly from the retained binary. The Arm prefetch kernel
contained `prfm pldl1strm`; the x86-64 kernel contained `prefetchnta`. Neither
demand kernel contained an explicit prefetch instruction. Instruction presence
proves code generation only; it does not prove that a request was issued or
useful.

## Random-gather result

| Distance | Arm prefetch/demand ratio, 95% interval | `xxl` prefetch/demand ratio, 95% interval |
|---:|---:|---:|
| 4 | 1.03844 [1.03469, 1.04220] | 1.00802 [0.98291, 1.03376] |
| 8 | 1.01383 [1.01232, 1.01535] | 1.04964 [1.03135, 1.06826] |
| 16 | 1.00539 [1.00003, 1.01077] | 1.02667 [0.98945, 1.06530] |
| 32 | 1.03639 [1.03142, 1.04138] | 0.98809 [0.95978, 1.01724] |
| 64 | 1.03855 [1.03739, 1.03970] | 0.97432 [0.94089, 1.00894] |

The Arm A/A ratio was 1.00045 [0.98513, 1.01601]. Its interval includes 1.
Every tested Arm primary interval was above 1, although distance 16 cleared 1
by only 0.00003 at the printed precision. The evidence shows slower
prefetch-labeled outcomes for this exact campaign, not a processor-family rule.

The `xxl` A/A ratio was 0.99761 [0.97499, 1.02075]. Distances 4, 16, 32, and 64
remain unresolved because their intervals include 1. Distance 8 was 1.04964
[1.03135, 1.06826], about 4.96% more elapsed time for the explicit-hint path in
this run. It is a candidate for replication, not a processor-family rule.

## Sequential control and phase boundaries

At distance 16, the Arm sequential ratio was 1.02224 [1.02065, 1.02382], with
an A/A ratio of 0.99665 [0.99192, 1.00141]. The `xxl` sequential ratio was
1.45057 [1.21716, 1.72875], with an A/A ratio of 0.97230 [0.65375, 1.44608].
Both primary intervals were above 1. Each used only two complete blocks, and
the `xxl` A/A interval was especially wide, so these remain descriptive
run-window results rather than mechanism evidence.

Startup remained outside the timed comparison. Across the 88 random processes,
median initialization, untimed warmup, and timed aggregate were 0.123176 s,
0.030681 s, and 0.061230 s on Arm. They were 0.133845 s, 0.052333 s, and
0.104053 s on `xxl`. Sequential medians were 0.086019 s, 0.009953 s, and
0.019880 s on Arm, and 0.101531 s, 0.025074 s, and 0.049637 s on `xxl`.

All 208 measured processes produced the expected checksum. The timed regions
recorded zero minor page faults and zero major page faults. Every timed region
began and ended on CPU 0 under single-CPU affinity, with zero endpoint-placement
mismatches; the two endpoint samples cannot exclude a migration away and back.
All processes reported an accepted `MADV_NOHUGEPAGE` request. This Linux memory
advice asks the kernel not to use transparent huge pages for the mapping;
acceptance does not prove the mapping's eventual page size.

Before runner extraction, each received archive passed a controller-side
SHA-256 check. Both in-host validators then reported `valid: true` against the
same controller-supplied digest and identity, with code generation regenerated
from the retained binary. Independent publication validation again supplied
the published digest, hostname, and architecture and reported `valid: true`;
the publication host lacked cross-architecture disassemblers, so that second
code-generation check was limited to the manifest-bound recorded text.

Directly measured or observed facts are the host records, checksums, elapsed
times, page-fault counts, CPU placement, hashes, and linked instructions.
Ratios, medians, and intervals are derived from those records. Explanations
involving redundant hardware prefetching, cache pollution, bandwidth, address
translation, or request-buffer pressure remain hypotheses that require
additional exact-model counters.

Raw receipts: [`raw/2026-08-28-f367af8/`](raw/2026-08-28-f367af8/).
