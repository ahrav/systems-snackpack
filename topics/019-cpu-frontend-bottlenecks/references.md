# Primary sources

- [Intel VTune CPU metrics
  reference](https://www.intel.com/content/www/us/en/docs/vtune-profiler/user-guide/2026-1/cpu-metrics-reference.html):
  top-down slot accounting and the Front-End Bound definition.
- [Yasin, *A Top-Down Method for Performance Analysis and Counters
  Architecture*](https://doi.org/10.1109/ISPASS.2014.6844459): hierarchical
  pipeline-slot analysis and its measurement method.
- [Intel optimization reference
  manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html):
  model-specific frontend organization, instruction delivery, and tuning rules.
- [Intel Jump Conditional Code mitigation
  guidance](https://www.intel.com/content/www/us/en/developer/articles/technical/software-security-guidance/best-practices/mitigation-strategies-jcc-microcode.html):
  the affected processor boundary and targeted 32-byte-boundary mitigations.
- [AMD uProf pipeline
  utilization](https://docs.amd.com/r/en-US/57368-uProf-user-guide/4.7.1.-Pipeline-Utilization):
  frontend latency and bandwidth categories on supported AMD processors.
- [Arm Neoverse V1 frontend
  description](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/neoverse-v1-platform-a-new-performance-tier-for-arm):
  V1 macro-operation-cache and decode-path widths.
- [Arm Neoverse V2 technical reference
  manual](https://documentation-service.arm.com/static/633fe1ec4c59b30b517730b8):
  V2 performance-monitoring and implementation details.
- [GCC optimization
  options](https://gcc.gnu.org/onlinedocs/gcc-15.2.0/gcc/Optimize-Options.html):
  hot/cold block partitioning, section placement, and target restrictions.
- [LLVM BOLT
  README](https://github.com/llvm/llvm-project/blob/main/bolt/README.md) and
  [BOLT paper](https://arxiv.org/abs/1807.06735): post-link block and function
  layout for ELF binaries.
- [Rust code-generation
  attributes](https://doc.rust-lang.org/reference/attributes/codegen.html):
  the contract and limitations of `#[cold]` and `#[inline]`.
- [`perf-stat(1)`](https://man7.org/linux/man-pages/man1/perf-stat.1.html) and
  [`perf-list(1)`](https://man7.org/linux/man-pages/man1/perf-list.1.html):
  event discovery, grouping, scaling, and running-time reporting.
