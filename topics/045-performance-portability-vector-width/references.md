# Primary sources and boundaries

- [Intel 64 and IA-32 Architectures Optimization Reference Manual, volume 1,
  revision 050](https://cdrdv2-public.intel.com/821612/248966-Optimization-Reference-Manual-V1-050.pdf)
  documents Intel optimization guidance. Processor-specific sections do not
  define behavior for every Intel model.
- [Intel AVX-512 Instruction Set for Packet Processing, document 633930-003](https://cdrdv2-public.intel.com/633930/IntelAVX-512_InstructionSetForPacketProcessing_TechGuide_633930v3.pdf)
  describes Advanced Vector Extensions 512 (AVX-512) light and heavy
  instruction classes, active-core effects, and generation-specific frequency
  behavior. Its first-generation Xeon Scalable transition timings are not
  universal constants.
- [Intel Software Optimization Manual changes, document 355308-048,
  section 2.5.3](https://cdrdv2-public.intel.com/821613/355308-Software-Optimization-Manual-048-Changes-Doc-2.pdf)
  records Skylake Server license-transition details, including approximate
  grant and return times. The section's processor boundary is part of the claim.
- [Intel Sapphire Rapids core performance-monitoring events](https://github.com/intel/perfmon/blob/main/SPR/events/sapphirerapids_core.json)
  is the model-specific event catalog. Event names from another model are not
  interchangeable.
- [Linux `perf_event_open(2)`](https://man7.org/linux/man-pages/man2/perf_event_open.2.html)
  defines `PERF_COUNT_HW_REF_CPU_CYCLES` as cycles not affected by central
  processing unit (CPU) frequency scaling. Availability still depends on the
  processor and environment.
- [The LLVM compiler project's Loop Vectorizer](https://llvm.org/docs/Vectorizers.html)
  documents its profitability cost model, runtime checks, tail handling, and
  vector-width selection. The compiler model does not observe service-level
  follow-on work.
- [GNU Compiler Collection (GCC) 11.5 x86 function attributes](https://gcc.gnu.org/onlinedocs/gcc-11.5.0/gcc/x86-Function-Attributes.html)
  documents target-specific function compilation for the compiler version used
  by both checked-source hosts. The checked-in C experiment uses these target
  attributes.
- [Arm Neoverse V1 platform overview](https://community.arm.com/developer/ip-products/processors/b/processors-ip-blog/posts/neoverse-v1-platform-a-new-performance-tier-for-arm)
  describes two 256-bit Scalable Vector Extension (SVE) or four 128-bit Advanced
  Single Instruction, Multiple Data (Advanced SIMD) and floating-point
  execution paths for Neoverse V1. This is a vendor microarchitecture claim,
  not a guarantee for every Arm processor.
- [Arm C Language Extensions for Scalable Vector Extension (SVE)](https://arm-software.github.io/acle/main/acle.html#sve-intrinsics)
  defines vector-length-agnostic SVE programming. It establishes semantics, not
  a speedup for a workload.
- [AMD 4th Gen EPYC Processor Architecture, publication 58008](https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/221704010-B_en_4th-Gen-AMD-EPYC-Processor-Architecture---White-Paper_pdf.pdf)
  states that Zen 4 executes 512-bit operations through 256-bit data paths over
  sequential cycles. The vendor's frequency claim applies to that generation.
- [AMD 5th Gen EPYC Processor Architecture, publication 70353 revision B](https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/5th-gen-amd-epyc-processor-architecture-white-paper.pdf)
  describes Zen 5's 512-bit data paths and a firmware option that splits 512-bit
  operations into two 256-bit operations for power efficiency.
- [Gottschlag et al., “The Price of Using the Wrong CPU Feature,” USENIX Annual
  Technical Conference 2021](https://www.usenix.org/system/files/atc21-gottschlag.pdf)
  measures Advanced Vector Extensions (AVX) scheduling externalities on its
  stated Xeon Gold 6130 setup. The measured transition and sibling effects do
  not transfer unchanged to another processor generation.
