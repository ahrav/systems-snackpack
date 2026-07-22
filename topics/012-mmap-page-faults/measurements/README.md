# Measurement records

The final record set will contain one host note per required Linux target, one
cross-host note, and raw evidence under `raw/<source-prefix>/<host>/`.

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
