# Correctness results

Tested source: `18626862119acbade4bc1be1748f1d28eed46aaf`.
Archive SHA-256: `29269b2c7477a4270f7150c4dc56c76515522814a4ed0ffdc5b3c8852ac92963`.
Both Linux transfer hashes match. The retained runs executed this commit's bytes.
Later commits are described at the end.

| Host | Model histories | Identity comparisons | Unit/doc | Native cases |
|---|---:|---:|---|---:|
| macOS arm64, Darwin 25.6.0 | 65,536 | 819,328 | 3/1 pass | Linux required |
| dev-dsk-ahrav-2b-7dc7bd93, Linux AArch64 | 65,536 | 819,328 | 3/1 pass | 256 pass |
| xxl, resolved dev-dsk-ahrav-2c-32182091, Linux x86-64 | 65,536 | 819,328 | 3/1 pass | 256 pass |

All three use Rust 1.93.1. Both Linux hosts use kernel 6.12.113-138.209.amzn2023
and GCC 11.5.0. Native flags: `-std=c11 -O2 -Wall -Wextra -Werror`.
Rust oracle uses the release profile. The portable Python reproduction passes
on all three hosts. The local final run used the extracted committed archive.

Each model run detects 97,536 raw-descriptor misroutes and zero guarded misroutes.
Each Linux run captures 256 pre-close readiness events, rejects every stale token,
reads B through the deliberately faulty raw callback, and reads C via fresh
dispatch. The 64 alias-without-DEL cases retain the old registration after close.
The logs report them as `alias_cases=64`; 128 runs hold an alias. Each run
observes 576 readiness events: 256 before close, 64 retained, and 256 after reuse.
This expectation is checked against kernel return values and distinct pipe bytes.

These counts describe correctness coverage. The native program executes 256
scenarios inside one process per host, using 64 repetitions of four schedules.
Timing, throughput, statistical variability, arbitrary concurrent schedules,
signal interruption, forked aliases, network sockets, and reclamation costs are
unmeasured. The generation model assumes one owner through validation and I/O.
No performance winner is claimed.

Per-host run logs and the source identity record are committed in `results/`.
The complete standalone lesson, inspected visual, and source archive are
retained with the daily automation output. Workspace validation is recorded in
the PR and the retained validation summary.

Commits after the tested commit change validation code and documentation.
`native/epoll_reuse.c` gains a guard after `main` that refuses a `-DNDEBUG`
build. `examples/reuse.py` exits under optimized Python. `test_checks.py` checks
both refusals. `src/lib.rs` gains one unit test and a rustdoc clarification. The
tested source ran three unit tests on each host; the head runs four.
`examples/oracle.rs` is byte-identical to the tested commit, and `Registry`
changes in rustdoc only.

Linux AArch64 host dev-dsk-ahrav-2b-a030d1dc built both revisions with kernel
6.12.113-138.209.amzn2023, GCC 11.5.0, Rust 1.93.1 and the flags above. The
native binary and the release oracle binary are byte-identical between the
tested commit and the head. The retained logs record no Python version. On this
host, with Python 3.9.25, the edited `reuse.py` passes and `test_checks.py`
passes three tests, including the 256 native cases. The table rows describe the
tested commit.
