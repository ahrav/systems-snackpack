# Validation results

Tested source: `557b84f34dc1914b661ab4b783a9a64eac81357f`.
Archive SHA256: `66d9985e0d3e2609e7acd9da7c4c8e047814b8340d6c4b194ba32052b3b44aa3`.
Both Linux hosts received that exact committed archive. Publication adds documentation
and retained results. `native.c` and the Rust source are byte-identical to the
tested commit.

| Host | Rust model | Native pthread cases | Portable Python |
|---|---|---|---|
| macOS arm64 | 3 unit tests and 1 doctest pass | Linux-only API | pass |
| dev-dsk-ahrav-2b-7dc7bd93, Linux aarch64 | 3 unit tests and 1 doctest pass | 384 pass | pass |
| xxl, Linux x86_64 | 3 unit tests and 1 doctest pass | 384 pass | pass |

The Rust model checks 30,906 initial-balance, amount and crash-point combinations,
with repeat recovery. Each native run checks 360 successful recoveries, 12 repair
refusals and 12 premature-consistency negative controls. The Python oracle computes
serial committed balances independently of the C undo path. Both host CSV files
have identical outputs. Return-code assertions execute inside the native program.

Linux kernel: 6.12.115. GCC: 11.5.0. Rust: 1.93.1. Native flags:
`-std=c11 -O2 -Wall -Wextra -Werror -pthread`. Each host ran one deterministic
384-case campaign. Process death uses `_exit` at controlled boundaries. Each parent
waits for the child before acquiring the mutex. Lock-free shared atomic integer
support is checked at runtime. No timing claim is made.

All six workspace gates pass: format, Clippy with warnings denied, library/binary/
example tests, doctests, benchmark compilation, and documentation with warnings denied.
Task-local Cargo cache isolates downloaded dependencies from the user cache.

Limitations: these are finite correctness checks. Arbitrary schedules, concurrent
waiter contention, SIGKILL injection, power loss, latency, throughput and arbitrary
memory corruption are unmeasured. The Rust model does not implement pthread ownership;
native tests supply that independent operating-system check. The poison oracle checks
record shape while the C program asserts `ENOTRECOVERABLE` directly.

Commits after the tested source change `oracle.py` and `protocol.py` and add
`test_checks.py`. Both scripts exit under optimized Python, which strips their
assertions. The oracle also requires the exact 384 scenario keys of the native
matrix. Its balance checks and the `protocol.py` recovery model are byte-identical
to the tested commit. `test_checks.py` checks these refusals, the two retained CSV
files and the portable example.

Linux x86_64 host dev-dsk-ahrav-2c-32182091, with kernel 6.12.115, GCC 11.5.0 and
Python 3.9.25, ran the head `protocol.py` and ran the head oracle on
`evidence/arm.csv`, on `evidence/x86.csv`, and on one fresh native run built with
the flags above. Each run prints the `PASS` line retained in the logs, and the
fresh CSV is byte-identical to `evidence/x86.csv`. The table, the logs under
`evidence/` and the archive hash record the tested-commit scripts on all three hosts.

Host metadata, the archive hash, this topic's Rust, Python and native output, and
the CSV rows accompany this lesson under `evidence/`. The `check` jobs of the CI
workflow run the six workspace gates on Linux and macOS for each pushed commit.
Commands and invariants are in [README.md](README.md).
