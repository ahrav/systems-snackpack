# Cross-host measurement boundary, 2026-07-18

Both hosts ran the same source archive, Rust 1.93.1, LLVM 21.1.8, native target
selection, 4 KiB base pages, 2 MiB PMD THPs, and the same process protocol.
Both kernels were Linux 6.12.94-123.180, with architecture-specific Amazon Linux
builds. Each comparison used 12 fresh, order-balanced process pairs, or 24
processes.

## Observations

| Comparison | Arm host | `xlg` |
| --- | ---: | ---: |
| Reach base/THP paired median | 1.131 | 5.162 |
| Reach 96.1% median interval | 1.112 to 1.154 | 5.018 to 5.249 |
| Permission 16/1 paired median | 1.028 | 1.810 |
| Permission 96.1% median interval | 0.883 to 1.179 | 1.781 to 1.852 |

The Arm PMU run retained many L1D TLB refill events under THP but reduced L2D
refills and DTLB walks from about 1.27 million to below 1,000. The `xlg` PMU
run reduced L2 DTLB misses from about 3.89 million to 5,056. These event names
and definitions differ, so their counts are not cross-host comparable.

The final guarded-allocation source also passed 200 fresh VMA-construction
tests on each host. Those repetitions cover the process-layout variation that
caused an unguarded aligned mapping to coalesce with an adjacent VMA in one CI
process.

Measured: the magnitude of the THP reach result and the reader-count result
differed between these two hosts. Inferred: both PMU records are consistent
with THP removing lower-level translation work, while the remaining translation
path differed. The experiment does not establish why, and it does not identify
an ISA, vendor, bare-metal, hypervisor, or kernel-wide effect.

The permission workload changes one page between read-only and read-write. Its
timer covers the complete `mprotect` pair and concurrent reader interference.
It is useful as mapping-change exposure, not as a direct TLB-shootdown latency
measurement.

Evidence roots:

- [`dev-dsk-ahrav-2b`](raw/52e7959/dev-dsk-ahrav-2b/)
- [`xlg`](raw/52e7959/xlg/)
- [SHA-256 manifest](raw/52e7959/SHA256SUMS)
