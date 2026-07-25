# 2026-07-24 cross-host record

Both hosts ran source commit
`8301b344287c674f559dbbd22718a7c6cd49921d` from archive SHA-256
`9af2fe9e343353f3086d4c57f499f5ac19f722f5cfa0bc19d31a8d276db5d59b`.
Both runners passed the required workspace gates, correctness example,
generated-code checks, binary verification, source verification, and strict
schedule checks. After relocation, each 29-file evidence manifest passed
`sha256sum -c`.

Each comparison used 12 AB/BA fresh-process pairs pinned to CPU 0, with six
pairs in each order. Each process timed eight passes over a deterministic
64 MiB input. The reported IQR covers process observations or paired-process
ratios in one run window. It is descriptive dispersion, not a confidence
interval or an ISA-family result.

## Steady timing

| Comparison and mode | AArch64 2b median [IQR] | x86-64 xlg median [IQR] |
| --- | ---: | ---: |
| scalar versus SIMD: `scalar_whole` | 354.917679 [354.349672–355.081213] ms | 160.821941 [160.718337–160.918346] ms |
| scalar versus SIMD: `simd_whole` | 69.420895 [69.396936–69.455050] ms | 26.716179 [26.708616–26.719455] ms |
| whole versus chunks: `dispatch_once` | 69.402648 [69.367809–69.418835] ms | 26.713255 [26.690742–26.730298] ms |
| whole versus chunks: `cached_chunks` | 71.472527 [71.462861–71.540418] ms | 29.773919 [29.758079–29.788809] ms |
| cached versus detect: `cached_chunks` | 71.478720 [71.464359–71.502230] ms | 29.754029 [29.741345–29.783443] ms |
| cached versus detect: `detect_chunks` | 71.402265 [71.393578–71.428374] ms | 30.538368 [30.497955–30.556370] ms |

## Paired results

The paired ratios divide the first named mode's steady time by the second's:

| Paired steady-time ratio | AArch64 median [IQR] | x86-64 median [IQR] |
| --- | ---: | ---: |
| scalar whole / SIMD whole | 5.110466 [5.094078–5.114599]x | 6.018989 [6.015627–6.023344]x |
| dispatch once / cached chunks | 0.970531 [0.970156–0.971282]x | 0.897286 [0.896360–0.898409]x |
| cached chunks / detect chunks | 1.001167 [1.000839–1.001327]x | 0.974973 [0.973987–0.975473]x |

Measured elapsed time supports two host-scoped conclusions. The selected SIMD
variant was faster than the controlled scalar path on both hosts. Dispatching
once for the whole buffer was faster than using the cached function pointer
for every 256-byte chunk on both hosts.

Repeated detection differed by host. On AArch64, detect chunks were slightly
faster than cached chunks in this run. On x86-64, cached chunks were faster.
The AArch64 target configuration included baseline `neon`, and its linked
resolver returned a constant function and kind. The x86-64 baseline did not
include AVX2, and its linked resolver checked Rust's feature cache and branched.
Those are generated-code observations. They are consistent with different
dispatch costs, but they do not prove the cause of either timing difference.
The small AArch64 detect advantage is not a general recommendation to repeat
detection.

The linked AArch64 SIMD kernel contained `cmeq`, `cnt`, and `addv`. The linked
x86-64 SIMD kernel contained `vpcmpeqb`, `vpmovmskb`, and `vzeroupper`.
The scalar controls remained scalar under builds that disabled LLVM loop and
SLP vectorization. This establishes code generation for these two binaries,
not performance for other CPUs or compiler versions.

No performance-monitoring-unit events, frequency residency, CPU isolation, or
concurrent host load were recorded. Absolute times and speedup factors must
not be compared as AArch64 versus x86-64 performance: the CPU models,
virtualization, topology, baseline features, binaries, and host state differ.
Read the [AArch64 record](2026-07-24-dev-dsk-ahrav-2b.md), the
[xlg record](2026-07-24-xlg.md), and the retained
[raw evidence](raw/8301b34/).
