# Cross-host summary: 2026-07-29

Both hosts ran the same archive from source commit
`cf1b205058a6985eac98dc70ef1b2ff1e35370c2`, archive SHA-256
`717e59c0dc7284bbeb8749da6229d96004417acdcef79e9619cb36cfc9d52a21`.
Each run generated and built its ELF files locally with GCC 11.5.0 and
`-march=native`; the binaries are therefore host-specific.

| Observation | `xxl` x86-64 | `alg` AArch64 |
|---|---:|---:|
| Analysis units / timing processes | 12 / 48 | 12 / 48 |
| Dense median, ns/call | 4.946949482 | 4.252230764 |
| Sparse median, ns/call | 36.896729112 | 14.350850463 |
| Geometric sparse/dense ratio | 7.383368103 | 3.373277553 |
| 95% log-t interval | [6.688401183, 8.150546454] | [3.359216483, 3.387397481] |
| A/A ratio | 1.000635208 | 1.001218188 |
| A/A interval | [0.940113367, 1.065053273] | [0.997524552, 1.004925501] |
| Dense `.text`, bytes | 9,053 | 9,204 |
| Sparse `.text`, bytes | 2,097,405 | 2,097,428 |
| Leaf size, bytes | 5 | 8 |
| Leaf spacing treatment, bytes | 16 versus 4096 | 16 versus 4096 |

## What crossed the host boundary

The treatment slowed the workload on both hosts. The point estimates differ,
and `xxl` had more block-to-block timing dispersion. These are two host results,
not x86-64-versus-AArch64 estimates. The machines differ in processor,
operating system build, Rust toolchain, native compiler target, and concurrent
host state.

Final-image inspection established equal leaf code within each host. The x86-64
`run_rounds` instruction sequence stayed equal apart from addresses and
displacements. The AArch64 dense caller contains one additional `nop`, so its
caller sizes are 116 and 112 bytes. The measured effect therefore covers the
complete linked-image response to the alignment request.

The PMU evidence is not directly comparable across hosts. `xxl` completed its
architectural anchor and Intel DSB/MITE delivery groups; three other requested
groups failed and remain recorded. `alg` completed the cycle/instruction, L1I,
and instruction-TLB groups. Every successful group reported 100% running time.

## Evidence boundary

- **Measured:** elapsed nanoseconds, complete-block ratios and intervals, A/A
  results, ELF layout, final instructions, PMU counts, counter failures, and
  gate outcomes.
- **Observed vendor evidence:** the Intel model string on `xxl`; the Arm
  implementer, part, and feature identifiers on `alg`.
- **Inferred:** which share of the slowdown came from decoded-operation supply,
  L1I refills, instruction translation, prediction, target structures, or
  prefetching.

The experiment establishes that extreme function spacing can dominate this
fixed indirect-call workload even after same-process warm-up. It does not
justify the 4096-byte treatment as a model of ordinary binaries, nor does it
set a universal alignment threshold.
