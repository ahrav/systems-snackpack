# Measurement records

Each dated host record identifies the exact source candidate, resolved host,
kernel, CPU model, toolchain, native target flags, input, process count, timing
boundary, and generated code. The final evidence bundle's
[`SHA256SUMS`](raw/03b9067/SHA256SUMS) covers every preserved raw file.

The comparison uses 12 fresh, paired, order-balanced processes per host. Each
process constructs both indexes over the same `2^26`-bit deterministic input,
warms both variants, and times 4,000,000 identical random positions. The
summarizer rejects missing pairs, order errors, duplicate process IDs,
checksum mismatches, inconsistent dataset fingerprints, or inconsistent byte
counts. It reports pooled ratios descriptively and estimates each measurement
order separately.

Cross-host notes compare observations. They do not treat two hosts as
samples of an instruction set, CPU vendor, kernel, or bare-metal platform.

The host records preserve the source-archive digest used for transfer. The
transient minimized archive is not checked in, so that digest is provenance
metadata rather than a locally re-hashable artifact. Per-file source hashes are
preserved under both raw host directories and match the checked-in candidate.

Recorded evidence:

- [Arm host, 2026-07-19](2026-07-19-dev-dsk-ahrav-2b.md)
- [`xlg`, 2026-07-19](2026-07-19-xlg.md)
- [Cross-host boundary](2026-07-19-cross-host.md)
- [Final raw logs and checksums](raw/03b9067/)
- [Initial source-candidate archive](raw/4e855a3/)
