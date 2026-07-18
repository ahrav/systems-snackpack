# Measurements

The exact pushed candidate was commit
`26b49a55473a8fc43b73d6e5e4ef58a7d72f3698`; its source archive SHA-256 was
`ba4a0704a4431c22714fdaa6111c144dcfa8da9a7cae246fce0a077a5ecaf217` on both
hosts.

- [AArch64 host](2026-07-17-dev-dsk-ahrav-2b.md)
- [x86-64 host](2026-07-17-dev-dsk-ahrav-2c.md)
- [Cross-host comparison](2026-07-17-cross-host.md)
- [Raw evidence](raw/26b49a5/)

Each raw host directory includes:

- uname, CPU identity, online and allowed CPUs;
- rustc, Cargo, GCC, target features, and build flags;
- exact source and benchmark-binary hashes;
- correctness output and 72 timed process records;
- focused and full generated assembly;
- workspace validation logs;
- a benchmark summary and run manifest.

Timing records report one non-inlined kernel call after warmup. Setup,
correctness checks, process launch, and output remain outside `timed_ns` and
are retained separately. The 72 `RESULT` lines are the raw process-level
observations. Median intervals use independent, identically distributed
continuous pair ratios as their coverage model.
