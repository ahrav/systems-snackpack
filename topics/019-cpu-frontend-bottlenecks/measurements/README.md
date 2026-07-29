# Measurement contract

The focused experiment builds two ELF executables from the same generated C
source and compiler options. Every generated leaf function has identical source
and control flow. The treatment changes only the requested function alignment:
16 bytes for `dense16` and 4096 bytes for `sparse4096`.

The treatment deliberately changes several frontend conditions together. It can
increase executable size, instruction-cache footprint, instruction-translation
footprint, and branch-target spacing. Timing therefore measures the effect of
this complete layout treatment. It does not identify one mechanism.

The timer uses `CLOCK_MONOTONIC_RAW` inside each process after an untimed warm-up.
Reported steady-state timing excludes compilation and process startup. Each
outcome contains 12 complete blocks and 48 fresh process invocations. Odd blocks
use `ABBA`; even blocks use `BAAB`. The analysis unit is the complete block, not
an inner call. The point estimate is the geometric `sparse4096/dense16` ratio
across block log contrasts. Its 95% Student-t interval covers block-to-block
variation in one run window.

An identical-artifact A/A run uses hard links to one dense executable and the
same schedule. It checks label, launch-path, and analysis symmetry. One A/A run
does not estimate a false-positive rate.

Performance-counter passes use separate fresh processes and balanced order.
They are descriptive mechanism evidence, not the paired timing estimand. Retain
unsupported events, multiplexing fractions, literal zero counts, and failed
attempts. A zero virtual PMU alias is not evidence that the event did not occur.

Each Linux record applies only to its source commit, archive hash, per-file
manifest, ELF hashes, host, selected CPU, kernel, toolchain, target flags,
workload, and run window. The before and after source manifests must match.
Archive mode records `git diff --check` as not applicable because an extracted
Git archive has no index; the named commit passes that gate before archiving.

The retained records use runtime aliases and resolved host identities:

- `xxl`: required x86-64 target for this round.
- `alg`: required AArch64 target for this round.

Neither result generalizes to an ISA, processor vendor, instance family, or
future host state.

Records:

- [`xxl` x86-64](2026-07-29-linux-x86-64.md)
- [`alg` AArch64](2026-07-29-linux-aarch64.md)
- [Cross-host summary](2026-07-29-linux-cross-host.md)
- [Raw archive identities](raw/cf1b205/README.md)
