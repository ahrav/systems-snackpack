# Delegation recall results

Commit `2d660a627913c3340d36e3b0df5b679ee54de637` supplied the model, oracle, example and the timing harness for the three-host table. The full Git archive had SHA-256 `a95a89e7c6f2f0d6fa49979eae141cf8d218511b036d576d0d6a7a668e402d7b`. Both Linux hosts verified the transfer before extraction.

## Correctness

Each host passed two unit tests, one doctest and all 10,708 Python oracle comparisons. The oracle computed the first valid release, open and write from positions in the history. It covered permutations, prefixes and a repeated writeback/open/write suffix for all four read/write grant and open combinations. An acknowledged recall left B waiting. B saw GOLD after a cooperative flush and return. Revocation allowed B to see BLUE when A had never flushed, or GOLD when A had already flushed. A late write on the old grant left B's RED intact.

## Cost experiment

The three-host table reports twenty samples per cell. Each sample ran in a fresh Python process. The policies alternated order within pairs. Startup, socket setup and one warm-up exchange were outside the timer. Both policies used one serial Unix socket service with a 500 µs sleep per exchange and `perf_counter_ns` timestamps. P50 is the median. P90 uses nearest rank. Each B open requested write access after a clean read delegation or ordinary server opens. Each host used its normal scheduler without CPU pinning. That harness answered B's OPEN on arrival, before the callback and return exchanges. Its last column is the span of the serial exchanges that start at B's request: one for plain and three for delegated.

| Host | A reopens | Policy | Exchanges | Total P50 / P90 (ms) | Span from B's request P50 / P90 (ms) |
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

On all three hosts, plain opens finished sooner with zero repeated opens. Delegation finished the batch sooner with eight repeats. The exchanges that start at B's request took longer with delegation in both workloads. This follows from the controlled exchange counts. A plain batch cost one or 17 exchanges. A delegated batch cost three. Real NFS latency also depends on the backchannel, server load, dirty bytes, retries, pipelining and the server's decision to grant a delegation.

## Held reply

The current harness holds B's reply until the service has answered the delegation return. B's open time then runs from B's request to B's reply. `test_cost.py` checks that message order. `cost.py` with SHA-256 `57a73b5738e157d4969effdccc6bc4343c2a6a53f8bca1eb24ba13e4d5e479cc` produced the rows below on a fourth host with the same method: twenty fresh-process samples per cell, alternating policy order, one warm-up exchange outside the timer and the normal scheduler.

| Host | A reopens | Policy | Exchanges | Total P50 / P90 (ms) | B open P50 / P90 (ms) |
|---|---:|---|---:|---:|---:|
| Linux Arm, second host | 0 | plain | 1 | 0.57 / 0.59 | 0.57 / 0.59 |
| Linux Arm, second host | 0 | delegated | 3 | 1.70 / 1.73 | 1.70 / 1.73 |
| Linux Arm, second host | 8 | plain | 17 | 9.75 / 9.86 | 0.57 / 0.58 |
| Linux Arm, second host | 8 | delegated | 3 | 1.72 / 1.74 | 1.72 / 1.74 |

B waited longer for its reply with delegation in both workloads: 1.70 ms and 1.72 ms at P50, against 0.57 ms for a plain open. These P50 values are within 0.02 ms of the three-exchange spans on the first Linux Arm host. The first three hosts have no held-reply samples.

## Hosts

| Host | Configuration |
|---|---|
| dev-dsk-ahrav-2b-7dc7bd93 | Linux 6.12.115, 64 AArch64 CPUs, Python 3.9.25 |
| xxl | Linux 6.12.115, Intel Xeon Platinum 8488C, x86-64, Python 3.9.25 |
| Local | Darwin 25.6.0, Apple M5 Pro, arm64, Python 3.13.16 |
| dev-dsk-ahrav-2b-a030d1dc | Linux 6.12.115, m7g.8xlarge, 32 Arm Neoverse V1 CPUs, 20 in the process affinity mask, Python 3.9.25 |

The first three hosts used rustc 1.93.1 and the default Cargo dev/test profiles. The fourth host ran only the Python cost harness. Raw samples are in `evidence/initial-*.csv` and `evidence/held-reply-arm.csv`. The experiments cover a state model and a local-socket cost model. Production recall latency, real NFS client/server interoperability, power-loss durability, partial writes, and server reboot recovery remain unmeasured.
