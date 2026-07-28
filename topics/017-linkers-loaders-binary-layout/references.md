# Primary sources

- [ELF program headers](https://gabi.xinuos.com/elf/07-pheader.html): segment
  mapping, alignment, permissions, and `PT_LOAD`.
- [ELF symbols](https://gabi.xinuos.com/elf/05-symtab.html): binding, visibility,
  and symbol identity.
- [ELF dynamic linking](https://gabi.xinuos.com/elf/08-dynamic.html): dynamic
  tags, relocation tables, dependencies, and PLT metadata.
- [x86-64 psABI](https://gitlab.com/x86-psABIs/x86-64-ABI): x86-64 relocation,
  PLT, GOT, TLS, and code-model contracts.
- [Arm ABI 2025Q4](https://github.com/ARM-software/abi-aa/releases/tag/2025Q4):
  AArch64 relocation, PLT, TLS, and veneer contracts.
- [GNU ld 2.46 manual](https://sourceware.org/binutils/docs/ld.html): linker
  options, scripts, garbage collection, versions, RELRO, and binding policy.
- [glibc 2.43 dynamic-linker hardening](https://sourceware.org/glibc/manual/2.43/html_node/Dynamic-Linker-Hardening.html):
  dependency, initialization, lazy binding, and RELRO guidance.
- [`ld.so(8)`](https://man7.org/linux/man-pages/man8/ld.so.8.html): glibc loader
  environment, lookup, and diagnostic behavior.
- [LLVM LTO](https://llvm.org/docs/LinkTimeOptimization.html) and [address
  significance](https://llvm.org/docs/Extensions.html#sht-llvm-addrsig-section-address-significance-table):
  whole-program visibility and safe identical-code folding metadata.
- [rustc code-generation options](https://doc.rust-lang.org/stable/rustc/codegen-options/)
  and [Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html):
  target-sensitive linker, relocation, LTO, and codegen controls.
- [Mytkowicz et al., ASPLOS
  2009](https://doi.org/10.1145/1508244.1508275): layout-induced measurement
  bias in the paper's evaluated workloads.
- [Stabilizer, ASPLOS
  2013](https://doi.org/10.1145/2451116.2451141): layout randomization as an
  experimental control in the paper's evaluated workloads.
