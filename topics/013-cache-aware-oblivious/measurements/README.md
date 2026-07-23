# Measurement records

Each host record must retain:

- requested and resolved hostname;
- source commit, archive SHA-256, and source-file hashes;
- `uname`, CPU model, CPU count, NUMA topology, cache geometry, page size,
  transparent huge-page policy, ASLR policy, and pagemap visibility;
- Rust and C toolchains, native target features, and build flags;
- all workspace gate logs;
- release binary checksum, symbols, and focused plus full linked disassembly;
- 72 raw fresh-process rows from 12 order-balanced six-mode blocks;
- each benchmark source and destination virtual base, plus offsets modulo 4,096
  bytes and 64 bytes;
- combined setup and conditioning, kernel, verification, and external process
  time;
- per-mode median, interquartile range, sample standard deviation, range, and
  within-block paired ratios;
- post-run source equality verification and a complete `SHA256SUMS`.

The kernel interval is the performance boundary. A process is the replication
unit; matrix elements and loop iterations are not independent samples.
Physical-page and NUMA placement remain unknown unless observed for those exact
Rust allocations. The separate pagemap probe establishes only process
privilege, not the benchmark buffers' placement. Within-block ratios pair
nearby time and order, not allocation placement.

Recorded runs require a 4,096-byte base page and 64-byte data-cache lines. The
runner fails closed if either host reports different geometry.

Host notes and raw evidence are added only after the exact committed source
candidate passes on both required Linux hosts.
