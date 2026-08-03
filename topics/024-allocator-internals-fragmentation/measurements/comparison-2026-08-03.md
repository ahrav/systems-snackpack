# Exact-source cross-host comparison

Both hosts ran archive commit `c7187b1` with the same probe hash, allocation
geometry, source-manifest hash, compile flags, schedule, and validation logic.
Each host contributed 12 four-process treatment blocks and four four-process
A/A blocks.

| Host | Compact RSS | Scattered RSS | Paired ratio [95% interval] | Paired difference [95% interval] |
|---|---:|---:|---:|---:|
| `xxl` x86-64 | 8,076 KiB | 73,348 KiB | 9.0826 [9.0809, 9.0842] | 65,272.2 KiB [65,270.8, 65,273.5] |
| AArch64 | 7,738 KiB | 73,008 KiB | 9.4443 [9.4309, 9.4578] | 65,269.8 KiB [65,255.6, 65,284.1] |

The medians are process observations. The ratios and differences are paired
estimates over block contrasts. Their t intervals cover block-to-block
variation in each recorded run window. They do not cover rebuilds, future
windows, other hosts, other glibc versions, other allocator policies, or other
workloads.

Measured controls matched on both hosts: requested live bytes were 4,194,304,
usable live bytes were 4,325,376, post-trim `uordblks` was 6,557,696, compact
and scattered median arena sizes were 6,561,792 and 73,400,320 bytes, and all
treatment rows reported `AnonHugePages: 0`. The final images preserved the
expected libc calls. Every source before/after manifest comparison passed.

The x86-64 A/A interval contained one. The AArch64 A/A interval was [1.00205,
1.00783], so label or period effects remained measurable there. This control
does not explain the approximately 9.44-fold treatment result, but it rejects
a claim that the Arm schedule removed all run-window bias.

The data show that scattered survivors were associated with much higher
post-trim residency under this controlled glibc layout. The equal allocator
accounting, larger retained arena, and larger anonymous RSS are consistent
with survivors preventing page release. The experiment does not locate each
object physically, prove a universal external-fragmentation ratio, or explain
the small cross-host ratio difference. No ISA or vendor-family conclusion is
justified.
