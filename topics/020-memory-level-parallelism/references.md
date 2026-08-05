# References

- [Little, “A Proof for the Queuing Formula: L = λW”](https://doi.org/10.1287/opre.9.3.383)
  proves the steady-state identity. Numerator and denominator populations must
  match.
- [Kroft, “Lockup-free instruction fetch/prefetch cache organization”](https://doi.org/10.1145/800052.801868)
  introduced miss-status tracking for a non-blocking cache. Current processors
  use model-specific structures and limits.
- [Intel Sapphire Rapids core events](https://raw.githubusercontent.com/intel/perfmon/main/SPR/events/sapphirerapids_core.json)
  define `L1D_PEND_MISS.PENDING`, `PENDING_CYCLES`, `FB_FULL`,
  `LD_BLOCKS.ADDRESS_ALIAS`, `LD_BLOCKS.STORE_FORWARD`, `LD_BLOCKS.NO_SR`, and
  `MEM_INST_RETIRED.SPLIT_LOADS`.
- [Intel 64 and IA-32 Optimization Reference Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html)
  documents memory disambiguation, store forwarding, alignment, and
  model-specific optimization boundaries.
- [Arm Neoverse V1 performance-analysis methodology](https://developer.arm.com/community/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/arm-neoverse-v1-top-down-methodology)
  links the V1 PMU guide and telemetry definitions.
- [Linux Arm SPE documentation](https://raw.githubusercontent.com/torvalds/linux/master/tools/perf/Documentation/perf-arm-spe.txt)
  defines perf integration for Statistical Profiling Extension sampling. SPE
  samples latency and data sources; it does not directly count concurrent
  misses.
- [Kiriansky et al., “Cimple: Instruction and Memory Level Parallelism”](https://arxiv.org/abs/1807.01624)
  evaluates coroutine and batching transformations for independent in-memory
  operations.
- [Rust `read_unaligned`](https://doc.rust-lang.org/std/ptr/fn.read_unaligned.html)
  states the pointer-validity contract for an unaligned typed read. The focused
  probe uses naturally aligned nodes instead.
