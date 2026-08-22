# Primary references

- [Spectre Attacks: Exploiting Speculative Execution](https://spectreattack.com/spectre.pdf) introduces transient-execution attacks and their threat model.
- [Linux Spectre documentation](https://docs.kernel.org/admin-guide/hw-vuln/spectre.html) describes kernel terminology, affected boundaries, and mitigation reporting.
- [Linux x86 barrier definitions](https://github.com/torvalds/linux/blob/master/arch/x86/include/asm/barrier.h) provides the kernel's x86 speculation-barrier primitives.
- [Linux arm64 barrier definitions](https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/barrier.h) provides the kernel's AArch64 dependency and barrier sequences.
- [Intel speculative-execution side-channel mitigations](https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/technical-documentation/speculative-execution-side-channel-mitigations.html) gives current vendor guidance for Intel processors.
- [Arm cache speculation side-channels guidance](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Security%20Update%2008%20June%202020/Cache_Speculation_Side-channels-v2.5.pdf) defines the Arm sequences used by this artifact.
- [LLVM Speculative Load Hardening](https://llvm.org/docs/SpeculativeLoadHardening.html) explains compiler-wide data-flow hardening and its cost model.
- [Rust `asm!` reference](https://doc.rust-lang.org/reference/inline-assembly.html) defines the inline-assembly operands and options used by the lookup shapes.

These sources support mechanism and toolchain claims. A validated host receipt,
when checked in, defines the measurement boundary. Neither source class proves
that these lookup shapes close a production trust boundary.
