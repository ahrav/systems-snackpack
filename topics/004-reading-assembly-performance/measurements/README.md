# Measurements

- [Apple M1 Pro baseline, 2026-07-14](2026-07-14-m1-pro.md) records the host,
  toolchain, benchmark design, timer boundary, medians, and observed release
  codegen.
- [Linux AArch64 baseline, 2026-07-14](2026-07-14-linux-aarch64.md) records nine
  pinned process runs, [raw benchmark output](raw/2026-07-14-linux-aarch64.txt),
  a [workspace gate log](raw/2026-07-14-linux-aarch64-workspace-gates.txt),
  both SHA-256 digests, an exact 96.1% sign-based confidence interval for the
  paired-ratio median, and AArch64 release codegen.
- [Linux x86-64 baseline, 2026-07-14](2026-07-14-linux-x86-64.md) records nine
  pinned process runs, [raw benchmark output](raw/2026-07-14-linux-x86-64.txt),
  a [workspace gate log](raw/2026-07-14-linux-x86-64-workspace-gates.txt), both
  SHA-256 digests, an exact 96.1% sign-based confidence interval for the
  paired-ratio median, and x86-64 release codegen.

Measurement notes keep elapsed-time results, codegen observations, and derived
models in separate sections. Cross-host ratios do not establish ISA-level
performance differences.
