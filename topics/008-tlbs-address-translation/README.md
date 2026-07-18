# Topic 8: TLBs, huge pages, and shootdowns

A translation lookaside buffer (TLB) caches virtual-to-physical translations.
Its miss path walks page tables; a page fault is a separate kernel exception.
Mapping changes must also invalidate stale per-CPU translations.

## Cost model

Use two models before choosing a page size or changing mappings:

```text
translation exposure
  ~= accesses * TLB-miss probability * unhidden walk cost

mapping-change exposure
  ~= page-table update + invalidation dispatch
     + slowest required remote acknowledgement + collateral refill
```

Larger pages increase the address range represented by each TLB entry. They
can also reduce page-table depth and memory. Those gains must repay allocation,
zeroing, compaction, resident-set inflation, copy-on-write, NUMA-placement, and
split costs. A process context identifier or address-space identifier reduces
unrelated flushes; it does not make stale translations safe.

## Experiment boundary

The Linux-only experiment rejects hosts that do not report 4 KiB base pages
and 2 MiB PMD THPs. It has two workloads:

- `reach` follows one dependent load per base page. It compares an explicit
  base-page mapping with a mapping verified through `/proc/self/smaps` to use
  2 MiB anonymous transparent huge pages.
- `shootdown` times `mprotect` write-disable/write-enable pairs while 1 or 16
  pinned reader threads share the same address space.

The reach result measures steady-state dependent-access time after mapping
setup and warmup. The shootdown result measures end-to-end `mprotect` pair
time. It includes system calls, page-table work, scheduling, reader
interference, invalidation, and acknowledgement. It is not a direct measure of
interprocessor-interrupt or architecture instruction latency.

## Recorded result

The 2026-07-18 run used source candidate `2a3b412`, 12 fresh order-balanced
process pairs, a 256 MiB reach mapping, 64 passes, and 20,000 permission-change
pairs per process. Values below are host observations, not ISA claims.

| Host | Reach base | Reach THP | Paired base/THP median (96.1% interval) | Permission 1 reader | Permission 16 readers | Paired 16/1 median (96.1% interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Arm host | 129.831 ns/access | 116.508 ns/access | 1.119 (1.091, 1.141) | 4.866 us/pair | 5.454 us/pair | 1.119 (0.949, 1.310) |
| `xlg` | 158.537 ns/access | 32.053 ns/access | 5.035 (4.794, 5.108) | 14.832 us/pair | 22.624 us/pair | 1.571 (1.417, 1.607) |

Each individual timing is a mean across 12 processes. Paired columns report
median ratios and intervals. Dated records give standard deviations, setup and
external-wall boundaries, PMU observations, generated code, and exact host
identities.

## Run

Check the mapping and checksum contracts:

```bash
cargo bench -p systems-snackpack-topic-008 --bench address_translation -- --verify
```

Run 12 fresh, order-balanced process pairs on Linux:

```bash
topics/008-tlbs-address-translation/experiment/run_processes.sh \
  /tmp/systems-snackpack-topic-008
cat /tmp/systems-snackpack-topic-008/summary.txt
```

The runner fixes the reach mapping at 256 MiB with 64 full passes and the
shootdown workload at 20,000 `mprotect` pairs. It records setup, warmup, the
timed region, time from `run` entry to immediately before result output, and
external launch-to-exit wall time separately. The latter includes launcher
overhead, startup, output, teardown, and exit. The summarizer treats each
process as one replication unit. Its exact 96.1% paired-median interval is the
third through tenth ordered ratio from 12 pairs, under independent,
identically distributed continuous pair ratios.

Inspect [Round 1](rounds/01.md), [measurement records](measurements/README.md),
and [primary sources](references.md) before interpreting a host result.
