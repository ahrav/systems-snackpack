# References

- [Intel Optimization Reference Manual, Volume 2, revision 050](https://cdrdv2.intel.com/v1/dl/getContent/787036) — Vendor-documented Intel optimization guidance; apply each claim only to the processors named by the manual.
- [AMD Zen 5 Software Optimization Guide, revision 1.00](https://docs.amd.com/v/u/en-US/58455_1.00) — Vendor-documented Zen 5 guidance; it does not describe every x86-64 core.
- [Arm Neoverse V2 Software Optimization Guide, issue 3.0](https://documentation-service.arm.com/static/668bc0a369e89f01e39c4668) — Vendor-documented Neoverse V2 guidance; it does not describe every AArch64 core.
- [Granlund and Montgomery, PLDI 1994](https://gmplib.org/~tege/divcnst-pldi94.pdf) — Derives multiplication-based division by invariant integers.
- [LLVM `DivisionByConstantInfo` source](https://github.com/llvm/llvm-project/blob/main/llvm/lib/Support/DivisionByConstantInfo.cpp) — Current conceptual source reference on LLVM's `main` branch; it is not pinned to LLVM 21.1.8 or a source of latency evidence.
- [`llvm-mca` documentation](https://llvm.org/docs/CommandGuide/llvm-mca.html) — Current conceptual reference for the tool's scheduling-model analysis; it is not pinned to LLVM 21.1.8.
- [uops.info methodology paper](https://arxiv.org/abs/1810.04610) — Describes the third-party method used to measure instruction latency, throughput, ports, and micro-ops.
- [uops.info `POPCNT` operand measurements](https://uops.info/html-instr/POPCNT_R64_R64.html) — Reports operand-specific measurements for listed CPU models.
- [uops.info AVX2 gather measurements](https://uops.info/html-instr/VPGATHERDD_YMM_VSIB_YMM_YMM.html) — Reports gather measurements for listed CPU models and operand forms.
- [Rust `ptr::read_unaligned`](https://doc.rust-lang.org/std/ptr/fn.read_unaligned.html) — States the API contract for reading a value from a potentially unaligned address.
- [Rust undefined-behavior alignment rules](https://doc.rust-lang.org/reference/behavior-considered-undefined.html) — Defines when Rust requires places and pointer accesses to satisfy alignment rules.
