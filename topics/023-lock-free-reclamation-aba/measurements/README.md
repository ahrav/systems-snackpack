# Measurement contract

Each retained host run records source and binary hashes, host identity, kernel,
CPU count and affinity, compiler versions, native target features, final-binary
code generation, correctness replicates, process rows, summaries, and a checksum
manifest.

The correctness phase launches 32 fresh pinned processes. Every process must
show the raw negative control accepting stale A and reintroducing B, while the
tagged treatment rejects generation 0 after the head reaches generation 3.

The timed comparison uses 12 complete `ABBA` or `BAAB` process blocks. Each
letter launches a fresh process and each block contributes one log-ratio
contrast. Six raw/raw blocks provide an A/A control. Loop iterations and the
four positions inside a block are not independent samples.

The point estimate is the geometric mean tagged/raw ratio. The two-sided 95%
Student-t interval uses the sample standard deviation among the 12 block log
contrasts. It covers temporal process-block variation within one build, CPU,
host, and run window. It does not cover other binaries, CPUs, hosts, contention
levels, or reclamation workloads.

Startup and warmup are outside the timed region. The measured kernel uses one
private hot `AtomicU64` and performs two successful CAS operations per
iteration. The result excludes reclamation scans, allocator work, destruction,
stalled participants, and contention.

Retained records:

Provenance notes for the `6b20b1f` receipts:

- Each retained `host.txt` line `RUSTFLAGS=<unset>` records the ambient
  environment at run start, not the build flags. The measured build always
  applied `-C target-cpu=native -C codegen-units=1`, as fixed by
  `experiment/run_host.sh` at that commit; the runner now records both the
  ambient and the effective build flags.
- Each retained `receipt-validation.txt` was produced by the validator as of
  commit `6b20b1f`, which checked counts, controls, and interval ordering
  only. The strengthened validator (exact witness lines, predeclared
  schedule, kernel final-word and checksum contracts, and summary
  recomputation from `raw.csv`) re-passes both retained receipt sets.

- [Resolved `xxl` x86-64 host](xxl-2026-08-02.md)
- [Required Arm host](arm-2026-08-02.md)
- [Cross-host comparison](comparison-2026-08-02.md)
- [Raw exact-source receipts](raw/6b20b1f/)
