# Cross-host correctness and code-generation comparison

## What was tested

Both required Linux hosts built the same Git archive from source commit
`af126fa920f51969667e02b926786cca598212ea`. The archive's Secure Hash
Algorithm 256-bit (SHA-256) digest was
`f83290e6f41ec6c704cd61f2033bae1f90e749dbd2799137172a7ab322e99b7d`.
Each host ran the seven workspace gates and eight fresh correctness processes
without retry. The experiment inspected optimized LLVM intermediate
representation (IR), assembly, object code, and the linked executable. It did
not record elapsed time.

The local Secure Shell (SSH) configuration resolved `xxl` during this run to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. The remote host confirmed that
fully qualified name and reported `x86_64`.

The two host archives use the same receipt paths. `source-identity.txt` records
the source and archive identity. `host.txt`, `proc-cpuinfo.txt`,
`rustc-version.txt`, and `cargo-version.txt` support the host and tool rows.
The gate logs and `processes/runs.tsv` support the pass counts.
`codegen/topic42.ll`, `codegen/topic42.s`, and
`codegen/linked.objdump.txt` support the compiler and instruction rows. The
checked-in `xxl-resolution.txt` records the local alias resolution and remote
confirmation.

| Observation | Required Arm host | Runtime-resolved `xxl` host |
| --- | --- | --- |
| Kernel | `6.12.95-124.187.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| Processor evidence | Arm implementer `0x41`, part `0xd40` | Intel Xeon Platinum 8488C under Kernel-based Virtual Machine (KVM) virtualization |
| Online and available CPUs | 64 and 64 | 192 and 192 |
| rustc and LLVM | 1.93.1 and 21.1.8 | 1.93.1 and 21.1.8 |
| Fresh-process result | 8/8 passed | 8/8 passed |
| Output contract | six exact lines, empty standard error | same |
| Reference LLVM parameters | two `noalias` attributes | same |
| Reference source loads | one | one |
| Raw LLVM parameters | no `noalias` | same |
| Raw source loads | two, surrounding the store | same |
| Reference native shape | `ldr`, `str`, register shift | `movq` load/store, register add |
| Raw native shape | `ldr`, `str`, second `ldr` | `movq` load/store, memory-operand add |

## What the comparison means

Both exact builds recorded the same source-level results and LLVM alias
contract. Their native instruction sequences differed because the compiler
selected instructions for different targets. Two hosts cannot establish an
AArch64-wide or x86-64-wide rule.

The report omits a dispersion interval because it contains no elapsed-time or
throughput estimate. The eight process replications cover deterministic output,
empty standard error, and stable executable identity during each host run. They
are not independent timing samples.

Inspect LLVM IR when a decision depends on compiler alias assumptions. Inspect
the linked native code when it depends on host instructions. Use a separate,
workload-shaped benchmark before making a performance decision.
