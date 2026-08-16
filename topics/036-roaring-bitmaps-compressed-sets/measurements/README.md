# Measurement contract

This directory defines and, after measurement, retains exact-source Linux
evidence for the single-chunk array, bitmap, and run intersection-cardinality
kernels.

Each promoted host record names:

- the shared source-archive Secure Hash Algorithm 256-bit (SHA-256) digest and
  the per-file SHA-256 digest of every measured source file, which pin the
  measured bytes in place of a source commit identifier;
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

After both promoted runs, `experiment/run_processes.py` gained a guard that
rejects odd `--blocks`, because an odd count leaves the alternating schedule
unbalanced. Its current digest therefore differs from the digest recorded in
each `SHA256SUMS.txt`; both promoted runs used the even 12-block schedule the
guard now requires, so the retained rows are unaffected. Every other measured
source file still matches its recorded digest byte for byte.

Generated instructions establish linked code shape, not causal attribution.
CPU identity and feature flags are host evidence, not evidence for an entire
instruction-set architecture or vendor family. The cases isolate five
deterministic chunk shapes; they do not represent a production distribution or
a complete Roaring implementation.
