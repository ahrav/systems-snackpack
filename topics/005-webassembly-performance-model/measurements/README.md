# Measurements

The experiment treats each fresh, CPU-pinned child process as one replication.
The runner excludes two whole-process warmups, then retains 12 measured pairs:
six guest-first and six host-first. Each child also performs three internal
warmup rounds before its measured pair. The process JSONL preserves the runner
manifest, excluded warmups, measurements, and summary.

For 12 ordered paired differences, `[X_(3), X_(10)]` is an exact 96.142578125%
sign interval for the population median under independent, identically
distributed, continuous sampling. The interval covers process variation within
one host, build, and time block. It does not cover rebuild, runtime-version,
host, fleet, instruction-set-architecture (ISA), or vendor variation. The two
hosts remain separate experiments.

Both host manifests record the same WAT, C embedder, and process-runner
SHA-256 values; those hashes match the checked-in experiment sources. All 24
measured processes passed correctness.

| Recorded host | Guest direct | Typed callback | Paired added path | Paired ratio |
|---|---:|---:|---:|---:|
| AArch64, Arm MIDR `0x411fd401` | 1.602 ns/step | 73.499 ns/step | 71.900 ns/step | 45.772× |
| x86-64, AMD EPYC 9R14 under KVM | 1.660 ns/step | 48.309 ns/step | 46.654 ns/step | 29.193× |

The hosts differ in processor, virtualization, kernel, compiler environment,
and generated instructions. The table does not isolate any one difference and
does not establish an ISA or vendor comparison.

- [`2026-07-15-linux-aarch64.md`](2026-07-15-linux-aarch64.md): AArch64 host, method, results, and limits.
- [`2026-07-15-linux-x86-64.md`](2026-07-15-linux-x86-64.md): x86-64 host, method, results, and limits.
- [`raw/`](raw/): manifests with hashes, identity probes, process JSONL,
  correctness output, native disassembly, and both full workspace-gate logs.
