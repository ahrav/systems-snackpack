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
