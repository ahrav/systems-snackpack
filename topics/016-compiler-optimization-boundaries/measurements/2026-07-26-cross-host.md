# Exact-source cross-host record, 2026-07-26

Both Linux records used pushed commit
`8b1d2d65f188a0329937789a310dca5b379e3d8f`, rustc 1.93.1 with LLVM 21.1.8,
the same input and round count, CPU 0 affinity, and
`-C target-cpu=native -C codegen-units=1 -C lto=off`. Every workspace gate
passed on both hosts. The [run-context receipt](2026-07-26-run-context.md)
records the pushed branch and x86 alias resolution.

Both bundles retain matching before/after source manifests, an executable
SHA-256 digest, and SHA-256-covered full and focused disassembly. They do not
retain the executable bytes. `source_archive_sha256=unknown` records that the
collectors used exact Git checkouts rather than uploaded source archives.

| Evidence | Arm target | Current x86 target |
| --- | --- | --- |
| Architecture | `aarch64` | `x86_64` |
| CPU evidence | implementer `0x41`, part `0xd40` | AMD EPYC 9R14 |
| Available CPUs | 64 | 128 |
| Visible loop | shared local/imported address; SVE loop | shared local/imported address; AVX-512 loop |
| Opaque loop | scalar `bl` per element | scalar indirect `call` per element |
| Opaque/local timed ratio | 5.6623 [`5.5558`, `5.7664`] | 29.2729 [`28.0472`, `30.0105`] |
| Imported/local timed ratio | 1.0064 [`0.9868`, `1.0278`] | 0.9016 [`0.8503`, `0.9541`] |

## What the comparison establishes

Measured:

- all three modes are value-equivalent for the checked workload;
- the visible local and imported reducers have one address and one linked body
  on each host;
- both visible bodies are vectorized;
- both opaque reducers retain a scalar per-element call;
- elapsed ratios and bootstrap intervals describe the named run windows;
- the x86 imported/local negative control differs by schedule stratum.

Inferred:

- making the helper body available allowed the compiler pipeline to optimize
  across the call boundary in these builds;
- with the helper body unavailable at the retained boundary, the compiler did
  not produce the same whole-loop result under these flags.

Not established:

- the cost of call/return in isolation;
- a general effect of Rust `pub`, the C ABI, or `no_mangle`;
- the cause of the x86 imported/local timing discrepancy;
- an Arm-versus-x86, vendor-family, or ISA-wide performance ranking.

The opaque/local ratios combine dispatch, vectorization, unrolling, register
allocation, and other loop-shape changes. Clock, memory, microarchitecture, and
target-feature effects are confounded with the cross-host difference. The x86
schedule nuisance also limits the precision of its pooled ratio and interval.
There is no population-valid host sample and no independent-build replication.

See the [Arm record](2026-07-26-arm.md), [x86 record](2026-07-26-xlg.md), and
[measurement contract](README.md).
