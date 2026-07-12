# Topic 2: Intrinsics vs handwritten assembly

This crate compares a compiler-visible AArch64 CRC32-C intrinsic with a
four-instruction inline-assembly block. Both paths fall back to a portable
reference implementation outside AArch64 CRC-capable systems.

The fold is a benchmark kernel. It is not a standard CRC32-C file format.

Run the example:

```bash
cargo run -p systems-snackpack-topic-002 --example compare
```

Run the benchmark program:

```bash
cargo bench -p systems-snackpack-topic-002 --bench fold
```
