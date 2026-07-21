# Primary references

These sources define the hardware counters, operating-system clocks, conversion
parameters, and estimator boundaries used by the artifact.

- [Intel 64 and IA-32 Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) — `RDTSC`, fence ordering, TSC feature evidence, invariant TSC, and CPUID frequency leaves.
- [AMD64 Architecture Programmer's Manual](https://docs.amd.com/v/u/en-US/40332_4.09_APM_PUB) — AMD fence, serialization, timestamp, and feature contracts.
- [Arm Architecture Reference Manual](https://developer.arm.com/documentation/ddi0487/latest/) — generic-timer registers, ordering, and feature boundaries.
- [Arm Generic Timer guide](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/Generic%20Timer.pdf?revision=c710e7a7-9f52-4901-8c9d-91b19f44f9c7) — `CNTVCT_EL0`, `CNTFRQ_EL0`, and `ISB` ordering examples.
- [Linux `perf_event_mmap_page` UAPI](https://github.com/torvalds/linux/blob/master/include/uapi/linux/perf_event.h) and [`perf_event_open(2)`](https://man7.org/linux/man-pages/man2/perf_event_open.2.html) — sequence counter, RDPMC, `cap_user_time`, `cap_user_time_zero`, short-clock reconstruction, and conversion formulas.
- [Linux arm64 user-space perf access](https://docs.kernel.org/arch/arm64/perf.html) — arm64 PMU access policy, `config1`, counter width, and mmap-page validity.
- [Linux RDPMC sysfs ABI](https://docs.kernel.org/admin-guide/abi-testing.html) — x86 user-space RDPMC modes and scope.
- [`clock_gettime(2)`](https://man7.org/linux/man-pages/man2/clock_gettime.2.html) and [`vdso(7)`](https://man7.org/linux/man-pages/man7/vdso.7.html) — Linux clock semantics and user-space delivery path.
- [KVM x86 timekeeping](https://docs.kernel.org/virt/kvm/x86/timekeeping.html) — guest TSC offset, scaling, stability, and migration boundaries.
- [`git archive`](https://git-scm.com/docs/git-archive) and [`git get-tar-commit-id`](https://git-scm.com/docs/git-get-tar-commit-id) — commit-bound source archives and extraction of their embedded commit IDs.
- [Chen and Revels, *Robust benchmarking in noisy environments*](https://arxiv.org/abs/1608.04295) — lower-envelope estimators and timer-error limits.
- [`llvm-exegesis`](https://llvm.org/docs/CommandGuide/llvm-exegesis.html) — instruction latency, inverse throughput, and PMU-backed snippet measurement.
