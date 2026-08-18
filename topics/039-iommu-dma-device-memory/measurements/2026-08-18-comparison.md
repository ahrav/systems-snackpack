# Topic 39 cross-host comparison

Date: 2026-08-18

## Comparison boundary

The two named hosts ran one exact source archive. This is a correctness and
code-generation comparison, not a timing comparison. It does not compare Arm
and x86-64 device, DMA, IOMMU, cache-maintenance, or translation performance.
The current comparison binds final-reviewed source commit
`f43f0fe3766933e9f17ce4d0c7590345238dbbae` and source archive SHA-256
`84f24c2ff91e38898d353481dd50b0effa66e25790eea433c736787e7a250802`.

| Observation | Arm target | `xxl` target |
| --- | --- | --- |
| Resolved host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| Architecture | AArch64 | x86-64 |
| Kernel | `6.12.95-124.187.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| CPU evidence | Arm implementer `0x41`, part `0xd40`, variant `0x1`, revision `0x1`; 64 CPUs | Intel Xeon Platinum 8488C under KVM; 192 CPUs |
| Rust / GCC | 1.95.0 / 11.5.0 | 1.97.1 / 11.5.0 |
| Generic Rust features | Neon | FXSR, SSE, SSE2 |
| Native build | `-C target-cpu=native` | `-C target-cpu=native` |
| Visible PCI devices / IOMMU groups | 4 / 0 | 154 / 0 |
| Generic hook linkage | Direct symbol calls | Relocation-slot-bound indirect calls |
| Checked-translator instructions | `subs`, `cbz`, comparisons, `adds`, `neg`, branches | `mov`, `test`, `sub`, `setcc`, comparisons, `add`, `neg`, branches |
| Fresh process results | 8 generic + 8 native pass | 8 generic + 8 native pass |
| Timing | Not reported | Not reported |

Both kernels expose config support for PCI ATS, PRI, PASID, VFIO, IOMMU SVA,
and SWIOTLB. The Arm config also enables Arm SMMUv3; the x86 config enables
Intel and AMD IOMMUs. Both guest-visible namespaces expose zero IOMMU groups.
That shared observation cannot establish the physical topology or active DMA
path.

## Measured, inferred, and untested

- **Measured:** exact host identity, kernel and toolchains, config and sysfs
  visibility, build flags, process output and exit status, hashes, source
  immutability, linked symbols, relocations or direct calls, and disassembly.
- **Derived:** none beyond file counts and cryptographic digests.
- **Inferred:** the hardware or compiler mechanisms that motivated a particular
  lowering; no timing was used to attribute a performance cause.
- **Untested:** real device access, IOMMU activation, map/unmap or invalidation
  cost, IOTLB and ATS misses, cache synchronization, PRI faults, SWIOTLB copy
  paths, VFIO containment, MMIO ordering, and device or peer memory.

The result supports the portable contract checks and demonstrates different
linked implementations on these machines. It does not support an ISA ranking.
