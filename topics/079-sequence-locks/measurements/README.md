# Sequence-lock measurements, 2026-10-16

Measured source: `d52d5d744d75de976c2ceeed4aef522be5f4003a`. Both hosts used Rust 1.93.1, release defaults,
four readers, one potential writer, and CPUs 0-4 (distinct physical cores on
one socket). Threads could migrate within the set. Each host completed 12
warmups and 72 measured fresh processes. All six mode permutations appear once
per workload. Nominal duration was 300 ms; rates use actual time through drain.

Correctness: six unit tests, one doctest, Clippy, and the 7,230-schedule Python
oracle passed on both hosts. Every process checked every accepted pair and its
final state. These observations complement the all-SeqCst argument; they do
not verify weaker orderings.

Initial partial archives omitted other workspace members and failed Cargo
`--locked` before compilation. The final archive includes every member manifest
and Rust sources, preserving the committed lockfile. Its SHA-256 matched on both
hosts. No experiment source changed between the final runs. Local pilots are excluded.

## arm

Host: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, AArch64, ARM r1p1, 64 cores.

| Workload | Mode | Reads M/s median [min, max] | Writes/s median [min, max] | Failed attempts/read median | Fallback % median | Skipped slots range |
|---|---|---:|---:|---:|---:|---:|
| none | seq | 107.707 [107.253, 108.280] | 0 [0, 0] | 0.000000 | 0.0000 | 0-0 |
| none | fallback | 106.780 [96.535, 106.881] | 0 [0, 0] | 0.000000 | 0.0000 | 0-0 |
| none | rw | 11.163 [10.900, 12.307] | 0 [0, 0] | 0.000000 | 0.0000 | 0-0 |
| paced | seq | 107.871 [106.931, 108.516] | 9998 [9995, 9998] | 0.000000 | 0.0000 | 0-1 |
| paced | fallback | 106.536 [100.917, 106.692] | 9998 [7898, 9998] | 0.000000 | 0.0000 | 0-630 |
| paced | rw | 12.138 [10.704, 16.806] | 9998 [9997, 9998] | 0.000000 | 0.0000 | 0-0 |
| held | seq | 85.421 [74.126, 86.271] | 9998 [5442, 9998] | 0.649802 | 0.0000 | 0-1367 |
| held | fallback | 74.537 [74.362, 74.900] | 9998 [9997, 9998] | 0.004291 | 0.0536 | 0-0 |
| held | rw | 9.662 [7.966, 10.609] | 9998 [7367, 9998] | 0.000000 | 0.0000 | 0-746 |
| hot | seq | 52.971 [19.861, 59.455] | 4487639 [3294319, 5812297] | 0.000102 | 0.0000 | 0-0 |
| hot | fallback | 41.920 [22.990, 67.858] | 3251026 [1544421, 8534888] | 0.392482 | 0.8360 | 0-0 |
| hot | rw | 5.529 [4.404, 6.566] | 1003578 [740837, 1141671] | 0.000000 | 0.0000 | 0-0 |

Pairwise read-throughput selection uses >5% in all six paired blocks.
Both sequence modes beat RwLock in all four workloads on this host.
Neither sequence mode beats the other under that rule in any workload.

## xxl

Host: xxl resolved to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com, x86_64, Xeon Platinum 8488C, KVM.

| Workload | Mode | Reads M/s median [min, max] | Writes/s median [min, max] | Failed attempts/read median | Fallback % median | Skipped slots range |
|---|---|---:|---:|---:|---:|---:|
| none | seq | 115.834 [108.194, 115.858] | 0 [0, 0] | 0.000000 | 0.0000 | 0-0 |
| none | fallback | 112.920 [100.672, 113.959] | 0 [0, 0] | 0.000000 | 0.0000 | 0-0 |
| none | rw | 16.326 [13.288, 20.306] | 0 [0, 0] | 0.000000 | 0.0000 | 0-0 |
| paced | seq | 110.401 [100.097, 115.189] | 9997 [5048, 9998] | 0.001099 | 0.0000 | 0-1485 |
| paced | fallback | 112.219 [112.129, 113.654] | 9997 [9996, 9998] | 0.000814 | 0.0025 | 0-0 |
| paced | rw | 15.484 [11.828, 19.522] | 9997 [9008, 9998] | 0.000000 | 0.0000 | 0-297 |
| held | seq | 91.792 [90.722, 92.725] | 8512 [5042, 9998] | 0.489705 | 0.0000 | 0-1487 |
| held | fallback | 80.641 [79.981, 81.976] | 9998 [9997, 9998] | 0.003965 | 0.0496 | 0-0 |
| held | rw | 11.751 [10.147, 13.026] | 9998 [9997, 9998] | 0.000000 | 0.0000 | 0-0 |
| hot | seq | 20.791 [13.180, 34.416] | 2241974 [1715003, 2447932] | 1.024624 | 0.0000 | 0-0 |
| hot | fallback | 18.195 [11.188, 21.624] | 1975086 [1358045, 2348681] | 1.135632 | 2.8979 | 0-0 |
| hot | rw | 7.255 [6.230, 12.016] | 1202488 [794049, 3032179] | 0.000000 | 0.0000 | 0-0 |

Pairwise read-throughput selection uses >5% in all six paired blocks.
Both sequence modes beat RwLock in all four workloads on this host.
Retry-only beats fallback in the held workload (paired ratios 1.125-1.152).
Other sequence-mode comparisons remain unresolved. In held, retry-only writes
fell to a median 8,512/s and as low as 5,042/s; fallback sustained about 9,998/s.
This is a read-throughput winner under the declared writer policy, not a
joint-service or equal-achieved-update-rate winner.

## Interpretation and limits

The eight-attempt policy trades failed speculation for lock waiting. In the held
workload its median failed attempts/read were about 0.004 on both hosts, versus
0.650 on Arm and 0.490 on x86 for retry-only reads. This does not measure CPU
savings: clock checks, kernel parking and scheduling costs differ.

Paced cases expose scheduling variability: individual processes skipped up to
630 (Arm fallback paced), 1,367 (Arm seq held), 746 (Arm RwLock held),
1,485 (x86 seq paced), or 1,487 (x86 seq held) of about 3,000 nominal slots.
No repeats were discarded. Raw results retain every count, duration, order and
per-reader minimum. The hot workload gives joint closed-loop progress with
different write counts. Neither the rare-write ratio nor one median is a
portable recipe for choosing a retry budget.

No latency distributions, process CPU time, context-switch counts, or PMU events
were collected. Busy work under protection is not a preemption measurement.
No architecture-wide conclusion, wait-freedom, starvation bound, statistical
equivalence, or fastest production seqlock claim is supported.

Raw JSON includes each command. Host files include CPU topology, affinity and
toolchain. The initial archive failure was corrected without weakening locked
dependency validation; both required Linux measurements are complete.
