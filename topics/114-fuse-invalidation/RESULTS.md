# Mounted results

Linux returned new metadata with stale page contents in all six trials.
Full inode invalidation made both answers agree with the independently
opened backing descriptor.

| Held descriptor after external write | Linux AArch64, 3 mounts | Linux x86-64, 3 mounts |
|---|---|---|
| Before notification | 0400 BLUE, 3/3 | 0400 BLUE, 3/3 |
| Attributes only | 0400 BLUE, 3/3 | 0400 BLUE, 3/3 |
| Attributes and pages | 0400 GOLD, 3/3 | 0400 GOLD, 3/3 |
| Direct backing-file oracle throughout these reads | 0400 GOLD | 0400 GOLD |

Each trial started a new daemon and mount, warmed one descriptor at 0444
BLUE, then updated the same backing inode outside FUSE. The driver checked
the result of each notification before the next observation. An initial test
required 0444 before notification. Both kernels returned 0400. The corrected
control allows either mode and checks that the warm page still contains BLUE.

Tested commit `f3d1a4a8c503dd37b055d1166717b61b9574c1d5`.
Both hosts verified the transferred source archive against SHA-256
`f30939db428a31ccfd078b565a06990137ab61c0f5cbcc73875af6004deac8f9`.
Linux 6.12.115, libfuse 3.10.4, GCC 11.5.0 with
`-std=gnu11 -O2 -Wall -Wextra -Werror -pthread`, and Rust 1.93.1.
The hosts provided the shared library and mount helper. The build used
headers from the matching [upstream release](https://github.com/libfuse/libfuse/tree/fuse-3.10.4/include).
Each host also passed the model unit test and doctest.
[Arm log](evidence/arm.log) and [x86 log](evidence/x86.log).

These are correctness observations for one clean page, one open reader and
an ordered update. The experiment does not exercise rename, dirty writeback,
concurrent refills, multiple mounts sharing a backing store, or lost events.
Latency and throughput were outside the experiment.
