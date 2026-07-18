# Cross-host measurement boundary, 2026-07-18

Both hosts ran the same source archive, Rust 1.93.1, LLVM 21.1.8, native target
selection, 4 KiB base pages, 2 MiB PMD THPs, and the same process protocol.
Both kernels were Linux 6.12.94-123.180, with architecture-specific Amazon Linux
builds. Each comparison used 12 fresh, order-balanced process pairs, or 24
processes.

## Observations

| Comparison | Arm host | `xlg` |
| --- | ---: | ---: |
| Reach base/THP paired median | 1.119 | 5.035 |
| Reach 96.1% median interval | 1.091 to 1.141 | 4.794 to 5.108 |
| Permission 16/1 paired median | 1.119 | 1.571 |
| Permission 96.1% median interval | 0.949 to 1.310 | 1.417 to 1.607 |

The Arm PMU run retained many L1D TLB refill events under THP but reduced L2D
refills and DTLB walks from about 1.25 million to below 1,000. The `xlg` PMU
run reduced L2 DTLB misses from about 3.84 million to 5,392. These event names
and definitions differ, so their counts are not cross-host comparable.

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

- [`dev-dsk-ahrav-2b`](raw/2a3b412/dev-dsk-ahrav-2b/)
- [`xlg`](raw/2a3b412/xlg/)
- [SHA-256 manifest](raw/2a3b412/SHA256SUMS)
