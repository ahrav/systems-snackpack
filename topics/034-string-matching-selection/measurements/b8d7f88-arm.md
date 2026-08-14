# Arm exact-source record for `b8d7f88`

The literal required Arm host passed correctness, workspace, timing, receipt,
and linked-code gates for source commit
`b8d7f88a25aede60fb589099239c771285450293`.

## Execution boundary

- SSH target and resolved host:
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Run window: 2026-08-13 07:37:00 through 07:40:49 PDT, based on retained
  result-file modification times
- Architecture and CPU evidence: `aarch64`, ARM vendor, model 1, stepping
  `r1p1`, 64 available CPUs, one non-uniform memory access (NUMA) node
- Reported features include Advanced SIMD (ASIMD, commonly called Neon) and
  Scalable Vector Extension (SVE)
- Kernel: `6.12.95-124.187.amzn2023.aarch64`
- Toolchain: Rust 1.93.1, Cargo 1.93.1, LLVM 21.1.8, GCC 11.5.0, GNU
  `objdump` 2.41; `clang` was unavailable
- Native flags: `-C target-cpu=native -C debuginfo=1`
- Pinned CPU: 0, the first CPU in the process's allowed `0-63` mask
- Source archive SHA-256:
  `5a2807443d9ef14ba3ce7a971787654db1879a3b52d227be404af8dbea4e640c`
- Timing binary SHA-256:
  `97d24c72983573ce67adaad3a460f3049e7ee49b99cf00274ae3d53ffa7bc61b`

Generic and native `verify` runs each checked 42,203 input pairs and all five
benchmark cases. Every required workspace command passed. The runner retained
112 fresh processes and 1,120 timing rows. The independent Python 3.9.25
validator recomputed every block contrast and returned `CHECK=PASS`.

## Candidate-to-left-to-right ratios

Each cell reports `geometric mean ratio (sample SD of log ratio)`. A ratio below
one favors the candidate. Each candidate cell has 12 complete-block contrasts;
the standard deviation describes variation among those contrasts in this run
window.

| Case | Mode | Horspool / left-to-right | KMP / left-to-right |
| --- | --- | ---: | ---: |
| uniform absent, 32 bytes | reuse | 0.319 (0.0042) | 1.992 (0.0003) |
| uniform absent, 32 bytes | one-shot | 0.318 (0.0030) | 1.993 (0.0004) |
| skewed text, late 16 bytes | reuse | 0.639 (0.0027) | 1.790 (0.0114) |
| skewed text, late 16 bytes | one-shot | 0.640 (0.0036) | 1.775 (0.0058) |
| repeated-prefix trap, 32 bytes | reuse | 1.545 (0.0021) | 0.951 (0.0036) |
| repeated-prefix trap, 32 bytes | one-shot | 1.545 (0.0019) | 0.950 (0.0038) |
| repeated-suffix trap, 32 bytes | reuse | 49.004 (0.0029) | 1.992 (0.0010) |
| repeated-suffix trap, 32 bytes | one-shot | 49.069 (0.0058) | 1.998 (0.0091) |
| tiny late match, 4 bytes | reuse | 2.458 (0.0098) | 1.963 (0.0111) |
| tiny late match, 4 bytes | one-shot | 2.521 (0.0017) | 1.999 (0.0025) |

The four-block same-method schedule checks ranged from 0.9986 to 1.0084. Their
largest sample log-ratio standard deviation was 0.0170. These checks exercise
the schedule and analysis path; they do not define a universal noise floor.

## Linked code

The retained inspection hooks include plan construction for Knuth-Morris-Pratt
(KMP) and Boyer-Moore-Horspool. The left-to-right hook used scalar `ldrb` byte
loads and called `bcmp` for full-window verification. KMP used scalar byte loads
and dependent prefix-table loads. Horspool initialized its 256-entry table with
SVE instructions including `rdvl`, `cntw`, and `str z0`, then used scalar
`ldrb` operations in the retained backward-comparison loop.

This is observed linked code for one binary. It does not prove which path
dominated elapsed time, retired instruction counts, or code generation on
another Arm processor.

The raw archive and its outer digest are under [`raw/b8d7f88`](raw/b8d7f88/).
