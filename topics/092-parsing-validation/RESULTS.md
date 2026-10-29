# Topic 092 results

Source commit: `6d099b74eb8efba6ea294da7f23a97e6d8e50f77`.

All three machines executed the same committed source and runner archive.
Archive SHA-256: `eb7cf4daa86de73e77484c387f681df68e430c691285135935cec61ec80126c9`.

Each machine passed four unit tests, one doctest, 136335 independent parser comparisons
across 45445 inputs, and exact output checks for all seven measured workloads.
Each completed 126 measured fresh processes and 21 excluded warmup processes.

## Measured valid batches

Entries are GB/s from median batch time [minimum, maximum throughput] across six processes. GB is decimal.
Each sample validates and produces every value. Throughput includes output and index writes.

| Host | Workload | Fused | Split | Indexed | Pairwise decision |
|---|---|---:|---:|---:|---|
| local | tiny | 2.108 [1.840, 2.296] | 0.826 [0.781, 0.934] | 1.204 [1.172, 1.235] | fused/split: fused; fused/indexed: fused; split/indexed: indexed |
| local | short | 2.818 [2.735, 2.860] | 0.710 [0.661, 0.723] | 0.873 [0.830, 0.895] | fused/split: fused; fused/indexed: fused; split/indexed: indexed |
| local | long | 1.700 [1.553, 1.884] | 1.235 [1.135, 1.304] | 1.284 [1.202, 1.362] | fused/split: fused; fused/indexed: fused; split/indexed: unresolved |
| local | mixed | 1.163 [0.997, 1.242] | 0.652 [0.632, 0.686] | 0.513 [0.494, 0.531] | fused/split: fused; fused/indexed: fused; split/indexed: split |
| local | large | 1.612 [1.562, 1.625] | 1.134 [1.089, 1.177] | 0.992 [0.972, 1.017] | fused/split: fused; fused/indexed: fused; split/indexed: split |
| arm | tiny | 0.856 [0.681, 0.879] | 0.477 [0.465, 0.481] | 0.558 [0.541, 0.562] | fused/split: fused; fused/indexed: fused; split/indexed: indexed |
| arm | short | 1.200 [1.163, 1.221] | 0.421 [0.388, 0.426] | 0.520 [0.501, 0.526] | fused/split: fused; fused/indexed: fused; split/indexed: indexed |
| arm | long | 0.781 [0.724, 0.786] | 0.547 [0.490, 0.550] | 0.579 [0.530, 0.586] | fused/split: fused; fused/indexed: fused; split/indexed: unresolved |
| arm | mixed | 0.449 [0.444, 0.456] | 0.355 [0.352, 0.357] | 0.266 [0.264, 0.269] | fused/split: fused; fused/indexed: fused; split/indexed: split |
| arm | large | 0.672 [0.667, 0.677] | 0.501 [0.500, 0.502] | 0.493 [0.490, 0.498] | fused/split: fused; fused/indexed: fused; split/indexed: tie |
| x86 | tiny | 0.973 [0.954, 0.996] | 0.450 [0.445, 0.462] | 0.496 [0.486, 0.498] | fused/split: fused; fused/indexed: fused; split/indexed: indexed |
| x86 | short | 1.483 [1.432, 1.574] | 0.344 [0.331, 0.358] | 0.448 [0.447, 0.453] | fused/split: fused; fused/indexed: fused; split/indexed: indexed |
| x86 | long | 0.853 [0.807, 0.860] | 0.594 [0.591, 0.618] | 0.437 [0.361, 0.439] | fused/split: fused; fused/indexed: fused; split/indexed: split |
| x86 | mixed | 0.392 [0.389, 0.396] | 0.310 [0.309, 0.313] | 0.210 [0.209, 0.212] | fused/split: fused; fused/indexed: fused; split/indexed: split |
| x86 | large | 0.728 [0.628, 0.731] | 0.527 [0.524, 0.531] | 0.371 [0.365, 0.381] | fused/split: fused; fused/indexed: fused; split/indexed: split |

## Malformed batches

Entries are median microseconds per rejected batch [minimum, maximum].
The complete input length is not a processed-byte count for an early exit.

| Host | Error position | Fused | Split | Indexed |
|---|---|---:|---:|---:|
| local | invalid_early | 0.001 [0.001, 0.001] | 2.993 [2.969, 3.150] | 126.482 [125.187, 133.977] |
| local | invalid_late | 153.151 [137.592, 161.794] | 295.844 [286.786, 304.590] | 365.143 [358.755, 387.303] |
| arm | invalid_early | 0.004 [0.004, 0.005] | 7.706 [7.700, 7.711] | 271.014 [267.510, 275.410] |
| arm | invalid_late | 426.109 [423.783, 433.806] | 543.766 [539.796, 547.303] | 718.910 [711.671, 754.078] |
| x86 | invalid_early | 0.003 [0.003, 0.003] | 5.269 [5.260, 5.329] | 381.871 [379.933, 383.310] |
| x86 | invalid_late | 488.550 [484.505, 492.119] | 618.553 [616.253, 621.660] | 916.190 [911.551, 920.949] |

## Controls and interpretation

A pair wins when all six paired process times show more than a 5% advantage.
All six ratios within [1/1.05, 1.05] produce a practical tie. Other pairs remain
unresolved. The rule is descriptive; these are not confidence intervals.

All builds use Rust 1.93.1, default release optimization and target CPU, without
RUSTFLAGS. Each fresh process performs four internal warmup parses. Buffers and
input are reused. File I/O, initial capacity allocation, checksums and oracle
comparisons are excluded from timing. Linux inherits affinity to CPU0; macOS
uses OS scheduling. CPU frequency, thermals, load and SMT siblings are uncontrolled.

The indexed implementation performs a full delimiter scan even when the first
field is malformed. The split implementation validates UTF-8 across the buffer
before parsing fields. These source-level facts explain the extra work on early
errors; hardware-counter attribution was not measured.

These comparisons cover this restricted ASCII protocol and these three paths.
JSON libraries, explicit SIMD, streaming, parallel parsing, cold allocation,
I/O and production tail latency remain unmeasured.

## Machine identities

- local: c0c7db201688, arm64, CPU model unavailable: sysctl permission denied; affinity OS scheduled.
- arm: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, aarch64, See metadata.json; affinity [0].
- x86: dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com, x86_64, Intel(R) Xeon(R) Platinum 8488C; affinity [0].

Raw samples, workload hashes, compiler identities and binary hashes are in
`measurements/<host>/`. Local validation logs and original SSH transcripts are
retained with the standalone lesson outputs. The published source files and
runner must match the measured commit byte-for-byte.

## Repository validation

All six workspace gates passed: formatting, Clippy, 526 tests, 150 doctests,
benchmark compilation and documentation. The first test run hit unchanged
Topic015 `pair.second_ns > 0`; the targeted retry and full-suite retry passed.
The original failure log is retained. Writing and branch whitespace checks pass.
