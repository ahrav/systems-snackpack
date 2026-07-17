# Measurements

The checked-in runner records one directory per host. Each record includes:

- uname, CPU identity, online and allowed CPUs;
- rustc, Cargo, GCC, target features, and build flags;
- exact source and benchmark-binary hashes;
- correctness output and 72 timed process records;
- focused and full generated assembly;
- workspace validation logs;
- a host summary and cross-host comparison.

Timing records report one non-inlined kernel call after warmup. Setup, process
startup, correctness checks, and output remain outside `timed_ns`.

The host-specific records are added only after both required Linux hosts rerun
the exact pushed source candidate. Median intervals use independent,
identically distributed continuous pair ratios as their coverage model.
