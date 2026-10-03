# Primary references

- [Intel Memory Layout Transformations, 2019-03-26](https://www.intel.com/content/www/us/en/developer/articles/technical/memory-layout-transformations.html): field versus row locality, tiled layouts and conversion around loops. Its broad gather wording is guidance, not a guarantee about every compiler output.
- [Rust1.93.1 type layout](https://doc.rust-lang.org/1.93.1/reference/type-layout.html): record padding and array element spacing. Our Row uses repr(C) and eight u64 fields.
- [Rust1.93.1 unaligned reads](https://doc.rust-lang.org/1.93.1/std/ptr/fn.read_unaligned.html): a packed field copy differs from forming an unaligned reference. The lesson implementation uses safe Rust and no packed values.
- [LLVM21.1.8 vector cost model](https://github.com/llvm/llvm-project/blob/llvmorg-21.1.8/llvm/lib/Transforms/Vectorize/LoopVectorize.cpp#L5648-L5685): interleave, gather/scatter and scalarization alternatives. Mechanism possibilities do not establish our target's speedup.
- [Cabana0.7.0 AoSoA](https://github.com/ECP-copa/Cabana/blob/7914d28708b1c67b40d5743c1fbc09e221144dd3/core/src/Cabana_AoSoA.hpp#L436-L451) and [Slice full-tile bug](https://github.com/ECP-copa/Cabana/issues/836): logical length and exact-multiple tails require explicit tests. The Rust example does not use Cabana.

Accessed2026-10-03. Contract/source evidence is separate from the local results in
[measurements](measurements/README.md). No external benchmark numbers are adopted.
