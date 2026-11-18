# Correctness results, November 18, 2026

The parent and child each decoded (42, 7) from distinct mappings of the same file. All three platforms rejected the interior offset 12, end offset 24, and maximum unsigned 32-bit offset. The independent Rust writer oracle passed 6,048 combinations per host (9 record counts × 8 trailer lengths × 84 selections). Short-header and version checks also passed.

| Host | Kernel and architecture | Python | Rust | Result |
|---|---|---|---|---|
| Local Mac | Darwin 25.6.0 arm64 | 3.13.16 | 1.93.1 | Two unit tests, one doctest, one forked mapping run passed |
| Linux development host | Linux 6.12.115 AArch64 | 3.9.25 | 1.93.1 | Same checks passed |
| xxl | Linux 6.12.115 x86-64 | 3.9.25 | 1.93.1 | Same checks passed |

The source commit was `14b40f16b93a546e0e5febef550fe503a428de3a`. All three hosts used its Git archive, SHA-256 `9f831ecb58927f7cc60274b24fa38e6d537d6accbd375e368bae4e6ce0215c66`. Both Linux logs contain the digest of the received archive.

The Rust tests ran in the default test profile. The local workspace passed formatting, Clippy with warnings denied, 578 unit/binary/example tests, 170 doctests, benchmark compilation, and documentation with warnings denied. The workload measured correctness for one stable generation. Concurrent mutation, truncation, and performance were outside the experiment.

Repeat from the repository root.

```sh
cargo test -p topic112-relocatable-inventory
python3 topics/112-relocatable-inventory/inventory.py
```
