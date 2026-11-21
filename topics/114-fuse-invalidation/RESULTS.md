# Mounted results

The attribute-only notification replaced the cached mode and left the cached
page in place in all six trials. Full inode invalidation made both answers
agree with the independently opened backing descriptor.

| Held descriptor after external write | Linux AArch64, 3 mounts | Linux x86-64, 3 mounts |
|---|---|---|
| Before notification | 0444 BLUE, 3/3 | 0444 BLUE, 3/3 |
| Attributes only | 0400 BLUE, 3/3 | 0400 BLUE, 3/3 |
| Attributes and pages | 0400 GOLD, 3/3 | 0400 GOLD, 3/3 |
| Direct backing-file oracle before each read above | 0400 GOLD | 0400 GOLD |

Each trial started a new daemon and read-only mount, warmed one descriptor
at 0444 BLUE, then updated the same backing inode outside FUSE. The driver
checked the result of each notification before the next observation.

An earlier run at `f3d1a4a` mounted read-write and returned 0400 BLUE before
any notification, 3/3 on each host. The warm-up `FUSE_READ` marked atime
stale on the writable mount, so the next fstat fetched attributes inside the
timeout and the attribute-only step started from 0400. On the read-only
mount 0444 stays cached until the notification.

Tested commit `022773a72ad419b089f887834b5c7ce6d68b1922`.
Both hosts verified the transferred source archive against SHA-256
`d4969e7f8d9ee1659debe9a839725d5477aac4271f74a599283e6fa060cdd3f4`.
The AArch64 host has Arm Neoverse V1 cores (CPU part 0xd40). The x86-64 host
has an Intel Xeon Platinum 8488C. Both ran Linux 6.12.115, libfuse 3.10.4,
GCC 11.5.0, Python 3.9.25 and Rust 1.93.1.

The hosts provide the libfuse shared library and mount helper without the
development package, so the `pkg-config` command in the lesson did not run
there. The build used headers from upstream tag
[`fuse-3.10.4`](https://github.com/libfuse/libfuse/tree/fuse-3.10.4/include),
commit `c56ba920474d972483926ec40022d9640b31779f`:

```sh
cc -std=gnu11 -O2 -Wall -Wextra -Werror -pthread palette.c -I<headers> /usr/lib64/libfuse3.so.3 -o palette
```

Each host also passed the model unit test and doctest, and the driver refused
to start under `PYTHONOPTIMIZE=1`. The six workspace checks in
`DOCUMENTATION.md` passed on the AArch64 host with 584 unit, binary and
example tests and 172 doctests.
[Arm log](evidence/arm.log) and [x86 log](evidence/x86.log).

These are correctness observations for one clean page, one open reader and
an ordered update. The experiment does not exercise rename, dirty writeback,
concurrent refills, multiple mounts sharing a backing store, or lost events.
Latency and throughput were outside the experiment.
