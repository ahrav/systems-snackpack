# Arm exact-source record

## Identity

- Source commit: `4f54c4d9e1b0754e9a02a0a37312711f54a3d588`
- Git archive SHA-256: `23c78439fca8d965325b5182492a8449fa50795cbfe86814a9793c2e8baac9d9`
- SSH target and hostname:
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Run window: 2026-08-12 14:33:48–14:34:12 UTC

The Git archive header, recorded commit, and archive digest matched. The
retrieved archive SHA-256 is
`d0c019d6e1fbfd4741829c51d79603633eb528e4918745bf442bfba2830bf65f`.
Its inner manifest and before/after source manifests passed after retrieval.

## Host and build

- Linux `6.12.95-124.187.amzn2023.aarch64`, `aarch64`, 64 available CPUs.
- CPU evidence: `lscpu` reported vendor `ARM`, model field `1`. The record does
  not infer a marketing model from that field.
- Rust and Cargo 1.93.1; LLVM 21.1.8; GCC 11.5.0; GNU objdump 2.41.
- Native features included NEON, CRC, Large System Extensions, and Scalable
  Vector Extension. The generic build did not request native features.
- WAL and receipt path: `/dev/nvme0n1p1`, XFS, `rw,noatime`; `lsblk` exposed an
  11.7-TiB nonrotating Amazon Elastic Block Store device. This identifies the
  presented virtual device, not its physical media or power-loss behavior.

## Results

Generic and native builds both passed the deterministic model and all three
external-supervisor `SIGKILL` cases. The model checked 160 byte-prefix cuts and
159 single-bit faults. The crash cases recovered LSN 2 after each cut; the
external acknowledgement witness was 1, 1, and 2 respectively.

The native timing comparison used eight complete blocks and 32 fresh child
processes. A synced each of 128 records. B synced eight records at a time and
made 16 calls. Both wrote 37,888 bytes.

- B/A geometric elapsed ratio: `0.128146`.
- Sample standard deviation of eight block log-ratios: `0.040686`, or about
  4.152% on the multiplicative scale.
- Exploratory paired-t 95% interval: `[0.123860, 0.132580]`.

The interval covers process and block variation inside this run window. It
does not cover another host, device, workload, concurrent commit formation,
startup, or power loss.

The retained `topic33_crc32c` disassembly used scalar AArch64 byte loads,
shifts, masks, and exclusive-OR operations. It did not use the architecture's
CRC instruction. Dynamic symbols included `write`, `writev`, `fdatasync`, and
`fsync`; this is link evidence, not a syscall trace.

Every required workspace format, test, doctest, lint, benchmark-build, and
documentation gate passed with the pinned toolchain.
