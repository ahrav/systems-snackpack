# Focused Linux experiment

This experiment tests three narrow claims on one Linux host at a time:

The Portable Operating System Interface (POSIX) defines the
`POSIX_FADV_*` advice values used below.

1. `POSIX_FADV_SEQUENTIAL` can populate more page-cache pages than the one
   page that a process asks to read.
2. `POSIX_FADV_RANDOM` can suppress that read-ahead effect for the same
   one-page read.
3. The same 16-mebibyte (MiB) file takes different elapsed time to scan with
   sequential buffered reads, randomized buffered reads, and aligned direct
   input/output where the filesystem reports support.

The experiment does not prove device-cold latency. It uses
`POSIX_FADV_DONTNEED` and `mincore`, Linux's page-residency query, to verify
that the test mapping has zero resident pages before each measured scan. The
backing device can still contain the data in an internal cache. The timing
result applies only to the recorded host, kernel, filesystem, device path,
compiler, binary, file, and run window.

## Workload

[`pcbench.c`](pcbench.c) creates deterministic 4-kibibyte (KiB) blocks. It
verifies each block after `pread`. The native program emits one JavaScript Object Notation
(JSON) object per process. It records startup separately from the measured
read loop. It also records process input/output counters from `/proc/self/io`,
page residency from `mincore`, and direct-I/O alignment from the `statx`
metadata query with the `STATX_DIOALIGN` mask.

[`run_processes.py`](run_processes.py) starts a fresh native process for every
observation. It uses fixed, order-balanced four-process blocks. ABBA and BAAB
place both treatments in early and late positions:

| Campaign | Fixed blocks | Ratio |
|---|---:|---|
| `primary` | 8 | randomized buffered / sequential buffered |
| `aa` | 8 | sequential label Y / sequential label X |
| `direct` | 4 | direct sequential / buffered sequential |

The runner journals each planned process before launch. It stops at the first
invalid attempt and never replaces a failed observation.
[`analyze.py`](analyze.py) treats one complete four-process block as the
independent unit. It reports the geometric mean ratio and a two-sided 95%
Student-t interval across block log ratios. This interval uses the variation
between complete blocks. It covers process-to-process variation within this
fixed run window. It does not cover other hosts, builds, kernels, or devices.
The A/A campaign runs the same treatment under two labels. It checks whether
the label paths behave alike, but it is not a calibrated noise floor.

The semantic controls also:

- compare one sequential-advice read with one random-advice read after verified zero residency;
- confirm that a buffered write populates the page cache;
- record the fill-and-write loop separately from a later interval that includes
  sampling and ends when `fdatasync` returns;
- confirm that `fdatasync` does not imply page-cache eviction;
- record page residency after each direct read without treating zero residency
  as an application binary interface guarantee.

## Exact-source host run

Run only from a pushed commit. Create a Git archive that contains Topic 51, upload the archive and this launcher to each authorized host, and execute the launcher from outside the extracted archive. The launcher checks that its bytes match the archived launcher before it builds anything.

Each host needs Linux user-space API headers 6.1 or newer. `pcbench.c` reads the
direct-I/O alignment that `statx` reports through `stx_dio_mem_align` and
`stx_dio_offset_align`, which Linux 6.1 added alongside the `STATX_DIOALIGN`
mask bit. Older headers stop the build with an explicit `#error`. The launcher
also requires `rustc`, `sysctl`, `cc`, `python3`, and `rg` on `PATH`.

Controller example:

```bash
commit=$(git rev-parse HEAD)
archive=/tmp/topic51-${commit}.tar.gz
git archive --format=tar.gz \
  --prefix="systems-snackpack-${commit}/" \
  -o "$archive" "$commit" topics/051-page-cache-io
archive_sha=$(shasum -a 256 "$archive" | awk '{print $1}')

scp "$archive" \
  topics/051-page-cache-io/experiment/run_host.sh \
  dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com:/tmp/
ssh dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
  "SOURCE_COMMIT='$commit' SOURCE_ARCHIVE_SHA256='$archive_sha' \
   SOURCE_ARCHIVE_PATH='/tmp/topic51-${commit}.tar.gz' \
   bash /tmp/run_host.sh /tmp/topic51-arm-receipt \
   dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
   dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com aarch64"
```

Resolve `xxl` at run time. Do not reuse a previously observed hostname:

```bash
xxl_host=$(ssh xxl hostname -f)
xxl_arch=$(ssh xxl uname -m)
test "$xxl_arch" = x86_64
scp "$archive" topics/051-page-cache-io/experiment/run_host.sh xxl:/tmp/
ssh xxl \
  "SOURCE_COMMIT='$commit' SOURCE_ARCHIVE_SHA256='$archive_sha' \
   SOURCE_ARCHIVE_PATH='/tmp/topic51-${commit}.tar.gz' \
   bash /tmp/run_host.sh /tmp/topic51-x86-receipt \
   xxl '$xxl_host' x86_64"
```

The run uses a bounded 16 MiB data file and a 4 MiB write control under `/var/tmp` by default. It rejects `tmpfs` and `ramfs`. It never drops global caches, touches a raw block device, or needs privilege. On success, it removes the disposable data and seals the receipt read-only under `/tmp`. The controller must retrieve the receipt, verify it, then remove only its exact uploaded archive, launcher, and receipt paths.

## Receipt verification

Validate a retrieved receipt with the expected source and host identity:

```bash
python3 -I -B experiment/validate_receipts.py /path/to/receipt \
  --expected-target-label xxl \
  --expected-hostname "$xxl_host" \
  --expected-architecture x86_64 \
  --expected-source-commit "$commit" \
  --expected-source-archive-sha256 "$archive_sha"
```

[`validate_receipts.py`](validate_receipts.py) independently checks the archive boundary, source freeze, host identity, block-backed mount evidence, build and code generation, semantic controls, fixed schedules, raw hashes, process uniqueness, complete-block estimates, cleanup record, and final manifest.

## Expected observations

- Success requires the one-read sequential probe to leave more than one page
  resident after 20 ms and the random probe to leave exactly one page resident.
- Success requires every timed scan to begin with zero resident pages and
  report one file-size worth of physical read bytes at the process boundary.
- Success requires buffered scans to leave all file pages resident. A supported
  direct scan records final residency but does not require zero. Linux
  documents `O_DIRECT` as trying to minimize cache effects, so zero resident
  pages is an observation rather than an application binary interface
  guarantee.
- The primary treatment changes access order and advice together. A slower
  randomized scan is consistent with losing sequential read-ahead and request
  locality, but this experiment does not isolate those effects. Treat the
  observed ratio as a host-specific measurement, not a filesystem or
  instruction-set constant.
- The write control records the fill-and-write-loop interval and a later
  interval that ends when `fdatasync` returns. The later interval also includes
  intervening process and kernel sampling, so it is not isolated `fdatasync`
  latency. The control requires the pages to remain resident after completion.
  Global dirty and writeback counters remain contextual because other
  processes can change them.

If direct I/O is unsupported, the fixed direct campaign fails instead of
silently switching methods. That host then lacks a complete publication
receipt for this experiment.
