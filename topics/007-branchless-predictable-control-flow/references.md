# References

- [Rust Reference: `if` expressions](https://doc.rust-lang.org/reference/expressions/if-expr.html) — Source contract: Rust evaluates only the selected block.
- [Rust Reference: operand evaluation order](https://doc.rust-lang.org/reference/expressions.html#evaluation-order-of-operands) — Source contract for evaluating function arguments before a call.
- [Rust `select_unpredictable`](https://doc.rust-lang.org/stable/std/hint/fn.select_unpredictable.html) — Rust 1.88+ hint contract; no instruction or constant-time guarantee.
- [LLVM Language Reference: `select`](https://llvm.org/docs/LangRef.html#select-instruction) — IR contract for choosing between produced SSA values.
- [GCC optimization options](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html#index-fif-conversion) — Documents GCC if-conversion flags and their branchless transforms.
- [LLVM `SelectOptimize.cpp`](https://llvm.org/doxygen/SelectOptimize_8cpp_source.html) — Current implementation snapshot for select-to-branch conversion.
- [LLVM `X86CmovConversion.cpp`](https://llvm.org/doxygen/X86CmovConversion_8cpp_source.html) — Current implementation snapshot for x86 CMOV-to-branch conversion.
- [Arm A64 ISA overview](https://developer.arm.com/-/media/Files/pdf/graphics-and-multimedia/ARMv8_InstructionSetOverview.pdf) — Architecture-level `CSEL` semantics.
- [Intel architecture manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) — Architecture and optimization manuals for `CMOVcc` and conditional control flow.
- [Yeh and Patt, ISCA 1992](https://doi.org/10.1145/139669.139709) — Primary paper for two-level adaptive prediction from branch and pattern history.
- [Linux `perf record`](https://github.com/torvalds/linux/blob/master/tools/perf/Documentation/perf-record.txt) — Branch-stack filters and hardware-dependent sampling controls.
- [Kalibera and Jones, ISMM 2013](https://kar.kent.ac.uk/33611/) — Process-level replication and multilevel benchmark variation.
