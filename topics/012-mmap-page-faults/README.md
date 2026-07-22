# `mmap`, minor faults, and major faults

A successful `mmap()` creates a virtual mapping represented by VMA metadata. It
does not ordinarily prove that the backing data is resident, that a leaf
page-table entry exists, or that a CPU has cached the translation. Adjacent
mappings may share one merged VMA.

Track these states separately:

1. The VMA defines the address range, permissions, and backing object.
2. The backing page or folio may be absent, resident, or under I/O.
3. This process may lack a PTE even when the file data is in the page cache.
4. A present PTE may still miss in the TLB and require a hardware page-table walk.

A TLB miss that page-walks to a present, permission-compatible PTE is not a page
fault. A recoverable not-present or write-protection fault enters the kernel,
validates the VMA, resolves anonymous, copy-on-write, swap, or file state,
installs or updates a mapping, and retries the original instruction. Invalid or
disallowed accesses instead deliver a signal.

## Outcome classes

Linux man-pages describe a minor fault as one serviced without I/O and a major
fault as one that required I/O. Upstream Linux v6.18 accounting also marks a
successfully completed retried fault as major through `FAULT_FLAG_TRIED`, even
when the final handler result lacks `VM_FAULT_MAJOR`. A process counter delta is
therefore a kernel accounting result, not proof of one specific I/O event or
address. These labels do not define latency tiers.

| First access | Likely work | Typical class |
| --- | --- | --- |
| Private anonymous read | Map the shared zero page | Minor |
| Private anonymous write | Allocate and zero private page(s) or a folio | Minor |
| Cached file page without a PTE | Install mappings for ready cache pages | Minor |
| File page absent from the page cache | Read backing data and install a mapping | Major |
| Swapped-out anonymous page absent from swap cache | Read swap backing and remap | Major |

A minor fault can allocate page tables, zero memory, break COW, charge a memory
cgroup, contend on locks, or stall behind reclaim. A major fault does not prove
a physical-media access. Device caches, remote storage, readahead, and
virtualized backing remain below the accounting boundary.

Faults are not pages or I/O requests. File fault-around can install several
ready PTEs after one trap. Readahead can fetch data used by later faults.

The counters do not determine pages or storage operations:

```text
pages_touched cannot be inferred from minor_faults
storage_requests cannot be inferred from major_faults
bytes_read cannot be inferred from major_faults * page_size
```

## Choosing where to pay

| Technique | Work placement | Checkable result | Limit |
| --- | --- | --- | --- |
| Demand `mmap` | First access | Mapping exists | Fault latency lands on arbitrary loads |
| `MAP_POPULATE` | `mmap()` | Population attempted | Incomplete population does not fail `mmap()` |
| `MADV_WILLNEED` | Best-effort hint | None | Work may be partial or evicted |
| `MADV_POPULATE_READ` | Advice call | Page tables populated readable once | Partial work on error; no retention |
| `MADV_POPULATE_WRITE` | Advice call | Page tables populated writable once | Allocates pages, breaks COW, or preallocates blocks for file holes |
| Manual touch | Explicit loop | Touched addresses completed | Access mode and NUMA location affect the work |
| Buffered `read` | Explicit syscall | Byte count or error | Copies page-cache data to a destination buffer |
| `mlock` | Explicit call | Pages resident and retained | Limits and system-pressure costs apply |

If a request touches fraction `f` of `P` pages, demand population pays for
about `fP` pages while a complete eager strategy pays for about `P`. When the
complete population runs before the critical section, it moves that work out of
the critical section; it does not remove page-cache lookup, page-table
construction, reverse mapping, TLB fill, or memory pressure.

The following schematic model separates terms that measurements often merge:

```text
T_mmap ≈ T_vma
       + F * (T_exception + T_vma_lookup + T_fault_dispatch)
       + Pte * (T_page_table + T_rmap)
       + T_io(I, bytes, queue_depth)
       + T_readahead_waste + T_reclaim + T_tlb_teardown
       + T_user_access

T_read ≈ S * T_syscall
       + T_io(I, bytes, queue_depth)
       + copied_bytes / effective_copy_bandwidth
       + T_destination_first_touch + T_user_access
```

The coefficients depend on the kernel, filesystem, cgroup, NUMA policy, access
pattern, and host. Dividing elapsed phase time by fault count yields an
amortized phase metric, not fault-handler latency.

## Focused experiment

[`experiment/vm_faults.c`](experiment/vm_faults.c) measures one volatile byte
access per runtime base page in four fresh-process modes:

- `anon-first`: first write to a fresh private anonymous mapping.
- `anon-refault`: first read after allocating pages and discarding them with
  `MADV_DONTNEED`.
- `file-warm`: file data resident but this process has no PTEs.
- `file-cold`: file data verified nonresident after `POSIX_FADV_DONTNEED`.

Both file modes use `MADV_RANDOM`. This deliberately sharpens the major-fault
case by suppressing ordinary sequential readahead. It does not model a normal
sequential scan or compare `mmap` with buffered I/O.

The recorded runner binds execution to the supplied archive SHA-256, checks that
its embedded commit metadata matches the caller assertion, extracts it into a
private tree, runs the workspace gates, compiles the C workload, checks its
linked code, and executes eight order-balanced blocks:

```bash
git archive --format=tar --prefix=source/ HEAD | gzip -n > /tmp/topic12.tar.gz
archive_sha=$(sha256sum /tmp/topic12.tar.gz | awk '{print $1}')
commit=$(git rev-parse HEAD)

SOURCE_ARCHIVE=/tmp/topic12.tar.gz \
  topics/012-mmap-page-faults/experiment/run_processes.sh \
  /absolute/output dev-host "$commit" "$archive_sha" \
  /absolute/storage-backed-directory 0 8 32
```

The runner rejects storage directories whose reported filesystem type is
`tmpfs` or `ramfs` and records the accepted type. That control does not prove a
physical-storage path. The runner rejects every `file-cold` row unless
`mincore()` reports zero resident pages before access, all pages resident
afterward, and at least one major fault. It records setup time separately from
the touch loop. The process is the replication unit; pages inside a process are
not independent samples.

The SHA-256 binds the run to archive bytes. The runner does not independently
prove that those bytes came from a trusted Git object database. For publication,
create the archive from the pushed commit and record both values.

Run the portable contracts and build-only benchmark locally:

```bash
cargo run -p systems-snackpack-topic-012 --example check_contracts
cargo bench -p systems-snackpack-topic-012 --bench fault_cost_model
```

The Rust benchmark measures only pure metric calculation. It makes no VM
performance claim. Use the Linux process runner for page-fault observations.

## Failure controls

- `mincore()` is a possibly stale residency snapshot, not proof that the next
  access cannot fault.
- `POSIX_FADV_DONTNEED` is best effort. Dirty, partial, mapped, or concurrently
  used pages can remain resident.
- A sparse `ftruncate()` fixture can return zero-filled holes without the
  intended data path. The workload writes a full deterministic byte pattern and
  calls `fdatasync()`.
- `MAP_POPULATE` does not guarantee complete population or retention.
- `MADV_POPULATE_READ` may map the shared zero page rather than allocate private
  writable pages.
- A concurrent file truncation can turn a previously valid mapped access into
  `SIGBUS`.
- Global `drop_caches` perturbs the whole host. The experiment uses an owned
  disposable file and per-file advice.
- Prefaulting from a setup thread can place memory according to that thread's
  NUMA policy rather than the consumer's location.

Read [the first-visit note](rounds/01.md), [the source ledger](references.md),
and [the measurement protocol](measurements/README.md).
