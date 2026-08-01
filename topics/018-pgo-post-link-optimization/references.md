# Primary sources

- [rustc profile-guided optimization](https://doc.rust-lang.org/rustc/profile-guided-optimization.html):
  Rust's instrumentation, profile merge, and profile-use workflow.
- [rustc code-generation options](https://doc.rust-lang.org/stable/rustc/codegen-options/):
  `profile-generate`, `profile-use`, target CPU, codegen-unit, debug, and linker
  controls used by the retained experiment.
- [Clang profile-guided optimization](https://clang.llvm.org/docs/UsersManual.html#profile-guided-optimization):
  instrumentation and sample-profile workflows, profile correction, and profile
  diagnostics.
- [`llvm-profdata`](https://llvm.org/docs/CommandGuide/llvm-profdata.html):
  raw-profile merge behavior, weighted inputs, profile inspection, and overlap
  analysis.
- [LLVM instrumentation profile format](https://llvm.org/docs/InstrProfileFormat.html):
  counter, value-profile, binary-ID, and correlation representations.
- [LLVM branch-weight metadata](https://llvm.org/docs/BranchWeightMetadata.html):
  how profile-derived weights annotate branches, calls, and switches.
- [LLVM block-frequency terminology](https://llvm.org/docs/BlockFrequencyTerminology.html):
  relative frequency, branch probability, and block-frequency definitions used
  by compiler analyses.
- [GCC optimization options](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html):
  GCC's profile use, partial-training, and correction controls.
- [GCC program instrumentation
  options](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html):
  GCC's profile generation and reproducibility controls.
- [LLVM BOLT](https://github.com/llvm/llvm-project/blob/main/bolt/README.md):
  required ELF metadata, profile collection paths, and binary-rewrite workflow.
- [BOLT paper](https://arxiv.org/abs/1807.06735):
  the design and evaluation of final-image profile-guided binary optimization.
- [Propeller paper](https://snehasish.net/assets/pdf/shen-asplos23.pdf):
  profile-guided basic-block layout through compiler-emitted sections and
  relinking.
