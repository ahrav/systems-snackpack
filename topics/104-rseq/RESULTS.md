# Exact-source results

Tested commit: `0754c64d9720457731d194dbace1e4c4d32011f5`.

Linux GCC 11.5.0, -O2 -std=c11 -pthread. Rust 1.93.1.
Arm host: AArch64. xxl: x86_64 Intel Xeon Platinum 8488C.

Each host ran 93 fresh processes: 27 small/empty correctness runs,
9 warmups, 54 timing runs, and 3 stress runs. All exact totals passed.
The Rust serial event-list oracle checks 16,384 scenarios; 2 unit tests
and 1 doctest passed on macOS arm64 and both Linux hosts.

Times are wall nanoseconds per total completed increment: throughput reciprocals,
not single-operation latency. Median [minimum, maximum], six balanced orders.

| Host | Workers / CPUs | rseq | TLS | Shared atomic |
|---|---:|---:|---:|---:|
| arm | 1 / 1 | 1.937 [1.933, 1.962] | 1.936 [1.931, 1.951] | 5.306 [5.304, 5.324] |
| arm | 8 / 8 | 0.243 [0.243, 0.243] | 0.242 [0.242, 0.243] | 13.061 [11.413, 14.201] |
| arm | 8 / 2 | 0.966 [0.965, 0.966] | 0.966 [0.965, 0.968] | 11.191 [10.643, 12.802] |
| xxl | 1 / 1 | 2.052 [1.892, 2.361] | 1.685 [1.513, 1.870] | 5.888 [5.660, 6.258] |
| xxl | 8 / 8 | 0.254 [0.245, 0.262] | 0.280 [0.248, 0.293] | 20.173 [16.726, 24.526] |
| xxl | 8 / 2 | 1.017 [0.994, 1.066] | 0.954 [0.835, 1.053] | 18.233 [16.205, 19.985] |

xxl stress retries: 617, 810, 610. Each run totals 800,000.

Both sharded methods beat shared atomics by more than 5% in every paired
round in all six host/workload cells. Neither sharded method beats the other
by 5% in every pair in any cell. Arm is a practical tie; x86 remains unresolved.
Selecting the smallest median alone would overstate the evidence.

Workers use the first allowed CPU IDs: 0 for one worker, 0..7 for eight CPUs,
and 0..1 for oversubscription. Each timed worker performs 3,000,000 increments.
The six method permutations balance order. A warmup is a separate process.
The timer includes launch/final barrier overhead and excludes allocation, thread
creation, registration, joining and final aggregation. Per-worker TLS is volatile;
the rseq helper includes a function call, CPU check, descriptor stores and retry.
This experiment compares these concrete implementations, including that overhead.

All Arm stress runs total 800,000 with 739, 748, and 726 retries.
Stress mixes same-CPU preemption, signals, migration and CPU-check mismatches;
the retry count does not distinguish these causes or prove every boundary.
The finite Rust model covers the stale-read interruption pattern only.

128-byte slot stride reduces adjacent sharing; host clocks, load, thermals,
SMT sibling activity, and physical placement were uncontrolled. No PMU causal
attribution was collected. macOS runs the portable model only. Live snapshots,
allocator throughput, memory footprint and process-crash durability are unmeasured.
The allocated native array is CPU_SETSIZE slots; real deployments must account
for supported CPU-ID ranges and registry overhead.
