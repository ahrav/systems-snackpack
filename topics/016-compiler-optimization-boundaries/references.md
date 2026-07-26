# Primary sources

- [Rust Reference: code-generation
  attributes](https://doc.rust-lang.org/reference/attributes/codegen.html):
  `inline` forms are hints, and their use can affect program behavior without
  unsafe code.
- [Cargo profiles: LTO and codegen
  units](https://doc.rust-lang.org/cargo/reference/profiles.html#lto): Cargo's
  profile-level controls for cross-codegen-unit and cross-crate optimization.
- [rustc code-generation
  options](https://doc.rust-lang.org/stable/rustc/codegen-options/): exact
  `lto`, `codegen-units`, target CPU, and optimization controls.
- [rustc linker-plugin
  LTO](https://doc.rust-lang.org/rustc/linker-plugin-lto.html): preserving LLVM
  bitcode for whole-program optimization across compiler boundaries.
- [LLVM language reference](https://llvm.org/docs/LangRef.html): linkage,
  preemption, alias, memory-effect, call, and optimization attributes.
- [LLVM optimization remarks](https://llvm.org/docs/Remarks.html): structured
  records for performed, missed, and analyzed transformations.
- [LLVM loop vectorizers](https://llvm.org/docs/Vectorizers.html): legality,
  runtime checks, tail handling, and profitability controls.
- [GCC optimization
  options](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html):
  interprocedural optimization, semantic interposition, and LTO boundaries.
- [Rust undefined
  behavior](https://doc.rust-lang.org/reference/behavior-considered-undefined.html):
  aliasing and mutation obligations that constrain legal optimization.
- [Rust `black_box`](https://doc.rust-lang.org/std/hint/fn.black_box.html):
  best-effort benchmark-harness opacity and its explicit non-guarantees.
- [Rust volatile
  reads](https://doc.rust-lang.org/core/ptr/fn.read_volatile.html) and
  [`compiler_fence`](https://doc.rust-lang.org/std/sync/atomic/fn.compiler_fence.html):
  distinct observable-access and compiler-ordering contracts.
- [C++ abstract machine and as-if
  rule](https://eel.is/c++draft/intro.abstract): the observable-behavior
  boundary for conforming C++ implementations.
- [Mytkowicz et al., *Producing Wrong Data Without Doing Anything Obviously
  Wrong!*](https://sape.inf.usi.ch/publications/asplos09.html): layout-induced
  performance bias in the paper's SPEC CPU2006 experiments.
