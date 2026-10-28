# Measured results

Measured source and runner: `429f08d9807d318950a952bb5e0fc84238b95cc7`. `evidence/source-identity.json` records the digests of the measured files at that commit. Publication adds prose and retained evidence. The compiled sources (`src/lib.rs`, `examples/replay.rs`, `Cargo.toml`) and `scripts/demo.py` remain byte-identical. Commit `7ad1581` later changed one statement in `scripts/campaign.py`: the resident-order check against the oracle raises `RuntimeError` instead of using `assert`. Traces, scheduling, and timing code are unchanged.

All three hosts used Rust 1.93.1. Each completed four unit tests, one doctest, 160 measured fresh processes and 20 warmups. Native counts and final resident order agree with the independent Python oracle. Each sample processes eight fresh logical caches, each with the same 262,144-request trace.

## Exact request hits

| Workload | FIFO | LRU | Persistent frequency | Aged frequency |
| --- | ---: | ---: | ---: | ---: |
| hot | 262,080 (99.976%) | 262,080 (99.976%) | 262,080 (99.976%) | 262,080 (99.976%) |
| scan | 114,688 (43.750%) | 114,688 (43.750%) | 132,032 (50.366%) | 131,008 (49.976%) |
| shift | 261,888 (99.902%) | 261,888 (99.902%) | 130,944 (49.951%) | 253,824 (96.826%) |
| cycle | 0 (0.000%) | 0 (0.000%) | 259,984 (99.176%) | 258,241 (98.511%) |
| uniform | 4,046 (1.543%) | 4,044 (1.543%) | 4,130 (1.575%) | 4,041 (1.542%) |

These counts match on all hosts. The hot set ties. Persistent frequency wins hits in scan, cycle and this fixed uniform trace. FIFO and LRU tie for the best shift result. These rankings apply to the exact synthetic traces.

The second half of shift contains 131,072 requests to a disjoint 128-key set:
- fifo: 130,944 hits.
- lru: 130,944 hits.
- frequency: 0 hits.
- aged: 122,880 hits.

The cyclic trace exposes the admission effect. Admit-all FIFO and LRU replace the next-needed key and miss every request. Frequency admission retains a useful subset and bypasses other requests. All rejected requests still require backend service.

## Policy time

Cells show median [minimum, maximum] ns/request across eight fresh measured processes. One sample times 2,097,152 requests. These values exclude backend service.

### Arm Linux

Host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`. Architecture: `aarch64`.

| Workload | FIFO | LRU | Persistent frequency | Aged frequency |
| --- | ---: | ---: | ---: | ---: |
| hot | 2.61 [2.58, 2.64] | 5.28 [5.23, 5.29] | 6.33 [6.13, 6.61] | 6.14 [6.05, 6.22] |
| scan | 5.05 [4.94, 5.15] | 6.14 [6.11, 6.37] | 4.96 [4.88, 5.10] | 5.36 [5.32, 5.39] |
| shift | 2.62 [2.58, 2.71] | 5.28 [5.19, 5.34] | 5.16 [4.94, 5.23] | 6.10 [6.03, 6.20] |
| cycle | 6.97 [6.88, 7.10] | 7.00 [6.85, 7.12] | 6.24 [6.17, 6.55] | 6.26 [6.20, 6.31] |
| uniform | 7.52 [7.43, 7.60] | 7.53 [7.50, 7.61] | 4.23 [4.18, 4.30] | 4.95 [4.88, 5.04] |

Pairwise decisions under the predeclared all-eight-pairs 5% rule:

| Workload | FIFO/LRU | FIFO/frequency | FIFO/aged | LRU/frequency | LRU/aged | frequency/aged |
| --- | --- | --- | --- | --- | --- | --- |
| hot | fifo | fifo | fifo | lru | lru | unresolved |
| scan | fifo | tie | unresolved | frequency | aged | unresolved |
| shift | fifo | fifo | fifo | unresolved | lru | frequency |
| cycle | tie | frequency | aged | unresolved | aged | unresolved |
| uniform | tie | frequency | aged | frequency | aged | frequency |

### x86-64 Linux

Host: `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. Architecture: `x86_64`.

| Workload | FIFO | LRU | Persistent frequency | Aged frequency |
| --- | ---: | ---: | ---: | ---: |
| hot | 2.35 [2.33, 2.43] | 4.29 [4.05, 4.47] | 4.56 [4.54, 4.61] | 4.85 [4.78, 4.97] |
| scan | 4.13 [4.05, 4.18] | 5.38 [5.27, 5.41] | 3.99 [3.90, 4.16] | 4.41 [4.33, 4.56] |
| shift | 2.37 [2.36, 2.44] | 4.20 [4.13, 4.31] | 3.79 [3.74, 3.88] | 4.84 [4.76, 4.87] |
| cycle | 4.95 [4.79, 5.30] | 4.85 [4.74, 6.87] | 4.65 [4.59, 6.34] | 5.03 [4.86, 6.26] |
| uniform | 8.23 [8.13, 8.44] | 8.39 [8.20, 8.46] | 3.37 [3.24, 3.45] | 4.01 [3.90, 4.09] |

Pairwise decisions under the predeclared all-eight-pairs 5% rule:

| Workload | FIFO/LRU | FIFO/frequency | FIFO/aged | LRU/frequency | LRU/aged | frequency/aged |
| --- | --- | --- | --- | --- | --- | --- |
| hot | fifo | fifo | fifo | unresolved | lru | unresolved |
| scan | fifo | unresolved | unresolved | frequency | aged | frequency |
| shift | fifo | fifo | fifo | frequency | lru | frequency |
| cycle | unresolved | unresolved | unresolved | unresolved | unresolved | unresolved |
| uniform | tie | frequency | aged | frequency | aged | frequency |

### Local macOS arm64

Host: `c0c7db201688`. Architecture: `arm64`.

| Workload | FIFO | LRU | Persistent frequency | Aged frequency |
| --- | ---: | ---: | ---: | ---: |
| hot | 1.33 [1.16, 1.51] | 2.39 [2.26, 2.46] | 2.65 [2.61, 2.72] | 2.82 [2.78, 2.92] |
| scan | 2.66 [2.51, 2.79] | 2.82 [2.66, 3.06] | 2.19 [2.09, 2.37] | 2.52 [2.48, 2.58] |
| shift | 1.76 [1.29, 2.22] | 2.55 [2.47, 2.69] | 2.30 [2.18, 2.32] | 3.03 [2.90, 3.16] |
| cycle | 3.11 [3.01, 3.21] | 3.14 [3.11, 3.23] | 2.83 [2.64, 3.19] | 2.89 [2.75, 2.97] |
| uniform | 3.95 [3.63, 4.29] | 3.68 [3.40, 3.98] | 1.84 [1.72, 1.92] | 2.06 [1.92, 2.11] |

Pairwise decisions under the predeclared all-eight-pairs 5% rule:

| Workload | FIFO/LRU | FIFO/frequency | FIFO/aged | LRU/frequency | LRU/aged | frequency/aged |
| --- | --- | --- | --- | --- | --- | --- |
| hot | fifo | fifo | fifo | lru | lru | unresolved |
| scan | unresolved | frequency | unresolved | frequency | unresolved | frequency |
| shift | fifo | unresolved | fifo | frequency | lru | frequency |
| cycle | tie | unresolved | aged | unresolved | aged | unresolved |
| uniform | unresolved | frequency | aged | frequency | aged | unresolved |

## Conclusions and limits

FIFO wins policy time against all three alternatives for hot and shift on both Linux hosts. Persistent frequency wins policy time against all three for uniform on both. Scan and cycle have unresolved or tied pairs, so neither gets an overall timing winner.

Uniform has few hits for every policy. Frequency admission rejects many misses and therefore avoids resident-list replacement on those requests. This code-path difference is visible in the source. The experiment does not attribute timing differences to individual CPU events. A backend-cost decision must combine misses with policy work.

Linux runs pinned to CPU 0 within each inherited affinity set. Clock rate, thermals, competing tasks and SMT sibling activity were uncontrolled. Local macOS was unpinned. The timing rule describes these samples; it supplies no confidence interval or population-wide ranking.

Counters and arrays use the exact bounded-universe representation in README.md. Hashing, payloads, allocation, backend latency, concurrent throughput, variable-size policy quality, expiry, invalidation and asynchronous maintenance remain unmeasured. The frequency policies are exact-count teaching variants. The results do not rank production TinyLFU, S3-FIFO, SIEVE, or cache libraries.

## Validation

Both Linux hosts passed the exact-source topic tests, doctest and Clippy. Local topic tests and Clippy pass. Six workspace checks were run. The first workspace unit-test attempt failed the unchanged Topic 15 `pair_uses_identical_work` assertion because `second_ns` was zero. Its targeted rerun passed; the complete workspace rerun passed 522 tests. All six checks ultimately passed, including 149 doctests. The initial failure remains in the evidence.

The existing cache-policy skill covers this lesson. See evidence/plugin-audit.md for the inspected revision, owner, relevant cases and the no-change finding.
