# Cross-host comparison: 2026-07-30

Both successful runs used the same commit, archive, Rust version, native build
flags, 256 MiB cycle, 33,554,432 loads per process, fixed stopping rule, and
seed-recorded balanced schedule.

| Observed quantity | Required AArch64 host | Configured live x86 host |
|---|---:|---:|
| One-chain median, ns/load | 130.889 | 149.148 |
| Eight-chain median, ns/load | 16.951 | 18.207 |
| Paired one/eight estimate | 7.7170 | 8.1875 |
| 95% process-pair interval | [7.6994, 7.7347] | [8.0751, 8.3015] |
| Paired log-ratio SD | 0.00274 | 0.01654 |
| A/A estimate | 1.0017 | 1.0023 |

Within these run windows, the x86 host's one-chain median was 1.140 times the
AArch64 host's and its eight-chain median was 1.074 times the AArch64 host's.
These are unpaired descriptive cross-host ratios. The two within-host
confidence intervals do not turn the cross-host difference into an
architecture comparison.

The measured facts are the source identities, host evidence, generated
instruction bodies, and elapsed times. The result is consistent with eight
independent chains exposing enough addresses to overlap much of the observed
latency. It does not identify the limiting fill-buffer, miss-status,
translation, fabric, or memory-controller resource. Cache-line crossing and
store/load disambiguation were not treatments.

The required second literal endpoint was unreachable. The x86 values therefore
remain replacement evidence rather than completion evidence for that endpoint.
