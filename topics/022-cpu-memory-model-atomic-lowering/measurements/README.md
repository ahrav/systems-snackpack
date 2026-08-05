# Measurements

Final records retain:

- source and binary SHA-256 identities;
- alias and resolved host, architecture, CPU, kernel, toolchain, and features;
- correctness output and native/generic generated code;
- raw fresh-process records and paired summaries;
- native and generic store-buffering observations;
- measured, observed-code-generation, and inferred-mechanism claims as separate facts.

The cost workload uses one hot private line on one pinned thread. It measures
steady loop throughput, not remote visibility, publication, handoff, or
contended ownership transfer. Store-buffering frequencies are sensitive to
binary layout, CPU placement, and coordination timing.

The exact-source records are:

- [Arm host](arm-2026-08-01.md)
- [`xxl` x86 host](xxl-2026-08-01.md)
- [Cross-host comparison](comparison-2026-08-01.md)
- [Raw receipts](raw/5f93fdb)
