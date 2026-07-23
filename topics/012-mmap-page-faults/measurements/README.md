# Measurement records

The record set contains the [AArch64 host note](2026-07-22-dev-dsk-ahrav-2b.md),
the [xlg host note](2026-07-22-xlg.md), the
[cross-host comparison](2026-07-22-cross-host.md), and raw evidence under
[`raw/bdd17c6/`](raw/bdd17c6/).

Every host record must retain:

- requested alias and resolved hostname;
- source commit and archive SHA-256;
- `uname`, CPU model, CPU count, NUMA topology, page size, THP policy, memory,
  swap, filesystem, mount, compiler, Rust toolchain, and native target features;
- workspace gate logs, C build flags, binary checksum, and focused disassembly;
- 32 raw fresh-process rows from eight order-balanced four-mode blocks;
- process-level medians, sample standard deviations, ranges, and paired ratios;
- a source-file SHA-256 manifest and a post-run equality-verification log.

The touch-loop interval excludes setup and process startup. The raw CSV retains
`setup_ns`. A Python `time.monotonic_ns()` boundary around each pinned workload
process supplies `external_wall_ns`. Summary dispersion covers the eight
processes per mode, not the pages within a mapping.

The file-cold mode uses `MADV_RANDOM` and therefore represents an intentionally
sharp storage-backed fault path. It does not estimate ordinary sequential mmap
behavior, device-cache-cold performance, or a universal major/minor ratio.

## Known limitation in the bdd17c6 evidence

The `vm_faults.sha256` files under `raw/bdd17c6/` name the transient run
directory, so `sha256sum -c vm_faults.sha256` fails after relocation into this
repository. Verify the retained binaries through each directory's `SHA256SUMS`
instead, which names `./vm_faults` relative to its own location; the digest on
its `vm_faults` line equals the digest inside `vm_faults.sha256`. The retained
files stay byte-identical to what the recorded runs produced rather than being
edited after the fact. The runner now writes relative names, so later evidence
does not carry this wart.
