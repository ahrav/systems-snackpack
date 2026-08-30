# Cross-host measurement boundary

Binary prefixes are used below: KiB means kibibytes and MiB means mebibytes.
A/A means the same sequential buffered treatment run under two labels.

Both accepted campaigns used source commit
`fa2dbeab31589618b8710096dd7b6f5a8e1fff89`, source-archive SHA-256
`05d940c7f05dbb40bb4a039ad7d87d1897068c0379712a28355553b56de244d0`,
the same 16 MiB file shape, and the same fixed schedules. Each
host compiled a native binary with GNU Compiler Collection (GCC) 11.5.0 and
`-O3 -g -std=c11 -Wall -Wextra -Werror -march=native`.

Each scan used 4 KiB reads.

| Exact-host result | Required Arm host | Runtime-resolved `xxl` host |
|---|---:|---:|
| Median sequential buffered scan | 48.464361 ms | 48.505881 ms |
| Median randomized buffered scan | 2,342.362265 ms | 2,343.360340 ms |
| Randomized / sequential ratio | 47.975044 | 48.435894 |
| 95% between-block interval | [47.538366, 48.415734] | [47.604306, 49.282010] |
| A/A Y/X ratio | 0.999580 | 0.996291 |
| A/A 95% interval | [0.986196, 1.013145] | [0.989118, 1.003517] |
| Median sequential direct scan | 2,339.839913 ms | 2,338.591319 ms |
| Direct / buffered ratio | 47.688376 | 48.168147 |
| Direct 95% interval | [46.419597, 48.991834] | [46.907396, 49.462783] |

Each primary and A/A estimate uses eight complete four-process blocks. Each
direct estimate uses four. A fresh process receives each treatment. A 4 KiB
`pread` inside the process is a subsample, not an independent replication. All
80 process identifiers per host were distinct. No attempt failed, stopped
early, or was replaced.

Both hosts showed the same one-read control: sequential advice produced 12
resident pages and 49,152 physical read bytes after one requested 4 KiB read;
random advice produced one resident page and 4,096 physical read bytes. Both
hosts also retained all 1,024 pages of the 4 MiB write control after
`fdatasync`, then reported zero after `POSIX_FADV_DONTNEED`.

Startup remained separate from each measured scan. Primary startup medians
ranged from 0.507 to 1.684 ms, while randomized scans took about 2,343 ms.
Startup therefore does not account for the measured treatment ratios in these
run windows.

The direct controls used `O_DIRECT`, reported `STATX_DIOALIGN`, used 8-byte
pointer-safe allocation alignment against reported 4-byte memory and 512-byte
offset requirements, verified each block's first and last eight-byte identity
sentinels, and charged 16 MiB of physical read bytes per process. Every
accepted direct process happened to finish with
zero resident pages. Post-direct residency remains telemetry, not a validity
promise.

## What the comparison supports

Measured: these two exact XFS and Amazon Elastic Block Store paths made a
serialized, sequential, buffered 4 KiB scan roughly 48 times faster than both
the randomized buffered treatment and the sequential direct treatment. The
same-source A/A intervals included one. The linked binaries retained the
identity-sentinel verifier. Their linked disassemblies contained the required
libc calls.

Inferred: buffered sequential read-ahead and request locality probably let the
kernel and device handle larger or more concurrent work than the explicit
4 KiB loop exposes. The experiment did not collect block request traces or
device service intervals. It also changes order and advisory policy together
in the primary treatment. Those limits prevent a unique causal attribution.

In this run, the sequential direct treatment was slower than the sequential
buffered treatment. The loop issued one blocking 4 KiB request at a time, and
only the buffered treatment received `POSIX_FADV_SEQUENTIAL`. Those facts are
consistent with buffered read-ahead helping this workload, but the experiment
did not isolate their individual effects. Direct I/O remains valuable when an
application owns caching, scheduling, or memory use. This experiment measures
none of those broader benefits.

Similar values on the two hosts do not establish an Arm-versus-x86 result or a
general Amazon Elastic Block Store constant. The intervals cover process-block
variation inside one host, binary, filesystem, device path, and run window.
They do not cover machine, kernel, processor-family, cloud-host, or device
populations.
