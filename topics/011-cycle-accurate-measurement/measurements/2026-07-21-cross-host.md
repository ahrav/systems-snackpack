# 2026-07-21 cross-host note

> Superseded: candidate `4b00356` used an x86 ordering boundary not supported by
> the cited AMD architecture contract. Retained for provenance only. See the
> [supersession note](superseded-4b00356.md).

Both records use source and archive commit
`4b00356711a3934fd92ec62a099991a71ecd6529` and archive SHA-256
`d9952eb769dbf1d8716fa32cebca446e87fbf1948d4388645546896d60b05bc9`.
They use the same four batch sizes, 500 raw samples per timer and batch, 12 fresh
CPU-0-pinned processes, and the same three-block ABBA order schedule.

| Host record | Counter bracket | Batch-4096 reference-derived ns/op | Batch-4096 raw-clock ns/op | External process wall median |
| --- | --- | ---: | ---: | ---: |
| `dev-dsk-ahrav-2b` | `ISB; MRS CNTVCT_EL0; ISB` | `3.085239955` | `3.084960938` | `20.899653 ms` |
| `xlg` (`dev-dsk-ahrav-2c-a9191cb6`) | `MFENCE; RDTSC; MFENCE` | `3.522954993` | `3.518066406` | `1025.430262 ms` |

Raw counter ticks, raw-clock batch durations, and external process wall times
are measured. The table's per-operation values and counter-to-time conversions
are derived. Observed linked code also differs: the Arm recurrence is a single
dependent loop, while the x86-64 recurrence has an eight-step unrolled main
loop. The x86 external process-wall boundary includes ten 100 ms runtime
frequency-calibration intervals; Arm reads a fixed frequency from
`CNTFRQ_EL0`. The two process-wall intervals therefore include different work.
These records do not isolate a causal explanation for the steady-state ns/op
values.

The Arm MIDR and product identity are supplemental evidence captured read-only
from the same resolved host at `2026-07-21T15:07:22.370949341Z`, after the
benchmark. They are not part of the timed run.

Both timer pairs converge as batch size grows. This supports the fixed-bracket
amortization model within each record. It does not compare instruction-set
architectures, processor vendors, physical hosts, or core-cycle latency. The two
records expose different CPU identities, code generation, virtualization
boundaries, and timer-scale contracts.

Read the [Arm host record](2026-07-21-dev-dsk-ahrav-2b.md), the
[`xlg` host record](2026-07-21-xlg.md), and the [raw checksums](raw/4b00356/SHA256SUMS).
