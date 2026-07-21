# Measurement records

Each host record identifies the exact source candidate, source-archive digest,
resolved hostname, kernel, CPU model, available CPUs, toolchain, native target
features, build flags, input, process count, timing boundary, and linked code.
The raw evidence manifest covers every preserved file.

The comparison uses 12 order-balanced pairs and 24 fresh processes per host.
Each process runs one variant over the same deterministic 4 KiB slice at
offset 3 after a 64 MiB warmup. It then hashes 1,073,741,824 bytes. Input
construction, runtime dispatch, and warmup are outside the steady-state timer.
External process startup is not part of the reported elapsed time.

The summarizer rejects missing pairs, order errors, duplicate records,
inconsistent checksums, malformed checksum or digest fields, a missing or
duplicate benchmark-binary artifact record, and mismatched byte counts. It
reports per-variant process distributions and paired table/hardware
throughput ratios. Order strata remain visible because cache, frequency, and
other process state can make order material.

Cross-host notes compare observations. They do not treat two hosts as samples
of an instruction set, processor vendor, kernel, hypervisor, or platform.

Recorded evidence:

- [Arm host, 2026-07-20](2026-07-20-dev-dsk-ahrav-2b.md)
- [`xlg`, 2026-07-20](2026-07-20-xlg.md)
- [Cross-host boundary](2026-07-20-cross-host.md)
- [Raw logs and checksums](raw/2ef0239/)

The minimized source archive is transient, so the digest recorded for
candidate `2ef0239` is provenance metadata rather than a locally re-hashable
artifact. The per-file source hashes match across hosts and match candidate
`2ef0239`. The harness now closes that gap for later runs: archive mode
requires `SOURCE_ARCHIVE`, re-hashes the tarball against the declared digest,
and rejects any extracted tree that differs from the archive contents.

## Local integration smoke

Before the exact-source Linux run, the artifact was exercised on local host
`b0f1d8752aba`: Darwin 25.5.0 on `arm64`, rustc 1.93.1 with LLVM 21.1.8.

```bash
cargo bench --quiet -p systems-snackpack-topic-010 --bench crc32c -- \
  --mode table --len 4096 --align 3 --iterations 2048
cargo bench --quiet -p systems-snackpack-topic-010 --bench crc32c -- \
  --mode hardware --len 4096 --align 3 --iterations 2048
```

Each command timed 8 MiB after a 64 MiB warmup. It excluded process startup,
input construction, dispatch selection, the independent check, and warmup. The
run checked harness integration and output parity; it is not part of the Linux
performance comparison. The [captured transcript](raw/2ef0239/local-darwin-smoke.txt)
records the exact output and benchmark-source hash.
