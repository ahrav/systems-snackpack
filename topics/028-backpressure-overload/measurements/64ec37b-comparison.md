# Two-host comparison: `64ec37b`

Both required Linux targets ran the same pushed source commit, deterministic
source archive, fixed schedule, outcome prefix, retry limits, key digest,
logical population, waiter cap, origin cap, and native build flags. Each host
calibrated its CPU-work iterations once and then held that value fixed across
all 48 analysis processes and both semantic controls.

| Retained result | Required Arm | Runtime-resolved `xxl` |
| --- | ---: | ---: |
| Calibrated mean attempt | `200,346 ns` | `199,080 ns` |
| Controlled/naive `burst_ns` | `0.132139` | `0.123703` |
| 95% t interval | `[0.123393, 0.141505]` | `[0.108537, 0.140989]` |
| Log-ratio block SD | `0.0819153` | `0.156449` |
| Controlled A/A B/A | `0.991313` | `0.991541` |
| Naive attempts per process | `192` | `192` |
| Controlled attempts per process | `3` | `3` |
| Saturation completed / shed | `64 / 64` | `64 / 64` |
| One-token exhausted results | `64` | `64` |

The physical-attempt ratio is exactly `3/192 = 0.015625` on both hosts. With
four origin permits, work alone gives an idealized controlled/naive lower-bound
ratio near `C/N = 4/64 = 0.0625` for this constructed wave. The measured ratios
are larger because `burst_ns` also contains start, decision, and end barriers,
thread scheduling, permit bookkeeping, follower wakeup, timestamps, and other
fixed process work. The work-only expression is a cost-model inference, not a
timing prediction or acceptance threshold.

ABBA/BAAB placement addresses additive position drift within a four-process
block. It does not remove thermal, cache, kernel, scheduler, nonlinear, or
cross-block carryover. The A/A blocks are descriptive mechanical diagnostics;
four blocks neither establish a false-positive rate nor define a noise floor.

Analyze the hosts separately. Their binaries, CPU work iterations, kernels,
clocks, and machines differ. The two results do not compare Arm with x86,
vendors, instruction sets, or fleet performance. They establish only that the
one-key count invariants and the predeclared timing contrast reproduced for the
two retained host-specific artifacts and run windows.

Review-hardening commits merged after these runs changed the probe, analyzer,
and runner sources. This promoted result therefore describes only the
`64ec37b` tree, binary, and analysis; the current tree has not been rerun on
either host and holds no promoted result of its own.

Evidence:

- [Arm record](64ec37b-arm.md)
- [`xxl` record](64ec37b-xxl.md)
- [Outer archive hashes](raw/64ec37b/SHA256SUMS)
