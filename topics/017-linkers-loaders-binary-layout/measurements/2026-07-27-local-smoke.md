# Local smoke run: 2026-07-27

The dependency-free Rust analysis benchmark completed on the local Codex
workspace:

- host boundary: Darwin 25.5.0, `arm64`, kernel target `RELEASE_ARM64_T6000`;
- CPU model: unavailable because the sandbox denied the `sysctl` query;
- toolchain: rustc 1.93.1, LLVM 21.1.8, target `aarch64-apple-darwin`;
- command: `cargo bench -p linkers-loaders-binary-layout --bench block_summary`;
- workload: 100,000 summaries, each over 12 identical block contrasts;
- retained output: `elapsed_ns=17840708`, `checksum=101000.000000`.

This run checks benchmark execution and the retained checksum. Its elapsed time
does not support a performance claim. The dynamic-binding experiment requires
glibc Linux and will run separately on the two required Linux hosts.

The [raw receipt](raw/local/block-summary.txt) retains the command output and
host boundary.
