# Measurement contract

Freeze src/lib.rs, examples/ports.rs, Cargo.toml and run.py before each campaign.
The runner records SHA-256 identities, declared source identity, exact binary hash,
hostname, architecture, kernel, CPU data, compiler, native flags and allowed CPUs.
Required hosts: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com (Arm), and SSH alias
xxl (runtime-resolved x86-64). Pin each process to its first allowed CPU.

Three candidates: scan, bitmap, tree. Six cases: tiny (64 ports, 1 destination,
16 occupied); crowded (4096, 1, 3891); full (4096, 1, 4096); spread (4096, 16,
1024 per destination); skew (4096, 16, 3891 in destination zero, 16 elsewhere,
90% forced hot churn plus incidental hot traffic); short (4096, 16, initially
empty, 32 steps). Other cases have 10000 churn steps. Each step releases a
seeded selected occupied slot and allocates the lowest free port. A full pool
also attempts allocation before release to check rejection. Initial filling is
ascending. Global limit is unlimited in timed traces; separate tests cover it.

One fresh-process warmup per candidate/cell. Six measured blocks enumerate all
six candidate permutations: 216 measured and 36 warmup processes per host.
Each process performs its independent oracle and candidate validation before
measurement. No cold-cache claim. Fixed seed controls event generation; oracle
hash order does not affect outputs. Process blocks, not events, are samples.

Full boundary: pool construction, initial filling, events, result-buffer writes,
checksum and pool destruction. Steady boundary: events, result-buffer writes and
checksum after construction/filling. Both exclude result-buffer allocation/drop,
trace/oracle creation, verification, compilation and process startup. Steady also
excludes pool destruction. No storage or network work is measured. Thus full is
an allocator lifecycle boundary, not end-to-end application latency.

Winner: a unique candidate achieves rival_ns/candidate_ns >= 1.05 against each rival in every
one of six paired blocks. Otherwise unresolved, not an equivalence claim. Report median
and min/max dispersion for every candidate/cell. Do not rerun for a preferred
winner. The initial and exact committed campaigns stay separate.

No PMU attribution, kernel packet throughput, cloud capacity, concurrency,
production port randomization, timeout-engine, or ISA-family claims. The oracle
and validation warm code/data and are outside the timer. Different compiler
versions and hosts prohibit interpreting cross-host differences as an ISA effect.
