# Cross-host comparison

## What was tested

The same Git archive and C source ran on both required Linux hosts. Each host
ran one ordinary permission control and eight fresh privileged correctness
processes. No retry or timing sample was used. The result tests admission,
generated code, attachment, and socket action; it does not compare performance.

The `xxl` alias resolved during this run to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, which reported `x86_64`.

| Observation | Required Arm host | Runtime-resolved `xxl` host |
| --- | --- | --- |
| Kernel | `6.12.95-124.187.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| Processor evidence | Arm implementer `0x41`, part `0xd40` | Intel Xeon Platinum 8488C under KVM |
| Possible and online CPUs | 64 and 64 | 192 and 192 |
| Privileged fresh-process result | 8/8 passed | 8/8 passed |
| Ordinary result | exit 77, `EPERM`, empty verifier logs | exit 77, `EPERM`, empty verifier logs |
| Invalid control flow | `EINVAL`, jump to instruction 101 rejected | same |
| Translated bytes | 16 accept, 16 drop | 16 accept, 16 drop |
| Native JIT bytes | 64 accept, 64 drop | 21 accept, 16 drop |
| Native-byte variation across processes | none in 8 processes | none in 8 processes |
| Socket action | exact 14-byte accept; drop timeout after successful send | same |

Both kernels returned the same translated BPF encodings and preserved the same
socket behavior. Their visible native bodies differed in instruction sequence
and length. That is the expected kind of backend-specific result, but two hosts
cannot establish an AArch64-wide or x86-64-wide rule.

No dispersion interval is reported because no elapsed-time or throughput
estimate exists. The process-level replication covers deterministic correctness
and code-byte stability during this run. Inner socket operations and the
250-millisecond timeout are not independent performance samples.

## Decision supported

Inspect translated and native code when a claim depends on code generation.
Do not infer cost from BPF instruction count or transfer one host's JIT result
to an instruction-set family. Measure the real hook, helper, map, contention,
and export path for the production question.
