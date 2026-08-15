# Measurement contract

This directory defines and, after measurement, retains exact-source Linux
evidence for the single-chunk array, bitmap, and run intersection-cardinality
kernels.

Each promoted host record names:

- the source commit and shared source-archive Secure Hash Algorithm 256-bit
  (SHA-256) digest;
- the Secure Shell (SSH) target, resolved hostname, architecture, kernel,
  central processing unit (CPU) model, target features, and available CPU count;
- Rust, Cargo, C compiler, and binary-tools versions plus exact build flags;
- the generic and native binary digests and correctness output;
- the pinned CPU, target duration, fixed block counts, and process schedule;
- every raw child row, external wall time, exit status, and summary row; and
- linked symbols and disassembly for all three kernels.

Elapsed time covers repeated intersection cardinality after construction,
oracle validation, calibration, and warmup. External wall time also covers
process startup and the excluded work. The 12 paired process blocks are the
analysis units. Inner iterations are subsamples and do not increase the run
count. The inclusive interquartile range describes block-to-block variation in
that exact host and run window.

Generated instructions establish linked code shape, not causal attribution.
CPU identity and feature flags are host evidence, not evidence for an entire
instruction-set architecture or vendor family. The cases isolate five
deterministic chunk shapes; they do not represent a production distribution or
a complete Roaring implementation.
