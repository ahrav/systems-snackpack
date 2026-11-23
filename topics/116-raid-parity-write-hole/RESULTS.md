# Recovery results

All three hosts returned `cf` when stale parity rebuilt the untouched byte and `55` after journal replay. Each host passed the same deterministic inputs from commit `63314bbaedd8a60da320161d15d2b26591cb37e5`. The source archive SHA-256 was `f644d767e05c88005edbd82995edc5035c27979fa78bc47686a47eed33fea94b`.

| Host | Environment | Stripe comparisons | File histories |
|---|---|---:|---:|
| Local | Apple M5 Pro, Darwin 25.6.0 arm64, Python 3.13.16 | 294,912 | 84 |
| Linux ARM | AArch64, Linux 6.12.115, Python 3.9.25 | 294,912 | 84 |
| Linux x86 | Intel Xeon Platinum 8488C, Linux 6.12.115, Python 3.9.25 | 294,912 | 84 |

Each host used Rust 1.93.1 and passed two unit tests and one doctest. The Rust model used the Cargo debug profile. The independent Python oracle compared the old stripe, unprotected reconstruction, replayed stripe and post-retirement stripe for each of 73,728 histories. It tested both single-member updates and full-stripe writes, four byte values per input and every possible single missing member. The unprotected control produced 3,072 wrong untouched reconstructions and 15,360 full-stripe outcomes outside the old and intended versions. Counts include repeated schedules that differ only in the subsequent replay cut. They measure coverage. They do not estimate failure probability.

Each file experiment used three regular files in a fresh temporary directory, one writer and two recovery attempts. Protected runs checked every surviving and reconstructed byte against literal bytes held by the test driver. Two unprotected partial updates corrupted the untouched byte, one with data first and one with parity first. Exiting processes preserves the OS page cache. Physical power loss, Linux MD implementation behavior, torn sectors, a lying device cache, overlapping writes and journal-device failure were outside the experiment.

The I/O counts in the lesson follow from the two-data-member geometry. Full stripes constructed from both supplied chunks need zero old reads, and single updates using the delta need two. These counts exclude journal metadata and caches. No device latency or throughput was measured.
