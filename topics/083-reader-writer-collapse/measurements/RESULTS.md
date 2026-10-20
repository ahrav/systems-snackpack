# Topic 083 results

Measured source: `7589a370efcf2ee2e41b7378352325edec68e373`. Results are descriptive shared-host comparisons, not confidence bounds.

Timing is wall time per completed request, including lock operations, computation, start barrier and joins. Checksums are verified after timing. Timed cells have no writers.

## arm-final

dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com; Linux-6.12.111-136.204.amzn2023.aarch64-aarch64-with-glibc2.34.

Rust 1.93.1 / LLVM 21.1.8. Worker CPUs: [0, 1, 2, 3, 4, 5, 6, 7]. Each worker affinity read back as a singleton.

| Readers | Rounds | Mutex ns/op: median [min,max] | RwLock | Copy then release | Pairwise result |
|---:|---:|---|---|---|---|
| 1 | 0 | 15.24 [15.21, 15.52] | 17.31 [17.22, 17.38] | 16.05 [15.99, 16.14] | mutex beats rwlock; mutex/snapshot unresolved; snapshot beats rwlock |
| 1 | 256 | 333.96 [333.35, 335.80] | 335.54 [334.86, 337.14] | 346.15 [345.30, 356.14] | mutex ~ rwlock; mutex/snapshot unresolved; rwlock/snapshot unresolved |
| 4 | 0 | 81.31 [71.55, 89.06] | 74.82 [63.66, 83.55] | 59.78 [55.87, 75.08] | mutex/rwlock unresolved; snapshot beats mutex; rwlock/snapshot unresolved |
| 4 | 256 | 570.03 [495.83, 588.83] | 98.30 [97.83, 101.05] | 109.67 [96.18, 125.21] | rwlock beats mutex; snapshot beats mutex; rwlock/snapshot unresolved |
| 8 | 0 | 90.70 [82.50, 103.83] | 85.27 [76.02, 99.18] | 88.68 [72.14, 95.80] | mutex/rwlock unresolved; mutex/snapshot unresolved; rwlock/snapshot unresolved |
| 8 | 256 | 621.81 [593.61, 625.40] | 50.61 [48.62, 55.44] | 102.38 [90.18, 109.56] | rwlock beats mutex; snapshot beats mutex; rwlock beats snapshot |

A/A mechanical identity and checksums pass; the two timing observations are 74.32, 74.97 ns/op. This is not a null calibration or a noise floor.

## xxl-final

dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com; Linux-6.12.111-136.204.amzn2023.x86_64-x86_64-with-glibc2.34.

Rust 1.93.1 / LLVM 21.1.8. Worker CPUs: [0, 1, 2, 3, 4, 5, 6, 7]. Each worker affinity read back as a singleton.

| Readers | Rounds | Mutex ns/op: median [min,max] | RwLock | Copy then release | Pairwise result |
|---:|---:|---|---|---|---|
| 1 | 0 | 13.65 [13.60, 13.69] | 18.67 [18.60, 18.79] | 16.18 [16.15, 16.26] | mutex beats rwlock; mutex beats snapshot; snapshot beats rwlock |
| 1 | 256 | 356.05 [355.12, 357.59] | 358.97 [358.19, 361.54] | 354.61 [354.06, 357.44] | mutex ~ rwlock; mutex ~ snapshot; rwlock ~ snapshot |
| 4 | 0 | 153.40 [138.37, 167.20] | 93.98 [66.98, 121.33] | 86.87 [57.17, 104.31] | rwlock beats mutex; snapshot beats mutex; rwlock/snapshot unresolved |
| 4 | 256 | 556.21 [532.70, 593.49] | 120.12 [114.14, 126.46] | 109.11 [89.40, 117.33] | rwlock beats mutex; snapshot beats mutex; rwlock/snapshot unresolved |
| 8 | 0 | 152.47 [144.32, 161.12] | 99.16 [68.39, 105.37] | 68.22 [45.95, 91.43] | rwlock beats mutex; snapshot beats mutex; rwlock/snapshot unresolved |
| 8 | 256 | 673.02 [658.03, 695.75] | 129.29 [87.47, 141.94] | 51.30 [47.50, 60.64] | rwlock beats mutex; snapshot beats mutex; snapshot beats rwlock |

A/A mechanical identity and checksums pass; the two timing observations are 114.44, 102.62 ns/op. This is not a null calibration or a noise floor.

## Validation and limits

Each host: six Rust tests, one doctest, 3,420 independent schedule cases and 48 independent arithmetic cases pass. All 128 process checksums pass (2 A/A, 18 warmups, 108 measurements).

Six repetitions use every candidate permutation and reverse cell order on alternating repetitions. A pairwise winner needs >5% improvement in every paired repetition; a practical tie needs all ratios within 5%. Everything else remains unresolved. These rules describe this sample, without a statistical population claim.

The model demonstrates writer gating and reader-preference writer delay. The benchmark measures only read-only scaling and guard-scope alternatives. No native writer-tail, production, coherence-counter, or architecture-wide claim. Shared-host interference, scheduling, barrier/join overhead and warm-cache state remain possible causes. CPU topology is guest-visible; memory was not NUMA-bound.

Initial remote attempts used each host default toolchain and were rejected before build or timing (Arm 1.98.1, x86 1.99.0). They are retained outside the repository. Final runs explicitly used `rustup run 1.93.1 python3 experiment/run.py OUTPUT`. No measured samples were discarded.

Candidate dispatch and generated code contribute to these complete-operation costs. The zero-round workload is not a pure lock-latency measurement. Linked assembly confirms compute precedes guard release in the held-guard candidates and follows release in the copy candidate.

Repository CSV line endings and assembly trailing spaces are normalized for review. Original byte streams, full command logs and binaries are retained in the external evidence archive.
