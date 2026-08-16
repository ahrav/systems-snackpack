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
unbalanced, and it now resolves `--binary` to an absolute path so the hashed
file is the executed file. Its current digest therefore differs from the digest
recorded in each `SHA256SUMS.txt`; both promoted runs used the even 12-block
schedule the guard now requires and passed an absolute binary path, so the
retained rows are unaffected. Every other measured source file still matches its
recorded digest byte for byte.

Each `SHA256SUMS.txt` mixes two kinds of entry. The repository-relative source
lines are verifiable from the repository root:

```
grep -v '^[0-9a-f]\{64\}  /tmp/' \
  topics/036-roaring-bitmaps-compressed-sets/measurements/2026-08-15-x86-64/SHA256SUMS.txt \
  | grep -v run_processes.py | sha256sum -c
```

The `/tmp` lines name the source archive and the generic and native binaries as
they existed on the build host. Those bytes are deliberately not retained here:
the archive was a transfer artifact and compiled binaries are not committed.
Their digests remain the record that the timed rows, `verify-*.txt` output, and
`symbols.txt` came from one specific build, and the paths are kept verbatim as
produced rather than rewritten to paths that never existed.

Generated instructions establish linked code shape, not causal attribution.
CPU identity and feature flags are host evidence, not evidence for an entire
instruction-set architecture or vendor family. The cases isolate five
deterministic chunk shapes; they do not represent a production distribution or
a complete Roaring implementation.
