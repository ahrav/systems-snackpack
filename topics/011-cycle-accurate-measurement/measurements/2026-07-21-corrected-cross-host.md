# 2026-07-21 corrected cross-host note

Both records use source and archive commit
`5117e64d5c5df6ef1615749cacb95eabe38956c0` and archive SHA-256
`8a8ce53a63029ad3b6512b4f3787ae12a57d326af71a0d97420045ff8da3b6cc`.
They use four batch sizes, 500 raw samples per timer and batch, 12 fresh
CPU-0-pinned processes, and the same three-block ABBA schedule.

| Host record | Counter endpoint | Batch-65,536 reference-derived ns/op | Batch-65,536 raw-clock ns/op | External process wall median |
| --- | --- | ---: | ---: | ---: |
| `dev-dsk-ahrav-2b` | `ISB; MRS CNTVCT_EL0; ISB` | `3.077450707` | `3.077438354` | `210.354986 ms` |
| `xlg` (`dev-dsk-ahrav-2c-a9191cb6`) | `RDTSCP; ...; CPUID` | `3.526778161` | `3.513793945` | `1244.934887 ms` |

Raw counter ticks, raw-clock batch durations, and individual process wall
durations are measured. Per-operation values, time conversions, process
summaries, and ratios are derived. The observed final linked code differs: the
Arm recurrence is one
dependent loop; the x86 recurrence has an eight-step unrolled main loop. The
x86 process-wall boundary includes ten 100 ms frequency-calibration intervals;
Arm reads `CNTFRQ_EL0`. The wall intervals therefore include different work.

At the largest tested batch, each host's median ratio was closest to 1 among
its four tested batch sizes. That pattern is consistent with fixed
endpoint-cost amortization, but it does not establish the endpoint cost as the
only cause.
The two largest-batch values
are not an architecture comparison: CPU identity, virtualization, generated
code, clock contract, and host state differ.

Read the [corrected Arm record](2026-07-21-corrected-arm.md), the
[corrected xlg record](2026-07-21-corrected-xlg.md), the
[superseded-candidate note](superseded-4b00356.md), and the
[raw checksums](raw/5117e64/SHA256SUMS).
