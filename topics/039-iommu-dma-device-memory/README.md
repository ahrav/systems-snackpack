# IOMMU, DMA, and device memory

A central processing unit (CPU) pointer is not a device address. Treating the
two as interchangeable can corrupt unrelated memory, expose stale data, or
free storage while a device is still using it. This topic keeps the address,
visibility, ordering, ownership, and completion contracts separate.

Direct memory access (DMA) lets a device move bytes without a CPU load and
store for every byte. An input-output memory management unit (IOMMU) can
translate and restrict a device address, called an input-output virtual address
(IOVA), to physical memory. Translation is useful, but it proves only that the
device may reach the mapped range.

## Start with five separate proofs

Use one 64-kibibyte (KiB) receive buffer as the running example. One KiB is
1,024 bytes. CPU code sees virtual address `0x7f20_0000_0000`. Four physically
scattered 16 KiB regions back it. The driver gives the device one contiguous
IOVA range beginning at `0x4000_0000`. The executable probe models this same
shape at a smaller size: a 16 KiB buffer backed by four scattered 4 KiB pages
at the same base addresses.

Before the device writes that buffer, establish all five claims:

1. **Reachability:** a live device-specific mapping covers the exact IOVA,
   length, direction, and address width.
2. **Visibility:** the new owner can observe the latest bytes. Hardware
   coherence or a DMA synchronization operation supplies this property.
3. **Ordering:** descriptor fields become visible before an ownership flag or
   memory-mapped input/output (MMIO) doorbell announces work.
4. **Ownership:** CPU code does not read or change a streaming buffer while the
   device owns it.
5. **Completion and lifetime:** a real provider completion occurs before
   unmap, unpin, free, reset reuse, or process teardown.

No proof substitutes for another. An IOMMU rejects an address outside its
aperture, but it cannot detect a wrong offset inside an allowed buffer. A
memory barrier orders operations, but it does not wait for DMA to finish or
flush a noncoherent cache. Pinning preserves backing pages, but it creates no
device mapping.

## Choose the memory contract deliberately

| Technique | Problem solved | Simple mechanism | Does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- | --- |
| Coherent DMA allocation | Long-lived rings and descriptors need mutual CPU/device visibility | Linux allocates a stable coherent mapping | Ordering, ownership, atomicity, or completion | Coherent writes can still be observed in the wrong order | Control structures live for many operations |
| Streaming DMA mapping | Payload ownership alternates between CPU and device | Map for a direction, synchronize at handoffs, then unmap | Completion or safe lifetime by itself | Direction, size, device, and unmap arguments must match | Bulk payloads are reused between transfers |
| Scatter/gather mapping | A device should consume physically scattered storage efficiently | Linux may merge input entries into fewer hardware segments | Unmap-count bookkeeping | Program the mapped count, but unmap with the original count | Hardware supports a segment list |
| IOMMU translation | A device needs isolation, address-width bridging, or contiguous IOVA space | Device identity selects an I/O page table | Cache visibility, ordering, in-range bugs, or group topology | Map, invalidation, and translation-cache costs | Isolation or flexible address layout matters |
| Software I/O translation lookaside buffer (SWIOTLB) | The device cannot reach or safely expose the original memory | Linux copies through a device-reachable bounce buffer | Ownership or ordering | Extra copy traffic, pool pressure, and size limits | The DMA layer reports that bouncing is required |
| Shared virtual addressing (SVA) | A capable device should use process virtual addresses | Process Address Space ID (PASID), Address Translation Services (ATS), and Page Request Interface (PRI) select, cache, and fault translations | Coherence, bounded fault latency, or universal support | Stale translations and fault storms require strict lifecycle control | Pointer-rich accelerators justify replayable faults |
| Device-local or peer memory | Data should remain near a device or move between devices | Provider-specific mappings expose device memory or peer-to-peer DMA | Ordinary RAM semantics or portable topology | MMIO access rules, revocation, and topology support | Measured locality wins and every provider supports the path |

Coherent means visibility without the streaming synchronization calls. It does
not mean ordered. Linux still requires a DMA write barrier before publishing a
descriptor ownership bit:

```c
desc->addr = cpu_to_le64(payload_dma);
desc->len = cpu_to_le32(payload_len);
dma_wmb();
WRITE_ONCE(desc->owner, DEVICE_OWN);
writel(queue_index, doorbell);
```

For a streaming receive buffer, the direction is part of the mapping contract:

```c
dma_addr_t payload_dma =
    dma_map_single(dev, payload, payload_len, DMA_FROM_DEVICE);
if (dma_mapping_error(dev, payload_dma))
    return -ENOMEM;

/* Publish the descriptor, then wait for the provider's real completion. */
dma_sync_single_for_cpu(dev, payload_dma, payload_len, DMA_FROM_DEVICE);
consume_read_only(payload, payload_len);

/* Stop submissions and drain the device before this teardown. */
dma_unmap_single(dev, payload_dma, payload_len, DMA_FROM_DEVICE);
```

`DMA_FROM_DEVICE` means that the device writes system memory and the CPU later
reads it. `dma_addr_t` is a device-facing token; CPU code must not dereference
it. Real drivers also publish the descriptor with the required ordering and
must not infer completion from elapsed time.

Linux may merge a scatter/gather list:

```c
int mapped_nents = dma_map_sg(dev, sg, original_nents, DMA_FROM_DEVICE);
if (mapped_nents == 0)
    return -ENOMEM;

program_hardware(sg, mapped_nents);
/* Later, after completion: */
dma_unmap_sg(dev, sg, original_nents, DMA_FROM_DEVICE);
```

The hardware consumes `mapped_nents`. Synchronization and unmap use the
original entry count according to the Linux DMA API contract.

## Use costs as screens, not forecasts

First ask how many IOMMU translations cover the buffer. Let `B` be buffer
bytes, `G` the actual IOMMU mapping granule, and `O` the starting offset within
one granule, where `0 <= O < G`:

```text
translations = ceil((O + B) / G)
```

The running buffer starts at aligned IOVA `0x4000_0000`, so `O = 0`. For 64
KiB and 4 KiB mappings, `ceil((0 + 64) / 4) = 16` translations. The same
length starting one byte after a granule boundary needs `ceil((1 + 64 KiB) /
4 KiB) = 17`. A pool of 1,024 aligned buffers can therefore require up to
`1,024 * 16 = 16,384` leaf translations before legal coalescing. In plain
language: alignment, physical layout, reuse, and supported larger mappings
determine translation pressure.

Next ask whether setup is reused. Let `T_pin` be pinning time, `T_iova` IOVA
allocation time, `T_pte(P)` page-table work for `P` translations, `T_inv`
invalidation time, and `R` completed reuses:

```text
setup_per_use = (T_pin + T_iova + T_pte(P) + T_inv) / R
```

If those setup terms total 80 microseconds and the mapping is safely reused
1,000 times, the screen gives `80 us / 1,000 = 80 nanoseconds` per use. Mapping
for every request pays the full 80 microseconds. This illustrative arithmetic
supports a reuse experiment; it is not a measured kernel cost. Persistent
mappings also retain pages and a longer-lived device aperture.

A bounce path adds at least one full copy. Let `N_copy` be the number of copy
passes, `B` the bytes, `C_copy` measured copy bandwidth, and `T_pool` bounce
pool overhead:

```text
bounce_extra = (N_copy * B) / C_copy + T_pool
```

For one 64 KiB copy at an illustrative 25 gibibytes per second (GiB/s),
`65,536 / (25 * 2^30) = 2.44 microseconds`, before pool and cache effects. In
plain language: a one-way bounce copies at least 64 KiB, causing at least a
64 KiB read and 64 KiB write, but only measurement can say whether that term
dominates.

Finally, translation-cache reach is approximately the entry count times the
mapping granule. Let `E` be effective cached IOMMU translations:

```text
translation_reach = E * G
```

With an illustrative `E = 512` and `G = 4 KiB`, reach is `512 * 4 KiB = 2
MiB`. Random DMA across 64 MiB exceeds that example. The real entry count,
associativity, replacement, and page-walk caches are hardware-specific; the
equation identifies a workload dimension to vary, not a hardware fact.

## Checked model and generated code

The Rust model distinguishes CPU virtual addresses, physical addresses, and
IOVAs at the type level. It accepts a contiguous IOVA over noncontiguous
physical pages, checks the inclusive DMA mask, direction, epoch, ownership,
completion identity, and scatter counts, and rejects early unmap. It also
demonstrates the IOMMU's limit: a wrong offset inside the aperture translates
successfully and needs a payload canary or higher-level protocol check.

Run it with:

```bash
cargo run --locked --package iommu-dma-device-memory \
  --bin dma-contract-probe
cargo test --locked --package iommu-dma-device-memory
```

The linked `topic39_checked_translate` and `topic39_mask_allows` functions make
the checked arithmetic visible to `objdump`. A compiler can implement their
comparisons with branches, conditional selects, or another equivalent sequence.
The retained disassembly proves only that both checked hooks remain in the CPU
executable. DMA mappings, IOMMU page-table walks, cache maintenance, and MMIO
happen outside this generated code.

Current mainline Linux source also illustrates an architecture boundary:
arm64 lowers the DMA write barrier to an outer-shareable-store `dmb` barrier,
while x86 defines its DMA write barrier as a compiler barrier. These are source
observations for current mainline, not measurements of these two hosts and not
evidence that every x86 device path is coherent or every Arm device path is
noncoherent.

## Failure modes and advice that breaks down

- **“Coherent means no barriers.”** Coherence supplies visibility, not the
  descriptor protocol's ordering.
- **“A barrier flushes caches.”** An ordering barrier and cache maintenance
  solve different problems.
- **“DMA mapping is address arithmetic.”** Mapping can install IOMMU entries,
  maintain caches, allocate bounce storage, validate device limits, and change
  ownership.
- **“The IOMMU makes the device safe.”** It blocks outside-aperture access, but
  not a bad offset inside an allowed mapping, broken firmware, unsafe group
  topology, or an in-flight unmap.
- **“Pin everything for speed.”** Long-lived pins reduce reclaim and migration,
  complicate writeback, and enlarge the device's reachable lifetime.
- **“`mlock` makes memory DMA-safe.”** It neither creates an IOVA nor supplies
  the DMA API's cache and ownership contract.
- **“Virtual address equals IOVA, so the mapping works.”** SVA may make the
  numbers equal while CPU and device translation machinery remains separate.
- **“Completion means delivery.”** A DMA completion proves only the provider's
  documented local operation; application delivery and durability are separate.
- **“x86 is coherent and Arm is not.”** Coherence is a platform and device-path
  property, not a safe instruction-set-family rule.
- **“Huge pages are always faster.”** Alignment, physical contiguity, mapping
  support, overpinning, and invalidation cost can reverse the result.
- **“Zero copy is always faster.”** Setup, synchronization, translation misses,
  invalidation, and lifetime pressure can cost more than copying a small buffer.
- Incorrect direction, size, device, or unmap count can expose stale bytes or
  let a dirty CPU cache line overwrite device data.
- Device and CPU ownership in one cache line can corrupt unrelated fields on a
  noncoherent path.
- Stale ATS translations after page reuse can let a device write into the
  page's new owner.
- PRI fault storms can exhaust queues, amplify tail latency, or deadlock an
  accelerator runtime without bounded fault handling.
- SWIOTLB pools can exhaust, and their size limits are kernel-version-sensitive.
- Device Base Address Register (BAR) memory is MMIO, not ordinary host RAM;
  plain pointer access and ordinary `memcpy` are not portable substitutes for
  I/O mappings and accessors.

## What the focused experiment establishes

The experiment is a deterministic CPU-side contract check. It runs in fresh
processes and inspects the linked address-checking functions on both required
Linux targets. It does not time or perform DMA because neither target exposes
an authorized, comparable device path to this unprivileged workload. A CPU-only
timing would measure process startup and arithmetic, not IOMMU performance.

The host runner records the exact source archive, Secure Shell (SSH) target
label and runtime-resolved hostname, architecture, CPU model, kernel, compiler
and Rust toolchain, target features, build flags, available CPUs, page size,
kernel configuration, visible IOMMU groups, and generated code. It runs generic
and native builds in independent processes and requires identical expected
output. See [`rounds/01.md`](rounds/01.md) for the acceptance contract and
[`measurements/README.md`](measurements/README.md) for retained evidence.

### Retained two-host observation

Both required hosts ran source commit
`3aaece99023cfa33440af7c5f90204c18840953d` from one Git archive with SHA-256
digest `9da821782a8fd37023a05e4ca08e8e942831eabf3410eabe31e81128913765f8`.
All 16 fresh correctness processes per host matched expected output, and every
package, source-integrity, receipt, and generated-code gate passed. No timing
was collected.

The Arm target was
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, AArch64, Linux
`6.12.95-124.187.amzn2023.aarch64`, with 64 available CPUs. Its processor
identification was implementer `0x41`, part `0xd40`, variant `0x1`, revision
`0x1`. The generic compiler target enabled Neon; the native C query reported
`armv8.4-a+crypto+sha3+sm4+sve+rng+i8mm+bf16`. Rust was 1.95.0 and GCC was
11.5.0.

SSH alias `xxl` resolved at run time to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. It reported x86-64, Linux
`6.12.95-124.187.amzn2023.x86_64`, 192 available CPUs, and Intel Xeon Platinum
8488C under Kernel-based Virtual Machine (KVM). The generic Rust target enabled
SSE and SSE2; the native C query reported Sapphire Rapids tuning with AVX2,
AVX-512F, and SSE4.2 enabled. Rust was 1.97.1 and GCC was 11.5.0.

Both kernels were configured with PCI ATS, PRI, PASID, VFIO, IOMMU SVA, and
SWIOTLB support. The Arm config also enabled Arm SMMU and SMMUv3; the x86 config
enabled Intel and AMD IOMMU support. The guest-visible sysfs view showed zero
IOMMU class entries, zero groups, and zero PCI group links on both hosts. That
absence does not prove that the physical host lacks an IOMMU or that a real
device would bypass translation.

Generated code differed without changing the model result. The Arm executable
contained direct calls to both hooks and used `sub`, `adds`, `ccmp`, `csinv`,
and `csel` in the generic checked translator. The x86-64 executable used
relative relocations plus indirect calls and implemented the checks with
`test`, `sub`, comparisons, branches, and `cmov`. These are observations of the
two named executables, not instruction-set-family performance claims.

## Practical selection guide

1. Use coherent allocation for small, long-lived control structures, and keep
   explicit descriptor barriers and ownership.
2. Use streaming mappings for bulk payloads, with exact direction,
   synchronization, completion, and matched unmap arguments.
3. Reuse mappings only after bounding pinned memory, device aperture, reset,
   invalidation, and teardown behavior.
4. Use an IOMMU when isolation or address flexibility matters; measure map,
   invalidation, and translation-working-set effects on the real device.
5. Accept SWIOTLB when required, but expose pool pressure and copy cost.
6. Choose SVA only when the complete endpoint, bridge, IOMMU, kernel, and driver
   support PASID, ATS, PRI, invalidation, reset, and bounded fault handling.
7. Treat device-local and peer memory as provider- and topology-specific, not
   as ordinary process memory.

The central rule is simple: a device address proves nothing by itself. Prove
reachability, visibility, ordering, ownership, and completion separately, then
measure the complete path whose cost matters.

## Sources

Primary sources and version boundaries are collected in
[`references.md`](references.md).
