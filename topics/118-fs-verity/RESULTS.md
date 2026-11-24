# Verification cost for a 64 MiB index

On all three hosts the tree won each of 12 paired trials for sparse reads. The whole-file digest won each pair for a complete scan. Both methods consumed the first four bytes of each requested block and checked the same resulting sum. The whole-file reader verified the immutable byte string once per session. The tree reader verified each requested data block and cached authenticated hash blocks for that session.

| Host | Workload | Tree median / P90 (ms) | Whole-file median / P90 (ms) | Tree wins |
|---|---|---:|---:|---:|
| mac | sparse | 0.045 / 0.054 | 21.408 / 22.848 | 12/12 |
| mac | scan | 37.157 / 38.331 | 24.703 / 25.766 | 0/12 |
| arm | sparse | 0.068 / 0.069 | 40.442 / 40.464 | 12/12 |
| arm | scan | 97.676 / 98.156 | 45.689 / 46.439 | 0/12 |
| x86 | sparse | 0.070 / 0.075 | 43.179 / 43.219 | 12/12 |
| x86 | scan | 87.765 / 88.255 | 46.530 / 46.593 | 0/12 |

Each workload and method ran in 12 fresh Python processes with alternating order in matched pairs. P90 is the 11th sorted observation. Sparse requests were blocks 129, 130 and 384. The scan requested all 16,384 blocks in order. Each process built the same file and both trusted identities before timing. The timed region includes reader setup, verification and consumption. Input bytes were resident. Proof caches started empty. The processes used default CPU scheduling on shared machines. Python interpreter work, including per-block calls, contributes to the timings.

The tree authenticated six blocks for the sparse workload, three data and three metadata. A complete traversal authenticated 16,384 data blocks and 129 metadata blocks. The whole-file reader hashed 64 MiB for either workload. These counts explain the change in winner. The experiment measures userspace verification time. It excludes disk, kernel readahead, signature verification, tree construction, and the cost of transporting the file.

- mac: Apple M5 Pro, Darwin 25.6.0 arm64, CPython 3.13.16.
- arm: 64-core AArch64 Linux 6.12.115, CPython 3.9.25.
- x86: Intel Xeon Platinum 8488C, Linux 6.12.115 x86-64, CPython 3.9.25.

## Correctness

Five independent fsverity-utils vectors cover 0, 1, 4,096, 100,000 and 1,000,000 bytes. The implementation produced every expected descriptor digest and verified every in-range block against the original input. A separate interval oracle checked all 391 reads for a fault in each of four leaf hash blocks and the top block, 1,955 decisions in total. Additional tests exercised changed data, replacement files, zero extension, partial blocks and invalid indices. Two Rust tests and a doctest cover proof geometry, including the largest representable file length.

The Linux probe compiled with GCC using `-std=gnu11 -Wall -Wextra -Werror`. Both hosts returned `ENOTTY` (25) from `FS_IOC_ENABLE_VERITY` on their XFS scratch mounts. Native kernel verification and storage-device latency remain unmeasured. The table uses committed implementation `eb0253853e293950ed96746e09a086a2de2f9f6b`. Raw samples and final-head replay results accompany the lesson.

[Independent reference vectors](https://github.com/ebiggers/fsverity-utils/blob/36660d79c9ddbc4d560d9a496b6b67c1c25dcd13/programs/test_compute_digest.c) · [Kernel filesystem support](https://docs.kernel.org/filesystems/fsverity.html#filesystem-support)
