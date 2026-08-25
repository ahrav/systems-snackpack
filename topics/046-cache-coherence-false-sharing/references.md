# Topic 46 primary sources

Each source below has a narrow scope. Protocol names and performance events are
not portable processor-family guarantees.

## Coherence and false sharing

- [Linux kernel false-sharing guide](https://docs.kernel.org/kernel-hacking/false-sharing.html)
  defines true and false sharing, describes cache-line granularity, and gives a
  `perf c2c` diagnosis workflow. The page tracks the kernel documentation and
  does not guarantee event support on every processor or virtual machine.
- [Bolosky and Scott, *False Sharing and Its Effect on Shared Memory
  Performance*](https://www.usenix.org/conference/sedms-iv/false-sharing-and-its-effect-shared-memory-performance)
  separates source-level sharing from coherence-block sharing. Its machine and
  protocol observations belong to the systems measured in the paper.
- [Linux `perf c2c` manual](https://github.com/torvalds/linux/blob/master/tools/perf/Documentation/perf-c2c.txt)
  defines cache-to-cache reporting and its architecture-specific sampled memory
  events. Snoop hit modified (HITM) samples can include true or false sharing;
  sample totals are not ownership-handoff counts.

## Exact architecture boundaries

- [Arm Neoverse V1 Core Technical Reference Manual,
  101427_0101_05_en](https://documentation-service.arm.com/static/6088335985368c4c2b1c266d)
  identifies `MIDR_EL1` part number `0xD40` as Neoverse V1 in section B2.101,
  specifies 64-byte L1 data-cache lines in sections A2.1.6 and A6.1.2, and
  describes near and far cacheable atomics over CHI in section A6.4.1. These
  facts identify the measured core and possible core interface behavior, not
  the complete Graviton3 system fabric or the path taken by one operation.
- [Intel 64 and IA-32 Architectures Optimization Reference Manual, order
  248966-050](https://cdrdv2-public.intel.com/821612/248966-Optimization-Reference-Manual-V1-050.pdf)
  documents Intel cache and locked-operation optimization guidance. Apply its
  model-specific guidance only after identifying the exact processor.
- [Intel, *An Introduction to the Intel QuickPath
  Interconnect*](https://www.intel.com/content/dam/doc/white-paper/quick-path-interconnect-introduction-paper.pdf)
  describes MESIF in the QuickPath Interconnect protocol on pages 15–16. It
  does not make MESIF an x86 instruction-set rule or establish the private
  implementation of the measured Xeon.
- [Arm AMBA AXI and ACE Protocol Specification,
  IHI0022H](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/IHI0022H_amba_axi_protocol_spec.pdf)
  defines ACE states such as Unique Clean, Unique Dirty, Shared Clean, Shared
  Dirty, and Invalid in sections D4.3.2 and D4.4. ACE is a useful comparison,
  not the exact CHI interface named by the Neoverse V1 manual.
- [AMD64 Architecture Programmer's Manual Volume 2, revision
  3.44](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2) documents AMD's
  MOESDIF protocol in section 7.3. It illustrates why MESI is only shared
  vocabulary; it is not evidence about either host measured in this round.

## Language and layout boundaries

- [Rust `std::sync::atomic::Ordering`](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html)
  defines `Relaxed` as atomic operations without ordering guarantees. It does
  not disable hardware coherence.
- [Rust type layout reference](https://doc.rust-lang.org/reference/type-layout.html)
  defines representation and alignment rules. The probe uses `repr(C,
  align(128))`, compile-time size checks, and runtime address checks because
  alignment alone does not promise the needed field stride.
- [C++ proposal P0154R1](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2016/p0154r1.html)
  explains constructive and destructive interference sizes and why one
  compile-time constant cannot capture every hierarchy or runtime target.
