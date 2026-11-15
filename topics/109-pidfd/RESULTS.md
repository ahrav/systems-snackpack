# Results

Committed source f3645696b7f713cdd438410089056da723b184c5 was checked on 2026-11-15. Archive SHA256:
`7052e122616310401aed23ad3fbd6131e6163a8626a7067ce35a60b4cd39fe8c`.
Every archive file was compared byte-for-byte with its Git blob. Both remote
transfer hashes match. Publication changes after this commit contain results and source notes only.

| Host | Portable oracle | Rust tests | Native lifecycle |
|---|---|---|---|
| macOS arm64 |279,936 histories,1,918,044 comparisons|2 unit,1 doc|Linux required|
| Linux AArch64, ARM implementer |279,936 histories,1,918,044 comparisons|2 unit,1 doc|256 cases and Python example pass|
| Linux x86_64, Xeon Platinum 8488C |279,936 histories,1,918,044 comparisons|2 unit,1 doc|256 cases and Python example pass|

Each oracle observed 15,486 wrong-target selections in the raw-PID negative control.
Both Linux hosts ran 64 repetitions each of clone/signal, fork/signal, zombie/open,
and clone/exit. All four modes executed. Each validates child PID, termination
class and status, WNOWAIT retention, reaping and stale-pidfd ESRCH. There were
zero native skips. Rust 1.93.1, GCC 11.5.0, Python 3.9.25 and Linux 6.12.115 were used.
The C flags were `-std=c11 -O2 -Wall -Wextra -Werror`.

Raw logs and source hashes are in [measurements](measurements/).
The first C build failed because libc headers omitted P_PIDFD. Adding the kernel
UAPI wait header fixed compilation. Both hosts reran the corrected committed
source. Failed initial logs and the initial source archive are retained with the
standalone lesson. The Python example also resets inherited signal dispositions
and masks before creating its child.

These are correctness observations. The model's seven-action bound and two PID
slots are explicit. Native tests do not force PID reuse or enumerate arbitrary
concurrent schedules. Performance, resource exhaustion, permission changes,
process namespaces, child trees and thread-specific pidfds were not measured.

All six workspace validation commands passed: formatting, Clippy, 570 tests, 167 doctests, benchmark compilation, and documentation with warnings denied. The final oracle-only change repeated formatting, workspace Clippy, topic tests, doctest, oracle and benchmark compilation.
