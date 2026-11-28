# Topic 122 results

macOS arm64, Linux AArch64 and Linux x86-64 each passed two unit tests and one doctest using Rust 1.93.1. All three ran the committed implementation at `69d3bffea13dfba66a727cb11cca4e0173415e13`. Each host checked the Git archive commit and SHA-256 before building. The archive included the workspace manifests, lockfile, Rust sources, toolchain pin and complete topic directory.

| Check | Observed on each host |
|---|---|
| Deterministic two-worker example | Read A=41, refuse B, read A=42, release A, load B=90, reload A=42 |
| Independent logical-page oracle | 100,000 histories of five client events, both final page values checked in each history |
| Saved-frame control in Python | After release and reuse, the same reference reads B=90 |

The tests exercise real Rust synchronization in memory. One test uses a scoped OS thread and an ordered join. The bounded oracle compares sequential histories. It exercises repeated pins, misses, writes and releases. It cannot prove correctness for every overlapping lock acquisition. The backing array preserves changes across replacement within one process. Disk durability, throughput and contention in a production database were unmeasured.

Run `cargo test --locked -p topic122-buffer-pinning` and `cargo run --locked -p topic122-buffer-pinning` from the workspace root. The lesson includes the standalone Python control.
