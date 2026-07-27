# Linux cross-host note: 2026-07-27

Both hosts ran the same source commit, archive bytes, C source generator,
compiler flags, glibc version, GNU linker version, 4,096-import workload,
CPU-0 affinity, and process schedule. Their final ELF hashes and machine
instructions differ, so this is not a controlled ISA or vendor comparison.

Eager/lazy startup was 1.1534 on the probed AArch64 host and 1.1333 on the
probed x86-64 host. First-use was 0.11777 and 0.07967, respectively. Each point
estimate uses 12 blocks and 48 fresh processes; its interval is in the
host-specific record. Both observations agree with the predicted placement
shift: eager binding pays more before `main` and less at first use.

Resolved steady behavior differed by host and remains unexplained. The
AArch64 samples and A/A control were highly dispersed; the x86-64 A/A control
was narrow, but the causal arms still have the same resolved call sequence.
Neither result supports an ISA, vendor, or loader-throughput claim.

Measured evidence comprises elapsed intervals, correctness checks, final ELF
metadata, relocations, program headers, dynamic tags, disassembly, binary
hashes, and host/toolchain records. The latency-placement explanation is an
inference supported by the same-image treatment and ELF evidence. Any
steady-state mechanism is unmeasured.
