# Exact-source Linux observations, 2026-10-02

Source commit: `1351bd81ff34b33aced0e31688a299301b9e136b`. Both path-limited archive and exact runner were hashed
before transfer and verified remotely before execution. Extracted source hashes
match Git objects. The dependency-free topic causes Cargo to prune the workspace
lockfile; input and derived lock hashes are separate. Earlier runs with post-build
lock hashing were retained as rejected receipt attempts and excluded below.

Arm: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, aarch64, ARM implementer 0x41,
part 0xd40, variant 0x1, revision 1; 64 available CPUs; kernel
6.12.103-129.197.amzn2023.aarch64; rustc 1.98.1, LLVM 22.1.8.

xxl resolved at runtime to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com,
x86_64, Intel Xeon Platinum 8488C, 192 available CPUs; kernel
6.12.103-127.188.amzn2023.x86_64; rustc 1.98.0, LLVM 22.1.8.

Release opt-level=3 and `-C target-cpu=native`; no LTO. Both runs pinned to allowed
CPU 0. Host metadata includes uname, lscpu, toolchain, CPU flags, and Rust cfg.
These two particular builds and machines do not represent entire architectures.

## Correctness and generated code

Both hosts passed 11 unit tests and one doctest. Every process checked its scan and
four-worker morsel result against the oracle. Mask 63 sum: 7,715,099; mask 1 sum:
247,307,285. Exact-once concurrent claim coverage was tested for finite inputs and
morsel sizes, including empty and partial ranges and usize::MAX. This is not a
formal proof, memory-model exploration, NUMA experiment, or parallel-speedup test.

The row dispatch loop contains `blr` on Arm and an indirect `callq` on x86. Linked
images and compiler assembly were retained. Inspected fused loops use scalar
loads/branches; no SIMD acceleration is claimed. Batch boundaries are a software
execution contract independent of SIMD. Code shape does not establish why the
measured ratios differ; counters and interventions would be needed for attribution.

## Warm measurements

Each row below is six adjacent process pairs, three per order; 120 processes per
host including A/A controls. Each process uses 32 warm scan repetitions as one
sample. Ratios below one favor the treatment. Ranges are min/max across paired
ratios, not confidence intervals. No outliers were removed. See README for complete
controls, allocation, CPU-affinity, and first-scan limitations.

## arm

| Mask | Treatment | Batch | Pairs | Fused ns/row | Treatment ns/row | Paired treatment/fused median [min,max] |
|---:|---|---:|---:|---:|---:|---|
| 63 | row | 1024 | 6 | 0.970 | 1.905 | 1.962 [1.869, 1.973] |
| 63 | batch | 64 | 6 | 0.972 | 0.955 | 0.992 [0.966, 1.030] |
| 63 | batch | 1024 | 6 | 0.979 | 0.777 | 0.795 [0.782, 0.810] |
| 63 | batch | 16384 | 6 | 0.969 | 0.765 | 0.789 [0.780, 0.805] |
| 63 | fused | 1024 | 6 | 0.976 | 0.972 | 1.007 [0.982, 1.010] |
| 1 | row | 1024 | 6 | 3.978 | 5.850 | 1.471 [1.468, 1.473] |
| 1 | batch | 64 | 6 | 3.984 | 4.543 | 1.140 [1.138, 1.143] |
| 1 | batch | 1024 | 6 | 3.986 | 4.303 | 1.079 [1.077, 1.083] |
| 1 | batch | 16384 | 6 | 3.983 | 4.263 | 1.071 [1.068, 1.074] |
| 1 | fused | 1024 | 6 | 3.983 | 3.985 | 1.001 [0.997, 1.002] |

All first scans follow initialized and oracle-read inputs; they are not cold-cache samples.
process_ns: median 122.007 ms, range [39.931, 230.617] across all treatments (descriptive mixture).
setup_ns: median 7.663 ms, range [7.396, 8.366] across all treatments (descriptive mixture).
first_ns: median 3.081 ms, range [0.795, 6.240] across all treatments (descriptive mixture).


## xxl

| Mask | Treatment | Batch | Pairs | Fused ns/row | Treatment ns/row | Paired treatment/fused median [min,max] |
|---:|---|---:|---:|---:|---:|---|
| 63 | row | 1024 | 6 | 0.792 | 2.070 | 2.615 [2.597, 2.621] |
| 63 | batch | 64 | 6 | 0.791 | 0.951 | 1.203 [1.192, 1.213] |
| 63 | batch | 1024 | 6 | 0.792 | 0.763 | 0.959 [0.923, 1.009] |
| 63 | batch | 16384 | 6 | 0.792 | 0.701 | 0.887 [0.853, 0.901] |
| 63 | fused | 1024 | 6 | 0.793 | 0.793 | 1.001 [0.995, 1.011] |
| 1 | row | 1024 | 6 | 4.906 | 6.802 | 1.386 [1.381, 1.390] |
| 1 | batch | 64 | 6 | 4.908 | 5.280 | 1.077 [1.068, 1.080] |
| 1 | batch | 1024 | 6 | 4.912 | 5.076 | 1.034 [1.032, 1.041] |
| 1 | batch | 16384 | 6 | 4.908 | 5.079 | 1.037 [1.029, 1.041] |
| 1 | fused | 1024 | 6 | 4.894 | 4.912 | 1.004 [0.999, 1.005] |

All first scans follow initialized and oracle-read inputs; they are not cold-cache samples.
process_ns: median 139.253 ms, range [34.203, 264.036] across all treatments (descriptive mixture).
setup_ns: median 5.627 ms, range [5.586, 8.059] across all treatments (descriptive mixture).
first_ns: median 3.680 ms, range [0.716, 7.140] across all treatments (descriptive mixture).


## Selection result and limits

The chosen selection-buffer implementation changes relative performance with
selectivity and batch size. Compare each treatment to its own nearby baseline.
Row calls remained slower in these observations. A/A variation is visible above.
This does not rank database engines or prove a dispatch-only, cache, branch, or
instruction-set cause. The batch path includes allocation once per query call;
startup/oracle work is excluded from warm timing but preserved separately.

Retained replay assets and raw receipts: `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-065/2026-10-02-1351bd81`.
Input archive SHA-256: `5a8589dacfd7ab021e9d9b6d4accf04f8f6c7db11bf7ea52ab9d6ee4b6d0a995`.
Runner SHA-256: `2e8304cab313ae3c038871cacb137be744cd4d6144ba4596bd463b684a1eb063`.
`SHA256SUMS` in that directory seals every retained evidence file.
