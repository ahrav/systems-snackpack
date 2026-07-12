# Topic 1: SWAR vs SIMD vs scalar code

This crate counts bytes equal to a target with three implementations.

- `count_eq_scalar` scans every byte.
- `count_eq_swar_prefilter` skips scalar checks for eight-byte words that contain no match.
- `count_eq_neon` uses AArch64 NEON when the current CPU supports it and falls back to scalar code elsewhere.

Run the example:

```bash
cargo run -p systems-snackpack-topic-001 --example count_eq
```

Run the benchmark program:

```bash
cargo bench -p systems-snackpack-topic-001 --bench throughput
```
