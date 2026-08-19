# Input-output memory management units, direct memory access, and device memory

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
   coherence, meaning CPU and device caches automatically agree on bytes, or a
   DMA synchronization operation supplies this property.
3. **Ordering:** fields in a descriptor, the small record that tells the device
   what work to do, become visible before an ownership flag or memory-mapped
   input/output (MMIO) doorbell announces work.
4. **Ownership:** CPU code does not read or change a streaming buffer, meaning
   payload storage mapped for a transfer, while the device owns it.
5. **Completion and lifetime:** the real device or driver reports completion
   before code removes the address mapping, releases pinned pages, frees the
   storage, reuses it after reset, or shuts down the process.

No proof substitutes for another. An IOMMU rejects an address outside its
aperture, meaning the allowed device-address range, but it cannot detect a
wrong offset inside an allowed buffer. A memory barrier orders operations, but
it does not wait for DMA to finish or flush a noncoherent cache, where CPU and
device views do not automatically agree. Pinning keeps backing pages from
moving or disappearing, but it creates no device mapping.

## Choose the memory contract deliberately

| Technique | Problem solved | Simple mechanism | Does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- | --- |
| Coherent DMA allocation | Long-lived circular descriptor arrays, called rings, need mutual CPU/device visibility | Linux allocates a stable coherent mapping | Ordering, ownership, whether a multi-step change appears indivisible, or completion | Coherent writes can still be observed in the wrong order | Control structures live for many operations |
| Streaming DMA mapping | Payload ownership alternates between CPU and device | Map for a direction, synchronize at handoffs, then unmap | Completion or safe lifetime by itself | Direction, size, device, and unmap arguments must match | Bulk payloads are reused between transfers |
| Scatter/gather mapping | A device should consume physically scattered storage efficiently | Linux may merge input entries into fewer hardware segments | Keeping the original and mapped counts straight | Program the mapped count, but unmap with the original count | Hardware supports a segment list |
| IOMMU translation | A device needs isolation, support for a device with a narrower address width, or contiguous IOVA space | Device identity selects a device-facing page table, which maps device ranges to physical memory | Cache visibility, ordering, in-range bugs, or which devices share one isolation boundary | Creating maps, discarding stale cached translations, and misses in the hardware cache of recent translations | Isolation or flexible address layout matters |
| Software input-output translation lookaside buffer (SWIOTLB) | The device cannot reach or safely expose the original memory | Linux copies through a device-reachable bounce buffer | Ownership or ordering | Extra copy traffic, pool pressure, and size limits | The DMA layer reports that bouncing is required |
| Shared virtual addressing (SVA) | A capable device should use process virtual addresses | Process Address Space ID (PASID), Address Translation Services (ATS), and Page Request Interface (PRI) select, cache, and request missing translations | Coherence, bounded fault latency, or universal support | Stale translations and fault storms require strict lifecycle control | The device may pause, request a missing translation, and retry the work |
| Device-local or peer memory | Data should remain near a device or move between devices | Mappings supplied by the device driver expose device memory or peer-to-peer DMA | Ordinary random-access memory (RAM) semantics or portable device connectivity | MMIO access rules, withdrawal of a mapping, and device-connectivity support | Measured locality wins and every required driver supports the path |

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

The byte-order conversion calls store multibyte descriptor fields with the
least-significant byte first, the little-endian order expected by this device.
`dma_wmb()` orders earlier descriptor stores before a later device-visible
ownership store. `WRITE_ONCE` asks the compiler to emit one store for the
ownership field, and `writel` writes the device's doorbell register. None of
these operations waits for completion.

For a streaming receive buffer, the direction is part of the mapping contract:

```c
dma_addr_t payload_dma =
    dma_map_single(dev, payload, payload_len, DMA_FROM_DEVICE);
if (dma_mapping_error(dev, payload_dma))
    return -ENOMEM;

/* Publish the descriptor, then wait for the device driver's real completion.
   Both steps are driver specific; the CPU must not synchronize or read the
   buffer until the driver has observed completed transfer status. */
publish_descriptor(dev, payload_dma, payload_len);
wait_for_device_completion(dev);

dma_sync_single_for_cpu(dev, payload_dma, payload_len, DMA_FROM_DEVICE);
consume_read_only(payload, payload_len);

/* Stop submissions and drain the device before this teardown. */
dma_unmap_single(dev, payload_dma, payload_len, DMA_FROM_DEVICE);
```

`DMA_FROM_DEVICE` means that the device writes system memory and the CPU later
reads it. `dma_addr_t` is a device-facing token; CPU code must not dereference
it. `dma_mapping_error` tests whether mapping failed, and `ENOMEM` is the Linux
error for an operation that could not obtain needed memory. The synchronization
call makes completed device writes visible to the CPU; it does not wait for the
device. Real drivers also publish the descriptor with the required ordering and
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
original entry count according to the Linux DMA application programming
interface (API) contract.

## Use costs as screens, not forecasts

First ask how many IOMMU translations cover the buffer. A mapping granule is
the smallest page-sized unit used by this IOMMU mapping. Let `B` be buffer
bytes, `G` the granule size, and `O` the starting offset within one granule,
where `0 <= O < G`. The `ceil` operation below rounds a fractional result up to
the next whole number:

```text
translations = ceil((O + B) / G)
```

The running buffer starts at aligned IOVA `0x4000_0000`, so `O = 0`. For 64
KiB and 4 KiB mappings, `ceil((0 + 64) / 4) = 16` translations. The same
length starting one byte after a granule boundary needs `ceil((1 + 64 KiB) /
4 KiB) = 17`. A pool of 1,024 aligned buffers can therefore require up to
`1,024 * 16 = 16,384` leaf translations before adjacent entries can legally be
combined, or coalesced. In plain language: alignment, physical layout, reuse,
and supported larger mappings determine translation pressure.

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
mappings, which stay live across many operations, also retain pages and a
longer-lived device aperture.

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

With an illustrative `E = 512` and `G = 4 KiB`, reach is `512 * 4 KiB = 2`
mebibytes (MiB). Random DMA across 64 MiB exceeds that example. Hardware also
decides how entries are divided among candidate slots, called associativity;
which old entry is evicted, called the replacement policy; and what intermediate
reads are cached during the hardware's page-table lookup, or page walk. The
equation identifies a workload dimension to vary, not a hardware fact.

## Checked model and generated code

The Rust model distinguishes CPU virtual addresses, physical addresses, and
IOVAs at the type level. It accepts a contiguous IOVA over noncontiguous
physical pages. It checks the inclusive DMA mask, the largest device address
allowed by the device's address width; the direction; the mapping epoch, a
generation counter used to reject stale work; ownership; completion identity;
and scatter counts. It rejects early unmap. It also demonstrates the IOMMU's
limit: a wrong offset inside the aperture translates successfully and needs a
payload canary, a known byte pattern that exposes corruption, or a higher-level
protocol check.

Run it with:

```bash
cargo run --locked --package iommu-dma-device-memory \
  --bin dma-contract-probe
cargo test --locked --package iommu-dma-device-memory
```

The linked `topic39_checked_translate` and `topic39_mask_allows` test functions
make the checked arithmetic visible to `objdump`, a binary-inspection tool.
That tool decodes executable bytes into a disassembly: a text listing of
machine instructions. A compiler can implement the comparisons with branches,
conditional selects, or another equivalent sequence. The retained disassembly
proves only that both functions remain in the CPU executable. DMA mappings,
IOMMU page-table walks, cache maintenance, and MMIO happen outside this
generated code.

Current mainline Linux source also illustrates an architecture boundary:
Linux's 64-bit Arm source (`arm64`) implements the DMA write barrier as `dmb
oshst`. `dmb` is the Arm data-memory-barrier instruction. In `oshst`, `osh`
selects the outer-shareable domain and `st` restricts the ordered access type
to stores. Linux's 64-bit x86 source (`x86`) implements the same API as a
compiler barrier, which stops compiler reordering without itself emitting a
CPU barrier instruction. These are source observations for current mainline,
not measurements of these two hosts and not evidence that every x86 device
path is coherent or every Arm device path is noncoherent.

## Failure modes and advice that breaks down

- **“Coherent means no barriers.”** Coherence supplies visibility, not the
  descriptor protocol's ordering.
- **“A barrier flushes caches.”** An ordering barrier and cache maintenance
  solve different problems.
- **“DMA mapping is address arithmetic.”** Mapping can install IOMMU entries,
  maintain caches, allocate bounce storage, validate device limits, and change
  ownership.
- **“The IOMMU makes the device safe.”** It blocks outside-aperture access, but
  not a bad offset inside an allowed mapping, broken device control software
  (firmware), devices that cannot be isolated separately, or removal of a
  mapping while work is still in flight.
- **“Pin everything for speed.”** Long-lived pins impede reclaim, which
  recovers idle pages, and migration, which moves pages. They also complicate
  writeback of dirty file data and enlarge the device's reachable lifetime.
- **“`mlock` makes memory DMA-safe.”** It neither creates an IOVA nor supplies
  the DMA API's cache and ownership contract.
- **“Virtual address equals IOVA, so the mapping works.”** SVA may make the
  numbers equal while CPU and device translation machinery remains separate.
- **“Completion means delivery.”** A DMA completion proves only the device or
  driver's documented local operation; application delivery and durability are
  separate. Durability means surviving the relevant failure, such as a restart.
- **“x86 is coherent and Arm is not.”** Coherence is a platform and device-path
  property, not a safe instruction-set-family rule.
- **“Larger page mappings are always faster.”** Alignment, physical
  contiguity, mapping support, pinning too much memory, and invalidation cost can
  reverse the result.
- **“Avoiding payload copies is always faster.”** Setup, synchronization,
  translation misses, invalidation, and lifetime pressure can cost more than
  copying a small buffer.
- Incorrect direction, size, device, or unmap count can expose stale bytes or
  let a dirty CPU cache line, the hardware block updated as one cache unit,
  overwrite device data.
- Device and CPU ownership in one cache line can corrupt unrelated fields on a
  noncoherent path.
- Stale ATS translations after page reuse can let a device write into the
  page's new owner.
- Many simultaneous PRI requests for missing translations can exhaust queues,
  amplify the slowest-request delays, or leave an accelerator runtime unable to
  make progress without bounded request handling.
- SWIOTLB pools can exhaust, and their size limits are kernel-version-sensitive.
- Base Address Register (BAR) memory is MMIO, not ordinary host RAM;
  plain pointer access and ordinary `memcpy` are not portable substitutes for
  input/output mappings and accessors.

## What the focused experiment establishes

The experiment is a deterministic CPU-side contract check. It runs in fresh
processes and inspects the linked address-checking functions on both required
Linux targets. It does not time or perform DMA because neither target exposes
an authorized, comparable device path to this unprivileged workload. A CPU-only
timing would measure process startup and arithmetic, not IOMMU performance.

The host runner records the exact source archive, Secure Shell (SSH) target
label and runtime-resolved hostname, architecture, CPU model, kernel, and
compiler and Rust toolchain versions. It records target features, meaning
compiler-reported instruction capabilities; build flags, meaning compiler
options; available CPUs; page size; kernel configuration; visible IOMMU groups,
meaning sets of devices that cannot be isolated separately; and generated
code. It runs generic builds, which use the compiler's portable target
defaults, and native builds, which may use features of that specific host.
Independent processes must produce identical expected output. See
[`rounds/01.md`](rounds/01.md) for the acceptance contract and
[`measurements/README.md`](measurements/README.md) for retained evidence.

### Retained two-host observation

This observation is historical. Both required hosts ran source commit
`2bb0d3e55efda225caeaeafbb285382824692b64` from one Git archive with Secure
Hash Algorithm 256-bit (SHA-256) digest, a content fingerprint,
`e5711fbfada35934afb39e4c3492f62a3066b731c05981d35c8dce0d7e31f614`.
All 16 fresh correctness processes per host matched that commit's expected
output, and every required package check, source-integrity check, retained
evidence record, and generated-code check passed. No timing was collected.

Later review commits changed the probe's receipt contract and the process
receipt schema, so this run does not validate the current branch head. Both
hosts must be rerun from the current head before any two-host observation
describes the published contract. See
[`measurements/README.md`](measurements/README.md) for which source commit each
retained binding covers.

The Arm target was
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, the 64-bit Arm architecture
(AArch64), Linux
`6.12.95-124.187.amzn2023.aarch64`, with 64 available CPUs. Its processor
identification was implementer `0x41`, part `0xd40`, variant `0x1`, revision
`0x1`. The generic compiler target enabled Arm Neon vector instructions. The
native C query reported the literal compiler feature string
`armv8.4-a+crypto+sha3+sm4+sve+rng+i8mm+bf16`: Arm version 8.4-A plus the
compiler's cryptography group, Secure Hash Algorithm 3 (`sha3`), SM4 block
cipher (`sm4`), Scalable Vector Extension (`sve`), random-number generation
(`rng`), 8-bit integer matrix multiplication (`i8mm`), and bfloat16 (`bf16`), a
16-bit floating-point format used in machine learning. Rust was 1.95.0 and the
GNU Compiler Collection (GCC) was 11.5.0.

The orchestrator supplied
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` as the resolution of SSH alias
`xxl`, and that host confirmed the same fully qualified hostname; the alias
resolution itself is a client-side observation retained outside the host
bundles. It reported x86-64, Linux
`6.12.95-124.187.amzn2023.x86_64`, 192 available CPUs, and Intel Xeon Platinum
8488C under Kernel-based Virtual Machine (KVM). The generic Rust target enabled
Streaming Single Instruction, Multiple Data Extensions (SSE) versions 1 and
2; the native C query reported compiler performance choices tuned for Sapphire
Rapids, with Advanced Vector Extensions 2 (AVX2), AVX-512 Foundation
(AVX-512F), and SSE version 4.2 enabled. Rust was 1.97.1 and GCC was 11.5.0.

Both kernels were configured with Peripheral Component Interconnect (PCI) ATS,
PRI, PASID, Virtual Function input/output (VFIO), IOMMU SVA, and SWIOTLB
support. The Arm configuration also enabled the Arm System Memory Management
Unit (SMMU) and SMMU version 3 (SMMUv3); the x86 configuration enabled Intel
and Advanced Micro Devices (AMD) IOMMU support. The guest-visible Linux system
filesystem (`sysfs`), which reports kernel objects and device relationships,
showed zero IOMMU class entries, zero groups, and zero PCI group links on both
hosts. That absence does not prove that the physical host lacks an IOMMU or
that a real device would bypass translation.

Generated code differed without changing the model result. An instruction
mnemonic is the assembler's short name for one machine operation. The Arm
executable called both test functions directly; its generic translator used
subtract-and-set-flags (`subs`), compare-and-branch-on-zero (`cbz`),
add-and-set-flags (`adds`), negate (`neg`), comparisons, and conditional
branches. On the measured x86-64 executable, the program loader resolves a
linker relocation by adding its chosen load base to a stored adjustment, called
the addend, and writing the resulting absolute target address into a slot. Code
reaches that slot with a load relative to the current instruction, then calls
the loaded address indirectly rather than naming it in the call instruction.
Its checks used move (`mov`), bitwise AND that updates flags without storing the
result (`test`), subtract (`sub`),
condition-code-to-byte (`setcc`), add (`add`), negate (`neg`), comparisons, and
conditional branches. These are observations of the two named executables, not
instruction-set-family performance claims.

## Practical selection guide

1. Use coherent allocation for small, long-lived control structures, and keep
   explicit descriptor barriers and ownership.
2. Use streaming mappings for bulk payloads, with exact direction,
   synchronization, completion, and matched unmap arguments.
3. Reuse mappings only after bounding pinned memory, device aperture, reset,
   invalidation, and teardown behavior.
4. Use an IOMMU when isolation or address flexibility matters; measure map,
   invalidation, and effects of the actively used translation range on the real
   device.
5. Accept SWIOTLB when required, but expose pool pressure and copy cost.
6. Choose SVA only when the complete device, every intervening bridge, the
   IOMMU, kernel, and driver support PASID, ATS, PRI, invalidation, reset, and a
   fixed limit on missing-translation requests.
7. Treat device-local and peer memory as specific to the driver, hardware
   interface, and physical device connectivity, not as ordinary process memory.

The central rule is simple: a device address proves nothing by itself. Prove
reachability, visibility, ordering, ownership, and completion separately, then
measure the complete path whose cost matters.

## Sources

Primary sources and version boundaries are collected in
[`references.md`](references.md).
