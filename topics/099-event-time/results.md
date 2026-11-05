# Topic 099 results

Tested source: `a0801586606a7496497e7a64dee72bf73c283601`.
Archive SHA256: `ca0d9e4c0938112c814441757ff2f03409a78ee4eb8aebbc5225b1e55342850e`.
Archive members were compared byte-for-byte to Git; both Linux transfer hashes matched.
The later publication commit adds documentation and results; tested Rust/oracle bytes are unchanged.

| Host | Correctness | Output digest |
|---|---|---|
| macOS arm64 (Darwin 25.6) | 3,180 schedules; 61,980 state comparisons | `4465552cca441a1d9ff9f86f3d875c9988e82144b518514e9379aa42b643114c` |
| dev-dsk-ahrav-2b-7dc7bd93, Linux aarch64 | 3,180 schedules; 61,980 state comparisons | same |
| xxl, Linux x86_64, Xeon Platinum 8488C | 3,180 schedules; 61,980 state comparisons | same |

Each host passed two unit tests and one doctest. Rust 1.93.1 on all hosts.
Linux kernel 6.12.113, Python 3.9.25. Host metadata and full command output are in results/.
The original finite schedules and random seed 9905 are reproducible in experiment/check.py.
Input SHA256: `166419ea3a930df896b343a0c5826d6981ead259d5808fa18d0358cd7732c7a9`.
Expected final demo row: `15 1 2 - 0:15`.

All six repository checks passed: fmt, Clippy with warnings denied, 542 unit/example/bin
tests, 156 doctests, benchmark compilation, and rustdoc with warnings denied.
The branch starts from current origin/main b2ca372, which includes through Topic 097.
Topic 098's independent PR is outside this branch. Reviews and merges do not gate this lesson.

This is correctness evidence for a serialized custom model. Production throughput, memory,
checkpoint recovery, duplicate delivery and watermark accuracy remain unmeasured.
There is no timing campaign or performance winner claim. Finite test coverage is not a proof
for arbitrary schedules. The sink retains emitted outputs; the operator cleans live state.

Initial local Cargo invocation used the workspace parent and found no Cargo.toml;
validation was rerun from the registered repository worktree. No result from that failed
invocation is counted. Hooks remained active throughout publication.
