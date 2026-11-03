# Measured join choice

The corrected cardinality selects the measured winner in all four workloads on
both Linux hosts. The independent estimate chooses nested for the correlated
case, producing 1.33x median regret on Arm and 1.46x on x86.

Source commit: `8e75f0c0832e77bf6b377434da026f07341b9578`.
Archive SHA256: `37c3713966d52979e43657e51e3fefcc78f678c31716ce912c3c065305308eaa`.
Both hosts verified the transferred archive hash before extracting it.
Final result/documentation additions preserve all measured source and harness bytes.

## Controls and correctness

Rust 1.93.1, Cargo release profile, default target CPU, no custom RUSTFLAGS.
Linux kernel 6.12.113-138.209.amzn2023, Python 3.9.25, CPU0 affinity.
x86 host: Intel Xeon Platinum 8488C through SSH alias xxl.
Arm CPU implementer 0x41, part 0xd40.
Arm host: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, AArch64.
Two unit tests and one doctest passed on each host. Each host passed 4,200
comparisons against SQLite across 2,100 input pairs, including exhaustive
small sequences, empty inputs, duplicates and seeded extreme-key cases.

Each host ran 64 measured fresh processes and eight excluded warmup processes.
Eight alternating AB/BA pairs per workload. Each process includes an untimed
warm call. Repetitions: 1000 independent, 100 correlated, 100000 exclusive,
10 dense. Hash table build/allocation/drop are timed every iteration.
The filter and statistics calculations occur outside the timed join.

Load, thermals, clocks, SMT and VM placement remain uncontrolled. These are
warm in-memory count results, with fixed workload order. Hash seeds vary by
call. They establish neither PostgreSQL plan speed nor disk/spill behavior.
The empty-input case measures the fast-return and harness overhead; its
absolute saving is only a few nanoseconds. A materializing join has additional
output costs. The factor10 cost model was fixed before measurement and is
illustrative. Exact joint counts are an information bound, not free statistics.

## Timings

All values below are microseconds per complete join call: median [min, max].
A winner exceeds the other algorithm by 5% in every matched pair.
The full JSON files retain raw samples, excluded warmups and paired ratios.

| Host | Workload | Nested | Hash | Winner | Independent-plan regret |
|---|---|---:|---:|---|---:|
| arm | independent | 0.8294 [0.8236, 0.8455] | 71.5067 [71.4448, 71.5696] | nested | 1.00x |
| arm | correlated | 96.3208 [95.9776, 97.5389] | 72.3680 [72.1798, 72.5551] | hash | 1.33x |
| arm | exclusive | 0.0012 [0.0012, 0.0012] | 0.0029 [0.0027, 0.0034] | nested | 1.00x |
| arm | dense | 4794.8975 [4787.8396, 4799.2341] | 111.1735 [110.3474, 112.6276] | hash | 1.00x |
| x86 | independent | 0.8842 [0.8830, 1.1776] | 56.4555 [55.9116, 83.6772] | nested | 1.00x |
| x86 | correlated | 94.5392 [88.5288, 121.6717] | 64.6712 [56.7188, 75.3828] | hash | 1.46x |
| x86 | exclusive | 0.0018 [0.0016, 0.0021] | 0.0031 [0.0025, 0.0033] | nested | 1.00x |
| x86 | dense | 4757.2808 [4485.3231, 5436.2318] | 107.4640 [94.1047, 137.7174] | hash | 1.00x |

Joint-plan median regret is 1.00x for every cell. Regret is relative only to
the two tested alternatives. No ties or unresolved cells occurred.

The Python estimate script produced exactly the three expected lines.
The optional PostgreSQL SQL script was retained but not executed: local
psql is unavailable. PostgreSQL estimate correction remains a source-backed
example; the SQL oracle above used SQLite.

## Repository validation

All six workspace checks passed: formatting, Clippy with warnings denied,
540 unit/example/binary tests, 155 doctests, benchmark compilation and
rustdoc with warnings denied. Full-branch whitespace and prose checks passed.
Local correctness also passed 4,200 independent SQL-oracle comparisons.
Local timing was omitted during workspace validation.
