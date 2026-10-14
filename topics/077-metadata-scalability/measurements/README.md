# Topic 077 measurements

Exact source commit: `33216b7de0448010e9dcd670f7b0edab99a9680a`. Archive SHA-256:
`bf08fbc9f0bb9f40c58b6a19620a4ce5a49365d97e2e0b42fe3432b06ff337cd`. Every transferred core source and runner hash
matches that commit and the publication tree.

Both Linux hosts used **Rust 1.93.1**, default Cargo release optimization, and
Python 3.9.25. No native CPU flags, pinning, or frequency controls. AArch64 host:
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` (64 logical CPUs).
Verified x86-64 alias `xxl` resolved to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, Intel Xeon Platinum 8488C.
Full OS, CPU and toolchain metadata are retained in each host directory.

| Host | Workload | Snapshot µs/batch: median [min, max] | Delta µs/batch: median [min, max] | Winner |
|---|---|---:|---:|---|
| arm | sparse | 24.608 [24.336, 26.215] | 0.075 [0.074, 0.075] | delta |
| arm | dense | 24.527 [23.854, 24.679] | 133.850 [132.330, 136.180] | snapshot |
| arm | hot | 24.739 [24.144, 25.404] | 304.493 [303.377, 305.351] | snapshot |
| xxl | sparse | 47.120 [45.121, 50.914] | 0.070 [0.062, 0.190] | delta |
| xxl | dense | 47.034 [45.475, 48.479] | 242.604 [235.929, 250.601] | snapshot |
| xxl | hot | 46.707 [45.428, 48.545] | 413.226 [406.160, 432.389] | snapshot |

Each host ran 36 measured processes (six balanced pairs per workload) and six
calibration processes. Reported ranges span process means, not request latency
percentiles. Every pair supports the named winner by more than 5%. The x86
sparse delta range is wider; the winner is unchanged across all pairs. This
rule is not a confidence interval, and no architecture-wide winner is claimed.

Each case has 65,536 slots. Sparse has 64 scattered changes; dense has 65,536
changes touching every slot; hot has 262,144 changes touching 64 slots.
Each method alternates between two prebuilt states. Snapshot size is 1,048,576
in-memory bytes. Delta sizes are 1,536, 1,572,864 and 6,291,456 bytes.
These are representation sizes, not wire traffic. The illustrative lesson's
64-byte encoded records use a different declared assumption.

Timing covers cache validation and application with warm data. It excludes
input construction, allocation, authority writes, encoding, transport, fanout,
and concurrent readers. Snapshot and delta paths expose the same complete
final state; no application observes intermediate updates. Coalescing is a
useful alternative for the hot case but was not measured.

Both hosts passed five unit tests, one doctest, Clippy, and benchmark state
checks on this source. The exhaustive oracle checks every prefix of 4,096
six-operation put/delete histories. All six full Systems workspace validation
commands passed locally. Only the runner compatibility fix followed those Rust
checks; final hosts exercised the committed compatible runner.

The first remote setup failed because Python 3.9 lacks zip(strict=True).
A committed explicit length check fixed the runner before final measurements.
One local exploratory run overlapped workspace validation and is excluded.
No required Topic 077 Linux measurement remains missing.
