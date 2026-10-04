# ABI and FFI performance boundaries

Compare one C call per value, borrowed batches of256 or all values, a copied
batch, and a same-language Rust loop. All compute an identical unsigned transform
and sum modulo2^64. The safe wrapper borrows synchronously; C does not retain or
write input. Rust owns every allocation and release.

```bash
cargo test -p topic-067-abi-ffi-performance-boundaries
cargo run -p topic-067-abi-ffi-performance-boundaries --release --example compare -- batch 4096 0
python3 topics/067-abi-ffi-performance-boundaries/scripts/run.py /tmp/topic67-new-results
```

Native Rust/C toolchains, ar and Python3 required. Linux runner also uses taskset,
objdump and nm. Cross-compilation is intentionally rejected by build.rs.
See [experiment](EXPERIMENT.md), [measurements](measurements/README.md),
[round](rounds/01.md) and [sources](references.md). Raw evidence stays outside Git.
