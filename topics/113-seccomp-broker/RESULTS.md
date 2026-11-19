# Results, November 19, 2026

Tested source commit `14ff16399d7198065bc81fbbab728528fac1407a`.
Both hosts received the same Git archive, SHA-256
`81456103f9f1221bbac773c15abbf94514771f152f4fbcb4e4b90aa7da9a7bc4`.

| Host | Portable Rust and Python | Native Linux broker |
|---|---|---|
| macOS arm64, Darwin 25.6.0 | Passed | Linux interface |
| Amazon Linux AArch64, kernel 6.12.115 | Passed | Two denials, verified grant, completed ID rejected |
| Amazon Linux x86-64 (xxl), kernel 6.12.115 | Passed | Two denials, verified grant, completed ID rejected |

The Rust test checks all 2,048 single-position assignments, eight short copies
and one overlong input. The doctest mutates the original array after selection.
The child independently checks the delivered device and inode, contents,
read-only access and FD_CLOEXEC against fixture facts. The final ADDFD checks
ENOENT on an already completed request. Each Linux host ran the native sequence
once with GCC 11.5 and the flags in the lesson. Rust used 1.93.1 on all hosts.

Workspace format, Clippy, tests (579), doctests (171), benchmark compilation
and documentation passed on macOS. Raw topic output is in `evidence/`.

These are correctness checks for a cooperative child, a bounded eight-byte name
and a preopened read-only file. The stale-ID check covers a completed request.
Signal interruption during a pending request, allocation failure, arbitrary
concurrent schedules, other ABIs and latency remain outside the measured scope.
