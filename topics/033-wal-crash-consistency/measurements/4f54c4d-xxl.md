# `xxl` exact-source record

## Identity

- Source commit: `4f54c4d9e1b0754e9a02a0a37312711f54a3d588`
- Git archive SHA-256: `23c78439fca8d965325b5182492a8449fa50795cbfe86814a9793c2e8baac9d9`
- SSH alias: `xxl`
- Resolved hostname:
  `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`
- Confirmed architecture: `x86_64`
- Run window: 2026-08-12 14:34:27–14:34:45 UTC

The Git archive header, recorded commit, and archive digest matched. The
retrieved archive SHA-256 is
`98266fea0d93d536ae649de0642b9025865311c2952de4a80d913362f96d66ab`.
Its inner manifest and before/after source manifests passed after retrieval.

## Host and build

- Linux `6.12.95-124.187.amzn2023.x86_64`, 192 available CPUs.
- CPU evidence: GenuineIntel, Intel Xeon Platinum 8488C, family 6 model 143.
- Rust and Cargo 1.93.1; LLVM 21.1.8; GCC 11.5.0; GNU objdump 2.41.
- Native features included AVX2 and several AVX-512 extensions. The generic
  build did not request native features.
- WAL and receipt path: `/dev/nvme0n1p1`, XFS, `rw,noatime`; `lsblk` exposed a
  2-TiB nonrotating Amazon Elastic Block Store device. This identifies the
  presented virtual device, not its physical media or power-loss behavior.

## Results

Generic and native builds both passed the deterministic model and all three
external-supervisor `SIGKILL` cases. The model checked 160 byte-prefix cuts and
159 single-bit faults. The crash cases recovered LSN 2 after each cut; the
external acknowledgement witness was 1, 1, and 2 respectively.

The native timing comparison used eight complete blocks and 32 fresh child
processes. A synced each of 128 records. B synced eight records at a time and
made 16 calls. Both wrote 37,888 bytes.

- B/A geometric elapsed ratio: `0.130341`.
- Sample standard deviation of eight block log-ratios: `0.056076`, or about
  5.768% on the multiplicative scale.
- Exploratory paired-t 95% interval: `[0.124372, 0.136597]`.

The interval covers process and block variation inside this run window. It
does not cover another host, device, workload, concurrent commit formation,
startup, or power loss.

The retained `topic33_crc32c` disassembly used scalar integer instructions plus
AVX/AVX-512 vector and mask operations selected by LLVM. It did not use the
x86 CRC32 instruction. Dynamic symbols included `write`, `writev`,
`fdatasync`, and `fsync`; this is link evidence, not a syscall trace.

Every required workspace format, test, doctest, lint, benchmark-build, and
documentation gate passed with the pinned toolchain.
