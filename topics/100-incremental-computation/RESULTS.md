# Results

Measured source: `36160211a02b69e3a9d2dc939788bbc18c898ae0`.
The published documentation commit preserves these implementation and experiment bytes.

Each host passed 3 unit tests, 1 doctest and 6000 SQLite-oracle method comparisons across 3000 snapshots (2216 accepted, 784 rejected).

## Timing

Eight paired trials per cell, alternating method order; one fresh process per method/trial. Eight warmup processes and 64 measured processes per host. Linux affinity CPU 0. Release build, repository Rust 1.93.1, default release flags. Timed scope and controls are defined in README.md.

Winner rule declared in the committed harness: greater than 5 percent in every paired comparison; otherwise unresolved.

| Host | Keys / changed | Delta median [min,max], us | Recompute median [min,max], us | Winner |
|---|---:|---:|---:|---|
| arm | 65536/1 | 0.042 [0.041,0.043] | 54.936 [54.880,56.404] | delta |
| arm | 65536/256 | 9.819 [9.716,11.005] | 64.640 [64.447,65.216] | delta |
| arm | 65536/65536 | 6298.101 [6289.761,6314.962] | 6258.625 [6248.091,6276.838] | unresolved |
| arm | 8/8 | 0.164 [0.163,0.169] | 0.166 [0.163,0.178] | unresolved |
| x86 | 65536/1 | 0.036 [0.035,0.092] | 36.929 [36.760,37.545] | delta |
| x86 | 65536/256 | 8.045 [7.892,8.643] | 44.896 [44.388,45.192] | delta |
| x86 | 65536/65536 | 6331.933 [6320.925,6341.063] | 6327.844 [6316.143,6353.003] | unresolved |
| x86 | 8/8 | 0.134 [0.132,0.149] | 0.153 [0.126,0.161] | unresolved |
| local | 65536/1 | 0.058 [0.050,0.071] | 23.777 [20.675,25.317] | delta |
| local | 65536/256 | 6.196 [5.950,6.567] | 28.562 [27.780,32.608] | delta |
| local | 65536/65536 | 3624.117 [3517.906,3779.547] | 3637.294 [3523.167,4100.562] | unresolved |
| local | 8/8 | 0.102 [0.086,0.124] | 0.103 [0.095,0.106] | unresolved |

Sparse batches favor delta maintenance on both Linux hosts. Dense and tiny cells remain unresolved by the declared criterion. Unresolved does not establish equivalence. The shared BTreeMap batch processing dominates dense work; that explanation is an inference from the implementation, without a profile isolating its cost.

Arm: Linux aarch64, CPU implementer 0x41 / part 0xd40. x86: SSH alias xxl resolved to Linux x86_64, Intel Xeon Platinum 8488C. Both kernels 6.12.113-138.209.amzn2023. Local: macOS arm64, no CPU affinity; the local run overlapped workspace validation and is supplemental. Toolchain logs distinguish the shell default compiler printed before changing directory from the actual repository-pinned compiler.

Memory footprint, distributed completion, iterative dataflows, trace compaction, crash recovery and full row output were not measured. Startup and arrangement construction are excluded. Load, frequency, thermals, sibling activity and virtual host placement were uncontrolled.

## Validation

All six repository workspace checks passed: format, Clippy, library/bin/example tests, doctests, benchmark compilation and warning-free rustdoc. The probe checks output checksums in every timing process. Separate unit tests check rejected batches leave complete state intact.

The three host archive SHA256 values match source.sha256. A local checker compares the retained archive members with committed source bytes. Initial preparation errors (wrong command directory and missing example crate documentation) were corrected before the measured commit. Hook log and credential-refresh warnings did not prevent commits.
