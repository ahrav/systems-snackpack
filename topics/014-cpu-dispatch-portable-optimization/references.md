# Primary-source ledger

## Rust code generation and target features

- [rustc code-generation options](https://doc.rust-lang.org/rustc/codegen-options/index.html#target-cpu)
  defines `target-cpu`, `target-feature`, and the host-dependent `native`
  setting. Scope: stable Rust documentation at the link. A measurement record
  must name the exact compiler version.
- [Rust `target_feature`
  reference](https://doc.rust-lang.org/stable/reference/attributes/codegen.html#the-target_feature-attribute)
  defines the unsafe call contract, inlining restrictions, and the distinction
  between function attributes and crate-wide `cfg(target_feature)`.
- [Rust dynamic CPU feature
  detection](https://doc.rust-lang.org/stable/core/arch/#dynamic-cpu-feature-detection)
  documents the checked wrapper pattern.
- [Rust x86 runtime detection
  macro](https://doc.rust-lang.org/std/macro.is_x86_feature_detected.html) and
  [AArch64 runtime detection
  macro](https://doc.rust-lang.org/std/arch/macro.is_aarch64_feature_detected.html)
  define the architecture-specific interfaces. Both can expand to `true` when
  the feature is enabled globally.
- [`std_detect` source](https://doc.rust-lang.org/stable/src/std_detect/detect/mod.rs.html)
  shows the implementation boundary behind Rust's detection macros. Scope:
  implementation evidence for the linked stable toolchain, not a stable API
  contract.

## x86 execution-state legality

- [Intel AVX and AVX2 detection
  note](https://www.intel.com/content/dam/develop/external/us/en/documents/how-to-detect-new-instruction-support-in-the-4th-generation-intel-core-processor-family.pdf)
  checks `OSXSAVE`, then `XCR0` XMM/YMM state, before leaf-7 features.
- [Intel 64 and IA-32 Software Developer's
  Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
  defines CPUID, XGETBV, XCR0, and instruction feature requirements. Scope:
  the manual revision linked by Intel; check the current revision for new
  extensions.

## Linux AArch64

- [Linux arm64 ELF
  hwcaps](https://www.kernel.org/doc/html/latest/arch/arm64/elf_hwcaps.html)
  specifies `AT_HWCAP` and the supported feature-discovery contract.
- [Linux Scalable Vector Extension (SVE) userspace
  ABI](https://www.kernel.org/doc/html/latest/arch/arm64/sve.html) specifies
  per-thread vector length, `PR_SVE_GET_VL`, `PR_SVE_SET_VL`, and `execve`
  behavior. Scope: the kernel documentation at the link; a measurement record
  must name the deployed kernel.
- [Arm C Language Extensions
  (ACLE)](https://arm-software.github.io/acle/main/acle.html)
  defines vector-length-agnostic and fixed-length SVE boundaries. Scope: the
  rendered ACLE revision at the link.

## Multiversioning and loader dispatch

- [GCC function
  multiversioning](https://gcc.gnu.org/onlinedocs/gcc/Function-Multiversioning.html)
  defines `target_clones` and resolver generation for supported targets.
  Scope: the compiler documentation at the link; target support varies by GCC
  version.
- [Clang `target_clones`
  attribute](https://clang.llvm.org/docs/AttributeReference.html#target-clones)
  defines clone priority and target support. Scope: the compiler documentation
  at the link; target support varies by Clang version.
- [glibc indirect
  functions](https://snapshots.sourceware.org/glibc/trunk/latest/manual/html_node/Indirect-Functions.html)
  documents indirect-function (IFUNC) binding, resolver multiplicity,
  concurrency, and resolver restrictions. Scope: the linked glibc development
  manual; deployment behavior must be checked against the deployed glibc
  version.
- [`ld.so(8)`](https://man7.org/linux/man-pages/man8/ld.so.8.html#NOTES)
  documents glibc-hwcaps loader search behavior. Scope: glibc 2.33 and later
  for the documented hwcaps directory mechanism.

## Evidence classification

In a completed record, raw process rows are measurements of exact recorded
processes. Medians, quartiles, throughput, and paired ratios are derived from
those rows. Instructions in the retained linked binary are observed code
generation. Explanations involving dispatch cost, inlining, frontend pressure,
or instruction behavior remain inferences unless a retained counter or
controlled perturbation measures them directly.
