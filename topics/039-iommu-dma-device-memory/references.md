# Primary sources and version boundaries

The retained targets run Amazon Linux 6.12 kernels. Current documentation and
mainline source can describe later behavior. Recheck a deployed kernel, device,
firmware, and topology, meaning how devices connect and share isolation, before
turning these contracts into operational claims.

## Linux direct memory access (DMA) and device input/output (I/O)

- [Linux Dynamic DMA Mapping Guide](https://docs.kernel.org/core-api/dma-api-howto.html)
  defines central processing unit (CPU), physical, and DMA address spaces;
  coherent and streaming mappings; direction; barriers; masks; map-error
  handling; and the original versus mapped scatter/gather counts.
- [Linux DMA application programming interface (API) reference](https://docs.kernel.org/core-api/dma-api.html)
  defines synchronization, mapping-size queries, resource mappings, attributes,
  and provider-facing API details.
- [Linux device input/output documentation](https://docs.kernel.org/driver-api/device-io.html)
  defines memory-mapped input/output (MMIO), `__iomem` (the Linux annotation
  used by the `sparse` static-analysis tool for pointers into memory-mapped
  input/output space), input/output accessors, and posted-access considerations.
- [Linux input/output ordering documentation](https://docs.kernel.org/driver-api/io_ordering.html)
  explains why a device read can be required to flush posted writes before a
  critical section ends.
- [Current mainline 64-bit Arm (`arm64`) barrier definitions](https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/barrier.h),
  [64-bit x86 (`x86`) barrier definitions](https://github.com/torvalds/linux/blob/master/arch/x86/include/asm/barrier.h),
  and [architecture-independent wrappers](https://github.com/torvalds/linux/blob/master/include/asm-generic/barrier.h)
  show how Linux maps, or lowers, the portable DMA barrier API to architecture
  operations. These links track mainline and are not the measured hosts' exact
  kernel source.

## Input-output memory management unit (IOMMU) translation, isolation, and bounce buffering

- [Linux IOMMU file descriptor (IOMMUFD) userspace API](https://docs.kernel.org/userspace-api/iommufd.html)
  defines I/O address spaces, device attachment, mappings, alignment, fault
  objects, and versioned capabilities.
- [Linux Virtual Function I/O (VFIO) documentation](https://docs.kernel.org/driver-api/vfio.html)
  defines IOMMU groups as the minimum ownership unit and describes device and
  userspace mapping lifecycles.
- [Linux software input-output translation lookaside buffer (SWIOTLB) documentation](https://docs.kernel.org/core-api/swiotlb.html)
  defines software bounce buffering, current slot and segment behavior, and
  confidential-virtual-machine use cases. Constants are version-sensitive.
- [Linux IOMMU kernel parameters](https://docs.kernel.org/admin-guide/kernel-parameters.html)
  document strict and deferred invalidation controls. A documented boot option
  is not a recommendation to change a production host.
- [Arm System Memory Management Unit version 3 architecture](https://documentation-service.arm.com/static/69ae9767e79f9a1d642aab2d)
  specifies stream identifier (`StreamID`) and substream identifier
  (`SubstreamID`) translation-context selection.
- [Intel Virtualization Technology for Directed I/O architecture](https://www.intel.com/content/www/us/en/content-details/919688/intel-virtualization-technology-for-directed-i-o-architecture-specification.html)
  specifies Intel IOMMU translation, remapping, and invalidation mechanisms.

## Pinning, shared address spaces, and device memory

- [Linux `pin_user_pages` documentation](https://docs.kernel.org/core-api/pin_user_pages.html)
  defines `FOLL_PIN`, the internal get-user-pages flag that selects page-pin
  semantics, plus separate pinned-page accounting, long-term cases, and
  restrictions.
- [Linux x86 shared virtual addressing](https://docs.kernel.org/arch/x86/sva.html)
  defines Shared Virtual Addressing (SVA), Process Address Space ID (PASID),
  Address Translation Services (ATS), and Page Request Interface (PRI) on the
  supported x86 path.
- [Linux memory-management-unit notifier documentation](https://docs.kernel.org/mm/mmu_notifier.html)
  defines invalidation ordering needed when secondary address translations can
  outlive a CPU page-table change.
- [Peripheral Component Interconnect Special Interest Group (PCI-SIG) ATS specification page](https://pcisig.com/PCIExpress/Specs/Base/AddressTranslationServices_1.0)
  and [PASID Engineering Change Notice (ECN)](https://pcisig.com/PCIExpress/ECN/Base/ProcessAddressSpaceID)
  are the PCI Express primary specifications for cached translations and
  process-address-space tags.
- [Linux PCI peer-to-peer DMA](https://docs.kernel.org/driver-api/pci/p2pdma.html)
  defines the memory provider, consuming device, coordinating component
  (orchestrator), and topology constraints for direct device-to-device
  transfers.
- [Linux DMA buffer sharing](https://docs.kernel.org/driver-api/dma-buf.html)
  defines cross-device buffer sharing, attachments, mappings, and explicit or
  implicit synchronization boundaries.
- [Linux pagemap documentation](https://docs.kernel.org/admin-guide/mm/pagemap.html)
  explains that page frame numbers are zeroed for unprivileged readers. A
  physical frame number would not establish an input-output virtual address
  (IOVA) in any case.
