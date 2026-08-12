# Two-host comparison: e88c363

Both required hosts ran source commit
`e88c3633d6a12b9787c31ec0612bccd810d5533d` from source archive Secure Hash
Algorithm 256-bit (SHA-256) digest
`57244a793084ead6db1b4598736046fed39843e0712a51c214fefc5dd1215b9a`.
They used Rust 1.93.1, the same deterministic data and queries, the same process
schedule, and logical CPU 0 for every sequentially launched timed process.
Every generic and native process produced checksum `1003443739073492248`.

## Native-build comparison

| Exact host | Narrow median | Covering median | Geometric narrow/covering ratio | Nominal 96.14% sign interval |
|---|---:|---:|---:|---:|
| Required Arm host | 381.856547 nanoseconds | 314.163466 nanoseconds | 1.220380 | [1.202430, 1.233358] |
| Runtime-resolved `xxl` host | 328.665009 nanoseconds | 336.644875 nanoseconds | 0.975917 | [0.974406, 0.981197] |

The result changed direction. The covering layout was faster on the measured
Arm host, while the narrow-plus-payload layout was slightly faster on the
measured `xxl` host. The generic builds had the same within-host directions,
with ratios `1.233395` and `0.986377` respectively.

This is the useful result: removing a base-payload lookup is not free, and
making sorted entries wider is not free. Which cost dominates depends on the
exact binary, data, processor, and run window. The linked code shows the narrow
path's extra locator-based load and the covering path's 24-byte binary-search
stride. Those observations are consistent with the timing difference, but do
not identify its cause. No cache-miss, branch-miss, translation-lookaside-
buffer, or other hardware event was measured.

The sign intervals have exact stated coverage only under independent,
exchangeable, continuous block contrasts. Processes shared host conditions, so
the reported coverage is nominal and covers only the twelve retained
within-host block contrasts. It does not cover hosts, compiler versions,
processor families, instruction-set architectures, data distributions, or
database workloads.

## Decision boundary

For a real index, estimate whether saved base-row accesses outweigh wider leaf
pages, lower cache residency, write amplification, and any internal-entry
growth. Then measure with the target engine and realistic visibility, update,
and residency conditions. These two kernels demonstrate the tradeoff; they do
not choose an index for a production query.
