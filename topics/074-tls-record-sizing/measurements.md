# Frozen experiment contract

Three candidates: OpenSSL local maximum send fragment 1024/4096/16384. Six
workloads: 128-byte, 1024-byte, 16384-byte, and 1048576-byte single writes;
16384 bytes as 128-byte writes; 1048576 bytes as 4096-byte writes. No delay
between writes. Application boundaries and cipher are held fixed within a cell.

Six blocks use all six permutations of candidate order. Workload order rotates
one position per block. Each candidate/cell/block is a fresh process, for 108
independent process observations. Eight response warmups precede timing; repeats
are max(8,4194304/response_bytes). Repeats are not independent samples.

Timing includes SSL_write_ex, memory-BIO transfer/copies, SSL_read_ex, byte-count
checks, and any internal library allocation. It excludes caller-buffer allocation,
key/certificate creation, handshake, initial framing/full-byte oracle, process
startup, and final teardown. Setup and teardown are separately recorded. The
setup timer includes fixture generation and handshake; it is not network setup
latency. No CPU-counter mechanism attribution is made.

Every process checks exact plaintext, parsed record lengths, independent count
and byte formulas, corrupted-tag rejection, and partial-record withholding.
Candidates failing correctness are rejected before selection. Four Rust tests
cover independent iterative fragmentation, limits/padding, flushes, and overflow;
one doctest demonstrates the public contract.

Winner: every paired rival/candidate time ratio must be >=1.05 in all six blocks
against both rivals. Otherwise unresolved, not statistical equivalence. Report
median and min/max process averages. The rule is conservative and is not a
confidence interval. No reruns to seek a winner.

The initial and committed-source campaigns are kept separate. Local host: Apple
M1 Pro, 10 logical CPUs, Darwin 25.6.0, uncontrolled scheduling; OpenSSL 3.6.2;
Apple clang, exact version and compile command in the receipt. C flags are
-std=c11 -O3 -Wall -Wextra -Werror, with pkg-config-selected headers/libraries;
no explicit target CPU/features. OpenSSL runtime crypto dispatch is not separately
identified. Rust budgeting checks use rustc 1.93.1 / LLVM 21.1.8.

Required Linux Arm and runtime-resolved xxl runs are pending after WSSH rejected
expired Midway authentication before identity/transfer. No claim about either
Linux host, remote TTFB, packet loss, cold caches, concurrency, kernel TLS,
production throughput, or universal optimal cap is supported by this fixture.
