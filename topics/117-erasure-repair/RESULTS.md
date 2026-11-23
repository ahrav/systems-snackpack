# Reconstruction measurements

At source `9d93411209e70f775bd343b2bc484f6ef5066b1b`, each host passed two unit tests, one doctest, the runnable byte example and an independent bit-matrix oracle. The oracle checked 18 encoded fragments, all 1,024 code/mask combinations and 4,608 missing-target decisions. Both layouts recover every zero-, one- and two-erasure pattern. RS recovers all 84 triples. This LRC recovers 64. These are counts of patterns, not estimates of their probabilities.

Each timing cell has 20 new processes, with 10 RS-first and 10 LRC-first pairs. Each process uses Rust 1.93.1, Cargo release defaults, a fixed pseudo-random stripe, one 1 MiB output, precomputed coefficient tables, one warm reconstruction and eight timed reconstructions. Reported times are milliseconds per reconstruction within a sample. P90 is the 18th sorted sample. Processes use the host scheduler and default CPU placement.

| Host and missing fragment | RS median | RS P90 | LRC median | LRC P90 | Median paired RS/LRC |
|---|---:|---:|---:|---:|---:|
| Apple M5 Pro, D0 | 1.602 | 1.653 | 0.066 | 0.068 | 24.26 |
| Apple M5 Pro, G | 1.598 | 1.625 | 1.599 | 1.639 | 1.00 |
| Linux AArch64, D0 | 3.587 | 3.595 | 0.134 | 0.136 | 26.76 |
| Linux AArch64, G | 3.585 | 3.592 | 3.585 | 3.593 | 1.00 |
| Linux Xeon Platinum 8488C, D0 | 3.314 | 3.832 | 0.255 | 0.290 | 12.79 |
| Linux Xeon Platinum 8488C, G | 3.416 | 3.955 | 3.429 | 5.024 | 0.99 |

The Linux systems ran Amazon Linux kernel 6.12.115 with 64 AArch64 or 192 x86-64 logical CPUs. The Arm host reported vendor ARM and model 1. The Mac ran Darwin 25.6.0. Timing excludes stripe generation, allocation, plan construction, integrity checks and destination I/O.

For D0 the helper interface delivered exactly 6 MiB for RS and 3 MiB for LRC. LRC finished first in all 20 pairs per host. It runs direct XOR on three fragments. This scalar RS implementation performs indexed byte lookups for weighted inputs. The large time ratios depend on those kernels and the host. Production SIMD codecs can change them.

For G the helper interface delivered 6 MiB for both, with identical coefficients and reconstruction steps. Median paired ratios were within 1% of 1 on each host. Call this workload a tie at median resolution. The x86 P90s vary more. The samples measure resident buffers. Remote traffic figures assume every helper sends one full fragment to a separate rebuild host. Cross-rack traffic and service latency require placement and live I/O measurements.
