# Recovery checks, 2026-11-26

The Rust planner agreed with forward replay for all 256 availability masks, 36 valid base ranges and 10 target positions (92,160 decisions). A separate test rejects a reversed base range. The Python example prints reachable bases for the four illustrated targets and one proposed deletion.

PostgreSQL 16.10 independently exercised actual recovery on Linux AArch64 and Linux x86-64. Each host used fresh temporary clusters, 1 MiB WAL segments, two independent streaming base backups, named restore points, one isolated missing archive file, and exact SQL row assertions. Both backup verifications passed. With the intact archive A recovered orders 41 and 42. With segment 000000010000000000000007 withheld A failed before its target. With the same gap B recovered the later orders 41 and 43. The post-target order 99 was absent.

On local macOS arm64 the model ran. PostgreSQL initdb failed during bootstrap because the sandbox denied shmget. Native results come from the two Linux machines. This is a single-timeline correctness drill. Restore time, archive throughput, media-corruption detection and cross-timeline replay were outside the experiment.

All native binaries came from the [PostgreSQL 16.10 source release](https://ftp.postgresql.org/pub/source/v16.10/). The published SHA-256 for postgresql-16.10.tar.bz2 matched on all three machines: de8485f4ce9c32e3ddfeef0b7c261eed1cecb54c9bcd170e437ff454cb292b42.
