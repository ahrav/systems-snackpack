# Results: 2026-11-13

Exact tested source: `c4a883dd8c0a743f534564a9688e0f6b3c4b4729`. Full source archive SHA256:
`66f83f4bf179bbf62f3a3e9d0af8e88cb1bc774512b221806a958b385356e2ae`.
Both transferred archives have that hash. Final publication keeps the executable
source and test bytes unchanged from this commit.

| Check | Linux AArch64 | Linux x86-64 | macOS arm64 |
|---|---|---|---|
| 16 seal masks × 5 fresh-object operations | 80 pass | 80 pass | Linux required |
| Child retains writer after parent unmaps | pass | pass | Linux required |
| Published payloads, every byte checked twice | 6 sizes pass | 6 sizes pass | Linux required |
| Rust policy tests and doctest | 2 + 1 pass | 2 + 1 pass | 2 + 1 pass |

Linux hosts: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com and alias xxl,
which reports x86_64. Both run Amazon Linux kernel 6.12.113 and Python 3.9.25.
Rust is 1.93.1. Exact kernel build and host identifiers are in the logs.
The range test checks 51,200 small range combinations plus overflow boundaries.
Payload sizes: 1, 4095, 4096, 4097, 65536, and 1048576 bytes.

The native checks observe EPERM for restricted operations and EBUSY for WRITE
sealing while the child retains a shared writable mapping. The child changes
bytes after FUTURE_WRITE; sealing with WRITE succeeds after it unmaps. The
receiver sees identical expected bytes before and after attempted mutations.
Default creation without ALLOW_SEALING prevents adding WRITE. SEAL locks later
seal additions. Private writes leave backing bytes unchanged.

The operation oracle uses a declarative forbidden-seal table. Expected lengths
and bytes are constructed separately from syscall results. Cross-process data
uses recurrence generation and a closed-form receiver oracle. This checks the
experiment against real kernel behavior and compares complete bytes.

Correctness study only. Latency, throughput, RSS, arbitrary concurrent schedules,
SCM_RIGHTS transfer, DMA, persistence and other kernels are unmeasured. There are
no performance winners or ties to report. The publication handoff uses fork.
The local native checker reports SKIP; its initial platform-constant import error
was fixed before the committed-source Linux runs.

## Repository validation

All six workspace gates pass: formatting, Clippy with warnings denied, library/
binary/example tests, doctests, benchmark compilation, and rustdoc with warnings
denied. Tests total 564 ordinary tests and 165 doctests across the workspace.

The related skill change is draft PR422. Its model evaluation and calibration
are separate from this lesson's native correctness checks.
