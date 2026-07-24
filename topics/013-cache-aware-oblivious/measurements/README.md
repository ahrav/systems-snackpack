# Measurement records

The record set contains the
[AArch64 host note](2026-07-23-dev-dsk-ahrav-2b.md), the
[xlg host note](2026-07-23-xlg.md), the
[cross-host comparison](2026-07-23-cross-host.md), and raw evidence under
[`raw/053e8f4/`](raw/053e8f4/).

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
PFN-disclosure behavior under the run's credentials, not privilege or the
benchmark buffers' placement. Within-block ratios pair nearby time and order,
not allocation placement.

Recorded runs require a 4,096-byte base page and 64-byte data-cache lines. The
runner fails closed if either host reports different geometry.

Host notes and raw evidence are added only after the exact committed source
candidate passes on both required Linux hosts.

The evidence source tree remains reachable through the annotated tag
`topic13-evidence-053e8f4`, which points at commit
`053e8f4d269e93276020a7937587762303e0104b`. The retained archive SHA-256 is
`51a39afc9da86c2a7c070e69b0b714cdb56dd1819cfae6e882bc7730c4721292`.
Its embedded commit metadata and each host's post-run source verification bind
the measurements to that tree.

Verify the relocated raw records from their host directories:

```bash
(cd raw/053e8f4/arm && sha256sum -c SHA256SUMS)
(cd raw/053e8f4/xlg && sha256sum -c SHA256SUMS)
```
