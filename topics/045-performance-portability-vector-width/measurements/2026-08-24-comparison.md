# Cross-host vector-width comparison

Date: 2026-08-24

## What was compared

Both required Linux targets consumed the same scoped Git archive from source
commit `edc75b260d1909bb9c4d043cbfadba5e98e38944`. The Secure Hash Algorithm
256-bit (SHA-256) archive digest was
`1c1f7c89a513ec6409367b3b5605def6748ba95d2a9f1a55fcfe67c111031852`.
Each process was pinned to one logical central processing unit (CPU) and used
the same 20,000,000-step count for each of 96 logical chains after same-mode
warmup.

| Boundary | Arm target | `xxl` target |
| --- | --- | --- |
| Hostname | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| Architecture | `aarch64` | `x86_64` |
| Processor evidence | Arm part `0xd40`, variant 1, revision 1 | Intel Xeon Platinum 8488C, family 6, model 143, stepping 8 |
| Selected CPU | 16, no simultaneous-multithreading sibling | 24, simultaneous-multithreading sibling 120 |
| Available logical CPUs | 64 | 192 |
| Kernel | 6.12.100-125.179 | 6.12.95-124.187 |
| C compiler | GNU Compiler Collection 11.5.0 | GNU Compiler Collection 11.5.0 |
| Rust compiler and LLVM back end | 1.95.0, 22.1.2 | 1.97.1, 22.1.6 |
| Supported timed widths | scalar, 128 bit | scalar, 128, 256, 512 bit |
| Host and offline validators | byte-identical pass | byte-identical pass |

## Common observation

On both hosts, doubling the lane count from scalar to 128 bit nearly halved
elapsed time for this compute-only recurrence. The Arm candidate/baseline point
estimate was 0.494984 with 95% interval `[0.486690, 0.503419]`. The x86 point
estimate was 0.499846 with interval `[0.499454, 0.500239]`.

This agreement does not make the hosts interchangeable. Their compilers,
microarchitectures, kernels, virtualization boundaries, available counters,
and observed variation differ. It supports only the narrower claim that the
fixed recurrence exposed enough independent arithmetic for both recorded
128-bit paths to approach their two-lane ideal during these run windows.

## Wider x86 observation

On the recorded Intel host, 512-bit time was 0.593238 of 256-bit time, a
1.686-fold speedup rather than the ideal twofold speedup. Median user-mode core
cycles were 0.501404 of the 256-bit value, while the median
cycles-to-reference-cycles witness was 0.844410 of the 256-bit witness. Their
quotient is a process-scope diagnostic estimate of 0.593792. It differs from
the main-kernel time ratio by 0.000554, or 0.093%. This after-the-run
decomposition is a consistency check across different measurement scopes, not
an independent prediction.

The counters are consistent with a lower effective clock during the 512-bit
process. A frequency license is an internal processor power-and-clock
classification. These counters do not identify an Advanced Vector Extensions
512 (AVX-512) license transition, prove causality, or establish behavior for
other Intel Xeon Platinum 8488C systems outside this Kernel-based Virtual
Machine (KVM) guest. The receipts retain no direct frequency or license-state
observation: the Linux `cpufreq` interface was absent and the `turbostat`
frequency tool was unavailable.

The Arm host ran only scalar and fixed 128-bit Advanced Single Instruction,
Multiple Data (Advanced SIMD). Scalable Vector Extension (SVE) availability in
its feature list is not an SVE performance result. No cross-architecture
statement about the best physical vector width follows.

## Generated-code comparison

Both binaries contained 12 independent fused multiply-add destinations in each
measured loop. The Arm vector loop used the 128-bit `fmla` instruction. XMM,
YMM, and ZMM are the x86 names for 128-bit, 256-bit, and 512-bit vector
registers; the x86 loops used the corresponding register class at each width.
The Arm checker allowed only the fused multiply-add and integer loop-control
instructions in its detected loops. The x86 checker found no memory operands or
`mov` or `vmov` mnemonics in its detected loops.

These are observed code-generation facts for the retained binaries. They do not
show instruction throughput on another processor, and they do not include
memory traffic, dispatch, tail handling, or later service work.

## Evidence boundary

- **Measured:** source and binary identities, host and toolchain state,
  correctness, generated loops, fresh-process kernel time, complete-block
  variation, selected user-mode hardware counters, affinity, and validator
  results.
- **Derived:** candidate/baseline ratios, paired intervals, speedups, the
  0.844410 witness ratio, and the 0.593792 process-scope diagnostic estimate.
- **Inferred:** the x86 result is consistent with reduced effective clock during
  the 512-bit process, and both 128-bit paths exposed their lane parallelism.
- **Not established:** direct frequency-license state, thermal causality,
  memory-bound behavior, short-request crossover, multi-core effects, SVE
  performance, complete-service latency, or another host and compiler.

See the [Arm note](2026-08-24-arm.md), the [`xxl` note](2026-08-24-xxl.md), and
the [sealed evidence](raw/2026-08-24-edc75b26/).
