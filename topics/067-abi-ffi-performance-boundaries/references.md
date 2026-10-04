# Primary sources, accessed 2026-10-04

- [Rust external blocks](https://doc.rust-lang.org/reference/items/external-blocks.html): declarations, C ABI and edition2024 unsafe extern.
- [Rust FFI](https://doc.rust-lang.org/nomicon/ffi.html): ownership, callbacks and unwind boundaries.
- [Rust raw slice contract](https://doc.rust-lang.org/std/slice/fn.from_raw_parts.html): nonnull even at zero length, one allocation, initialized values, lifetime, aliasing and byte-size bounds.
- [Rust representation](https://doc.rust-lang.org/reference/type-layout.html): repr(C) and transparent layout limits.
- [Rust linker-plugin LTO](https://doc.rust-lang.org/rustc/linker-plugin-lto.html): compatible LLVM IR, matching modes and linker support.
- [LLVM vectorizers](https://llvm.org/docs/Vectorizers.html): trip-count profitability and scalar remainder loops.

These define contracts and optimization possibilities. Measurements in this topic
are observations of named builds; timing differences do not isolate pure call cost.
