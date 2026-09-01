# Focused Linux experiment

This experiment asks one narrow question: what changes when one userspace
thread raises its maximum outstanding direct reads from one to eight?

The probe uses raw Linux asynchronous input/output (AIO) through `io_setup`,
`io_submit`, and `io_getevents`. It opens one regular file with `O_DIRECT`,
which asks Linux to minimize page-cache effects. It never writes a block
device. It never uses `sudo`, `drop_caches`, `fio`, `perf`, a memory-backed
filesystem, or a sysfs write.

The result covers the full observed file-read path. That path includes the
filesystem, the Linux multi-queue block layer (`blk-mq`), the device driver,
and any virtual or physical storage behind the guest. The result does not
isolate media service time.

## Workload and correctness checks

[`nvme_aio_depth_probe.c`](nvme_aio_depth_probe.c) creates a private 128
mebibyte (MiB) regular file. Every 64-bit word contains a deterministic,
nonzero value. `init` uses `O_CREAT | O_EXCL`, writes every block, and calls
`fdatasync`. `verify` reads and checks every word before timing begins.

Each timed process:

- runs one userspace thread;
- reads a unique deterministic sequence of 4 kibibyte (KiB) blocks;
- checks the first, middle, and last word of every completed read;
- records its thread count, process identifier, startup time, setup time,
  elapsed time, voluntary and involuntary context switches, and
  `/proc/self/io` storage-read bytes;
- queries `statx` with `STATX_DIOALIGN` and rejects an incompatible direct-I/O
  alignment;
- exits with status 77 when Linux AIO, `O_DIRECT`, or alignment support is
  absent. The harness treats that result as a failed publication receipt.

The same seed drives all four processes in one block. Queue depth is the only
workload change in the depth comparison. The depth-eight process records
`peak_outstanding=8`. That field proves only the userspace AIO submission
window. It does not prove eight requests occupied one `blk-mq` hardware
context or one Non-Volatile Memory Express (NVMe) submission queue.

## Fixed process design

[`run_processes.py`](run_processes.py) retains two fixed campaigns. Each letter
starts a fresh native process.

| Campaign | Eight four-process blocks | Compared ratio |
|---|---|---|
| `depth` | `ABBA BAAB ABBA BAAB BAAB ABBA BAAB ABBA` | q8 IOPS / q1 IOPS |
| `aa` | `XYYX YXXY XYYX YXXY YXXY XYYX YXXY XYYX` | q1 label Y IOPS / q1 label X IOPS |

One complete four-process block is the analysis unit. The 8,192 reads inside a
default process are workload, not 8,192 independent samples. Each campaign
contains 32 processes and 8 block contrasts. The full receipt contains 64
timed processes per host.

The runner journals each plan before launch. It stops after the first invalid
attempt and never replaces a failed process. A failed campaign requires a new
complete campaign in a new receipt.

[`analyze.py`](analyze.py) computes each order-cancelled block ratio on the log
scale. It reports the geometric mean, dispersion across the eight block
contrasts, and a two-sided 95% interval with 7 degrees of freedom. The interval
covers between-block variation in this host, binary, file, device stack, and
run window. It excludes variation across hosts, kernels, builds, storage
states, and storage products.

The identical-artifact A/A control passes only when all three checks hold:

- the point ratio is within `[0.95, 1.05]`;
- the 95% interval contains `1.0`;
- the full interval stays within `[0.90, 1.10]`.

These checks catch large label or schedule asymmetry. They do not define a
universal noise floor or prove that smaller bias is absent.

## Per-process storage evidence

The runner takes read-only snapshots immediately before and after every fresh
process. Each snapshot records:

- `/proc/diskstats` and selected `/proc/vmstat` counters;
- Pressure Stall Information (PSI) from `/proc/pressure/io`;
- effective control-group `io.stat` and `io.pressure` data;
- every mapped block-stack device's `stat` and `inflight` fields;
- wall-clock and monotonic timestamps.

The analyzer derives these device-wide values when the required fields exist:

```text
completed reads        = delta stat field 1
sectors read           = delta stat field 3
read milliseconds      = delta stat field 4
busy milliseconds      = delta stat field 10
weighted milliseconds  = delta stat field 11
average observed work  = weighted milliseconds / process elapsed milliseconds
mean block read time   = read milliseconds / completed reads
```

Linux reports sectors in 512-byte units in this interface. Device counters are
system-wide. Ambient traffic can change them. Counters from adjacent stacked
devices are not additive. Mean block read time includes queueing and block-layer
completion work. It is not pure controller or media latency.

## Exact-source host run

Run from a pushed commit. Build one Git archive that contains Topic 53. Upload
the archive and the archived launcher to each authorized host. The launcher
compares its own bytes with the archived copy before compilation.

```bash
commit=$(git rev-parse HEAD)
archive=/tmp/topic53-${commit}.tar.gz
git archive --format=tar.gz \
  --prefix="systems-snackpack-${commit}/" \
  -o "$archive" "$commit" topics/053-nvme-blk-mq
archive_sha=$(shasum -a 256 "$archive" | awk '{print $1}')

scp "$archive" topics/053-nvme-blk-mq/experiment/run_host.sh \
  dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com:/tmp/
ssh dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
  "SOURCE_COMMIT='$commit' SOURCE_ARCHIVE_SHA256='$archive_sha' \
   SOURCE_ARCHIVE_PATH='/tmp/topic53-${commit}.tar.gz' \
   bash /tmp/run_host.sh /tmp/topic53-arm-receipt \
   dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
   dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com aarch64"
```

Resolve `xxl` at run time. Confirm its architecture before transfer.

```bash
xxl_host=$(ssh -G xxl | awk '$1 == "hostname" {print $2; exit}')
xxl_runtime=$(ssh xxl hostname -f)
xxl_architecture=$(ssh xxl uname -m)
test "$xxl_architecture" = x86_64
{
  printf 'alias=xxl\n'
  printf 'ssh_config_hostname=%s\n' "$xxl_host"
  printf 'runtime_hostname=%s\n' "$xxl_runtime"
  printf 'architecture=%s\n' "$xxl_architecture"
  date -u '+observed_utc=%Y-%m-%dT%H:%M:%SZ'
} > /tmp/topic53-xxl-resolution.txt
scp "$archive" topics/053-nvme-blk-mq/experiment/run_host.sh xxl:/tmp/
ssh xxl \
  "SOURCE_COMMIT='$commit' SOURCE_ARCHIVE_SHA256='$archive_sha' \
   SOURCE_ARCHIVE_PATH='/tmp/topic53-${commit}.tar.gz' \
   bash /tmp/run_host.sh /tmp/topic53-x86-receipt \
   xxl '$xxl_runtime' x86_64"
```

Retain `/tmp/topic53-xxl-resolution.txt` with the controller evidence. The
record binds the authorized alias to the SSH configuration value and the host
that answered at run time. It does not prove that DNS or SSH configuration
will resolve the same way in a later run.

The launcher rejects memory-backed, overlay, and network filesystems. It maps
the data mount's major and minor device number through sysfs, then records the
full `lsblk` parent stack. It also records CPU, kernel, compiler, mount,
`blk-mq`, queue, NVMe controller, interrupt-affinity, virtualization, and
control-group evidence. It writes no sysfs field.

The launcher builds with:

```bash
cc -O3 -g -fno-omit-frame-pointer -march=native -std=gnu11 \
  -Wall -Wextra -Werror nvme_aio_depth_probe.c -o nvme_aio_depth_probe
```

It retains source and binary Secure Hash Algorithm 256-bit (SHA-256) digests,
compiler identity, Executable and Linkable Format (ELF) metadata, full
disassembly, compiler assembly, and focused disassembly for
`cached_read_loop` and `direct_aio_loop`. Userspace assembly cannot show
`blk-mq` dispatch or NVMe commands. It verifies only the workload that called
the kernel.

## Receipt verification

[`validate_receipt.py`](validate_receipt.py) independently verifies source and
binary identity, host identity, the fixed schedules, every raw process, counter
deltas, analysis, controls, cleanup, and the receipt seal.

```bash
python3 -I -B experiment/validate_receipt.py /path/to/receipt \
  --expected-label xxl \
  --expected-hostname "$xxl_runtime" \
  --expected-architecture x86_64 \
  --expected-commit "$commit" \
  --expected-archive-sha256 "$archive_sha"
```

`MANIFEST.sha256` contains one sorted GNU SHA-256 line for every retained file
except the manifest and `SEALED`. `SEALED` contains `topic53-receipt.v1`. The
launcher removes all write bits after sealing. A validator exit status alone
cannot accept an incomplete or writable receipt.

## Expected observations and limits

Depth eight can increase throughput when depth one leaves the observed path
underfilled. Depth eight can also leave throughput flat while queueing grows.
The probe cannot attribute either result to a specific tag limit, scheduler,
driver queue, hypervisor, cloud-volume cap, controller, or flash medium.

An NVMe-named guest device does not prove local Peripheral Component
Interconnect Express (PCIe) flash. Amazon Elastic Block Store and other virtual
backends can expose NVMe namespaces. `O_DIRECT` minimizes Linux page-cache
effects. It does not bypass a hypervisor, service cache, controller cache, or
device cache.

The two retained host results describe those exact hosts and run windows. A
cross-host difference does not establish an Arm, x86-64, CPU-vendor, NVMe, or
filesystem-wide effect.

## Primary sources

- [Linux multi-queue block I/O queueing](https://docs.kernel.org/block/blk-mq.html)
- [Linux block device I/O statistics](https://docs.kernel.org/admin-guide/iostats.html)
- [Linux `io_submit(2)`](https://man7.org/linux/man-pages/man2/io_submit.2.html)
- [Linux `io_getevents(2)`](https://man7.org/linux/man-pages/man2/io_getevents.2.html)
- [Linux `open(2)` and `O_DIRECT`](https://man7.org/linux/man-pages/man2/open.2.html)
- [Linux `statx(2)` direct-I/O alignment](https://man7.org/linux/man-pages/man2/statx.2.html)
- [NVM Express specifications](https://nvmexpress.org/specifications/)
