# Storage layout and device geometry

Compare three ways to prepare the same logical bytes: explicit zero fill,
sparse length extension, and Linux preallocation. Inspect filesystem allocation
separately from elapsed time and physical-device behavior.

The library also provides a checked sequential-zone cursor for a serialized owner.
It models geometry and successful placement. Exclusive device-range ownership
is an external assumption; the model does not implement device I/O or recovery.

```bash
cargo test -p topic-072-storage-layout
mkdir -p /path/to/task-owned-disk-directory
cargo run --release -p topic-072-storage-layout --example layout -- /path/to/task-owned-disk-directory sparse 16777216 scattered
```

The example supports `dense`, `sparse`, and `prealloc` initialization; the
patterns are `empty`, `dense`, `scattered`, and `clustered`. `scattered` writes
one 4096-byte block every 64 blocks. `clustered` writes the same block count
at the start. A final partial block is allowed. Optional `keep` preserves the
verified process-owned file for extent inspection. Inputs are capped at 64 MiB.
Preallocation requires 64-bit Linux and filesystem support for mode-0 fallocate.
Other platforms can compile and test the library; they reject preallocation.

See [round 1](rounds/01.md), [sources](references.md), and
[measurement contract](measurements/contract.md).
