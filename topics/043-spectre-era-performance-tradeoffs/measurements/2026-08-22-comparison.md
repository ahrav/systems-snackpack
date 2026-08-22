# Cross-host comparison: 2026-08-22

Both required targets passed exact-source validation, unit and documentation
tests, checksum equivalence, generated-code ordering, the same-treatment A/A
screen, the fixed
24-block schedule, summary recomputation, and receipt hashing.

The A/A screen ran the plain implementation under labels `a` and `b` in eight
alternating paired blocks. It checks label and position bias before comparing
different implementations.

| Host | mask/plain | Paired 95% interval | barrier/plain | Paired 95% interval |
|---|---:|---:|---:|---:|
| Arm implementer `0x41`, part `0xd40` | 0.38021 | [0.37413, 0.38639] | 2.75021 | [2.69458, 2.80699] |
| `xxl`, Intel Xeon Platinum 8488C | 0.35030 | [0.34939, 0.35120] | 1.41674 | [1.41312, 1.42037] |

Measured: these ratios describe 24 paired fresh-process blocks per host. The
fixed stream produced 49.999635% invalid indices from its committed seed. The
generated code showed the intended dependency or post-check barrier on each
host.

Inferred: one plausible explanation for masking beating the plain path is that
this workload makes the plain bounds branch hard to predict while the mask
creates a safe address. The receipts contain no branch-miss counters, so they
do not prove that mechanism. The larger Arm barrier ratio is also only an
observation of these complete host, compiler, and instruction sequences. It is
not an AArch64-versus-x86 instruction-set comparison.

Not tested: exploitability, secret disclosure, mitigation completeness,
production traffic, simultaneous multithreading interference, scheduler
migration, power-state control, or another CPU model.
