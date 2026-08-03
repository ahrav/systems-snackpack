# Allocator internals and fragmentation

Equal live bytes do not imply equal reclaimable pages. A live allocation can
pin the page or arena span that contains it after neighboring allocations are
freed.

## Cost model

The focused experiment allocates 262,144 blocks of 256 requested bytes. Each
treatment retains 16,384 blocks and 4,194,304 requested bytes:

```text
survivors = allocation_count / spacing
requested_live = survivors * requested_block_bytes
```

The compact treatment keeps the first 16,384 blocks. The scattered treatment
keeps every sixteenth block. [`Geometry`](src/lib.rs) models their equal live
payload and different fixed-stride address spans. It does not convert an
address span into resident set size (RSS).

## Linux experiment

The C probe uses glibc `malloc`. It fixes one arena, disables mmap allocation,
and disables automatic trimming. It touches every allocation, frees one of the
two survivor patterns, records `smaps_rollup` and `mallinfo2`, then calls
`malloc_trim(0)`.

Run one process on glibc Linux:

```bash
cc -std=c11 -O2 -g -Wall -Wextra -Werror -fno-omit-frame-pointer \
  experiment/allocator_frag_probe.c -o /tmp/allocator_frag_probe
/tmp/allocator_frag_probe compact A 1 1 262144 256
```

Run the retained fresh-process schedule:

```bash
python3 experiment/run_processes.py \
  /tmp/allocator_frag_probe /tmp/topic24-processes 0
python3 experiment/validate_receipts.py /tmp/topic24-processes
```

`experiment/run_host.sh` binds a run to one source tree, records host and ELF
facts, runs the schedule, and hashes the evidence. Its output directory must be
outside the repository.

## Evidence boundary

`mallinfo2.uordblks` is allocator accounting. `smaps_rollup` is process-wide
kernel accounting. Neither identifies a per-allocation cause. Equal live-byte
accounting paired with different arena, anonymous-memory, and RSS values can
support a fragmentation hypothesis for the named glibc build and workload.

The experiment excludes multiple arenas, cross-thread frees, mixed size
classes, allocator caches beyond one thread, and default mmap and trim policy.
One host result does not represent an instruction set or allocator family.

The exact-source run retained 4,194,304 requested live bytes and 4,325,376
usable live bytes in both treatments. Post-trim RSS was 9.083 times higher for
the scattered layout on the named x86-64 host and 9.444 times higher on the
named AArch64 host. See the comparison note for intervals and controls.

See [round 1](rounds/01.md), [references](references.md), and the
[measurement contract](measurements/README.md).
