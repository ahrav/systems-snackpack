# Cross-host comparison: 2026-08-02

| Host | Tagged/raw ratio | 95% interval | Block log SD | Final CAS form |
| --- | ---: | ---: | ---: | --- |
| Resolved `xxl`, Xeon Platinum 8488C | 1.038854 | [1.038506, 1.039203] | 0.000528 | `lock cmpxchg` |
| Required Arm, part `0xd40` | 1.002938 | [1.001997, 1.003880] | 0.001478 | LSE `cas` |

Both runs used source commit `6b20b1f`, CPU 0, 5,000,000 iterations per fresh
process, 12 ABBA/BAAB treatment blocks, and six raw/raw A/A blocks. Each timed
iteration performed two successful 64-bit CAS operations on one private, hot,
uncontended atomic. Startup and warmup were outside the timed region. Both A/A
intervals included one.

Control caveat: the Arm A/B interval `[1.001997, 1.003880]` overlaps the Arm
A/A control interval `[0.999129, 1.002209]`, so the small Arm ratio is not
resolved above the run's order and temporal noise band; treat it as consistent
with no practical penalty on that host. Only the `xxl` ratio, roughly 13 times
the width of its control interval from one, is clearly resolved.

Measured: elapsed process-kernel time, process-block dispersion, host identity,
final code generation, and correctness outcomes. Inferred: on `xxl`, extra
integer work around the same two CAS operations is the likely source of the
resolved non-unit ratio; the Arm contrast is within its control band.
The experiment does not isolate individual instructions or measure hazard
scans, epoch advancement, RCU grace periods, allocation, destruction, stalled
readers, or contention. The ratio difference is specific to these two exact
host, binary, workload, and run windows.
