# `xxl` exact-source record for `b8d7f88`

The runtime-resolved required x86 host passed correctness, workspace, timing,
receipt, and linked-code gates for source commit
`b8d7f88a25aede60fb589099239c771285450293`.

## Execution boundary

- SSH alias: `xxl`
- Resolved host: `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`
- Confirmed architecture: `x86_64`
- Run window: 2026-08-13 07:36:53 through 07:40:42 PDT, based on retained
  result-file modification times
- CPU evidence: Intel Xeon Platinum 8488C under KVM, 192 available CPUs, two
  non-uniform memory access (NUMA) nodes; reported features include AVX2 and
  AVX-512
- Kernel: `6.12.95-124.187.amzn2023.x86_64`
- Toolchain: Rust 1.93.1, Cargo 1.93.1, LLVM 21.1.8, GCC 11.5.0, GNU
  `objdump` 2.41; `clang` was unavailable
- Native flags: `-C target-cpu=native -C debuginfo=1`
- Pinned CPU: 0, the first CPU in the process's allowed `0-191` mask
- Source archive SHA-256:
  `5a2807443d9ef14ba3ce7a971787654db1879a3b52d227be404af8dbea4e640c`
- Timing binary SHA-256:
  `9d2ddee788ccaed6bceb64301072fbf010df67d6466218a06b5fc191e4e8cf4c`

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
| uniform absent, 32 bytes | reuse | 0.376 (0.0098) | 2.988 (0.0039) |
| uniform absent, 32 bytes | one-shot | 0.376 (0.0091) | 2.982 (0.0051) |
| skewed text, late 16 bytes | reuse | 0.709 (0.0058) | 2.320 (0.0092) |
| skewed text, late 16 bytes | one-shot | 0.706 (0.0109) | 2.301 (0.0137) |
| repeated-prefix trap, 32 bytes | reuse | 1.530 (0.0047) | 0.762 (0.0072) |
| repeated-prefix trap, 32 bytes | one-shot | 1.523 (0.0080) | 0.761 (0.0043) |
| repeated-suffix trap, 32 bytes | reuse | 50.219 (0.0046) | 2.991 (0.0025) |
| repeated-suffix trap, 32 bytes | one-shot | 50.269 (0.0045) | 2.991 (0.0016) |
| tiny late match, 4 bytes | reuse | 2.955 (0.0006) | 2.971 (0.0024) |
| tiny late match, 4 bytes | one-shot | 2.984 (0.0022) | 2.997 (0.0019) |

The four-block same-method schedule checks ranged from 0.9988 to 1.0070. Their
largest sample log-ratio standard deviation was 0.0146. These checks exercise
the schedule and analysis path; they do not define a universal noise floor.

## Linked code

The retained inspection hooks include plan construction for Knuth-Morris-Pratt
(KMP) and Boyer-Moore-Horspool. The left-to-right hook used scalar `movzbl`
byte loads and called `bcmp` for full-window verification. KMP used scalar byte
loads and dependent prefix-table loads. Horspool initialized its 256-entry
table with AVX2 `vpbroadcastq` and `vmovdqu` instructions, then used scalar byte
loads in the retained backward-comparison loop.

This is observed linked code for one binary. It does not prove which path
dominated elapsed time, retired instruction counts, or code generation on
another x86 processor.

The raw archive and its outer digest are under [`raw/b8d7f88`](raw/b8d7f88/).
