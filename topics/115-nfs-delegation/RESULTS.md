# Delegation recall results

Commit `2d660a627913c3340d36e3b0df5b679ee54de637` supplied the model, oracle, timing harness and example. The full Git archive had SHA-256 `a95a89e7c6f2f0d6fa49979eae141cf8d218511b036d576d0d6a7a668e402d7b`. Both Linux hosts verified the transfer before extraction.

## Correctness

Each host passed two unit tests, one doctest and all 10,708 Python oracle comparisons. The oracle computed the first valid release, open and write from positions in the history. It covered permutations, prefixes and a repeated writeback/open/write suffix for all four read/write grant and open combinations. An acknowledged recall left B waiting. B saw GOLD after a cooperative flush and return. Revocation allowed B to see BLUE when A had never flushed, or GOLD when A had already flushed. A late write on the old grant left B's RED intact.

## Cost experiment

The table reports twenty samples per cell. Each sample ran in a fresh Python process. The policies alternated order within pairs. Startup, socket setup and one warm-up exchange were outside the timer. Both policies used one serial Unix socket service with a 500 µs sleep per exchange and `perf_counter_ns` timestamps. P50 is the median. P90 uses nearest rank. Each B open requested write access after a clean read delegation or ordinary server opens. Each host used its normal scheduler without CPU pinning.

| Host | A reopens | Policy | Exchanges | Total P50 / P90 (ms) | B open P50 / P90 (ms) |
|---|---:|---|---:|---:|---:|
| Linux Arm | 0 | plain | 1 | 0.58 / 0.58 | 0.57 / 0.58 |
| Linux Arm | 0 | delegated | 3 | 1.72 / 1.72 | 1.72 / 1.72 |
| Linux Arm | 8 | plain | 17 | 9.72 / 9.75 | 0.57 / 0.57 |
| Linux Arm | 8 | delegated | 3 | 1.72 / 1.72 | 1.72 / 1.72 |
| Linux x86-64 | 0 | plain | 1 | 0.57 / 0.58 | 0.57 / 0.58 |
| Linux x86-64 | 0 | delegated | 3 | 1.72 / 1.73 | 1.72 / 1.73 |
| Linux x86-64 | 8 | plain | 17 | 9.70 / 9.75 | 0.57 / 0.58 |
| Linux x86-64 | 8 | delegated | 3 | 1.72 / 1.72 | 1.71 / 1.72 |
| macOS Arm | 0 | plain | 1 | 0.77 / 0.78 | 0.77 / 0.78 |
| macOS Arm | 0 | delegated | 3 | 2.30 / 2.33 | 2.30 / 2.33 |
| macOS Arm | 8 | plain | 17 | 12.89 / 13.00 | 0.76 / 0.77 |
| macOS Arm | 8 | delegated | 3 | 2.30 / 2.32 | 2.30 / 2.32 |

On all three hosts, plain opens finished sooner with zero repeated opens. Delegation finished the batch sooner with eight repeats. B itself waited longer with delegation in both workloads. This follows from the controlled exchange counts. A plain batch cost one or 17 exchanges. A delegated batch cost three. Real NFS latency also depends on the backchannel, server load, dirty bytes, retries, pipelining and the server's decision to grant a delegation.

| Host | Configuration |
|---|---|
| dev-dsk-ahrav-2b-7dc7bd93 | Linux 6.12.115, 64 AArch64 CPUs, Python 3.9.25 |
| xxl | Linux 6.12.115, Intel Xeon Platinum 8488C, x86-64, Python 3.9.25 |
| Local | Darwin 25.6.0, Apple M5 Pro, arm64, Python 3.13.16 |

All three used rustc 1.93.1 and the default Cargo dev/test profiles. Raw samples are in `evidence/initial-*.csv`. The experiments cover a state model and a local-socket cost model. Production recall latency, real NFS client/server interoperability, power-loss durability, partial writes, and server reboot recovery remain unmeasured.
