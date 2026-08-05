# Primary sources

First accessed 2026-07-31.

- [Intel 64 and IA-32 Architectures Optimization Reference Manual, revision
  050](https://cdrdv2.intel.com/v1/dl/getContent/821612?fileName=248966-Optimization-Reference-Manual-V1-050.pdf):
  write-combining stores, cache behavior, store forwarding, and ordering costs.
- [Intel perfmon map at commit
  `6e3329d`](https://github.com/intel/perfmon/blob/6e3329d20457aad11d8cc323b85aa6a16b075918/mapfile.csv)
  and [Sapphire Rapids core event table at the same
  commit](https://github.com/intel/perfmon/blob/6e3329d20457aad11d8cc323b85aa6a16b075918/SPR/events/sapphirerapids_core.json):
  pinned model-to-event mapping and event definitions for later mechanism
  measurements.
- [Arm Neoverse V1 Software Optimization
  Guide](https://documentation-service.arm.com/static/668ba8c29082ad344b14c3eb):
  V1 pipeline, cache, load/store, and dependency guidance.
- [Arm `STNP`](https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/STNP--Store-Pair-of-Registers--with-non-temporal-hint-):
  architectural semantics of the non-temporal pair-store hint.
- [Arm `STLR`](https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/STLR--Store-Release-Register-):
  architectural semantics of release publication.
- [Rust `_mm256_stream_si256`](https://doc.rust-lang.org/core/arch/x86_64/fn._mm256_stream_si256.html)
  and [Rust `_mm_sfence`](https://doc.rust-lang.org/stable/core/arch/x86_64/fn._mm_sfence.html):
  alignment, target-feature, streaming-store, and store-fence contracts used by
  the x86-64 kernel.
- [LLVM 21.1.0 store instruction and `!nontemporal`
  metadata](https://releases.llvm.org/21.1.0/docs/LangRef.html#store-instruction):
  the IR-level non-temporal hint contract. Topic 21 uses target-specific
  intrinsics and assembly, then gates the final linked instructions.
