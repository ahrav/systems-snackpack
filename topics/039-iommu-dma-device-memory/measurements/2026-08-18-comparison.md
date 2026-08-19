# Topic 39 cross-host comparison

Date: 2026-08-18

## Comparison boundary

The two named hosts ran one exact source archive. This is a correctness and
code-generation comparison, not a timing comparison. It does not compare
64-bit Arm and 64-bit x86 (x86-64) device, direct memory access (DMA),
input-output memory management unit (IOMMU), cache maintenance (software
operations that make central processing unit (CPU) and device cached views
agree), or translation performance.
This comparison is historical. It binds source commit
`2bb0d3e55efda225caeaeafbb285382824692b64` and source archive Secure Hash
Algorithm 256-bit (SHA-256) digest
`e5711fbfada35934afb39e4c3492f62a3066b731c05981d35c8dce0d7e31f614`.
Later review commits changed the probe's receipt contract and the process
receipt schema, so these archives do not validate the current branch head;
both hosts must be rerun before a comparison describes the published contract.
Here, a digest is a content fingerprint. A generic build uses the Rust
compiler's default target features, meaning the instruction capabilities the
compiler may assume. A native build adds the build flag
`-C target-cpu=native`; a build flag is an option passed to the compiler, and
this one permits features reported by that host.

An IOMMU group is a kernel isolation set of devices that cannot be separated
by the IOMMU. The table records group visibility, not physical device
connectivity.

| Observation | Arm target | `xxl` target |
| --- | --- | --- |
| Resolved host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| Architecture | 64-bit Arm (AArch64) | 64-bit x86 (x86-64) |
| Kernel | `6.12.95-124.187.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| Central processing unit (CPU) evidence | Arm implementer `0x41`, part `0xd40`, variant `0x1`, revision `0x1`; 64 CPUs | Intel Xeon Platinum 8488C under Kernel-based Virtual Machine (KVM); 192 CPUs |
| Rust / GNU Compiler Collection (GCC) | 1.95.0 / 11.5.0 | 1.97.1 / 11.5.0 |
| Generic Rust target-feature names | Arm Advanced Single Instruction, Multiple Data, where one instruction operates on multiple lanes; commonly named Neon | Floating-point and vector register-state save and restore instructions (`FXSAVE` and `FXRSTOR`), plus Streaming Single Instruction, Multiple Data Extensions versions 1 and 2 |
| Native build | `-C target-cpu=native` | `-C target-cpu=native` |
| Visible Peripheral Component Interconnect (PCI) devices / IOMMU groups | 4 / 0 | 154 / 0 |
| Generic test-function linkage | Call instruction names the target directly | Loader writes its chosen executable load base plus a stored adjustment into a linker-created slot, producing an absolute target address; program-counter-relative code reaches that slot and loads the target into a register |
| Checked-translator instructions | Subtract/add and update flags (`subs`, `adds`); compare with zero and branch (`cbz`); negate (`neg`); comparisons and branches | Copy (`mov`); bitwise AND that updates flags without storing its result (`test`); subtract/add (`sub`, `add`); write a condition result (`setcc`); negate (`neg`); comparisons and branches |
| Fresh process results | 8 generic + 8 native pass | 8 generic + 8 native pass |
| Timing | Not reported | Not reported |

Both kernels expose configuration support for PCI Address Translation Services
(ATS), Page Request Interface (PRI), Process Address Space ID (PASID), Virtual
Function input/output (VFIO), IOMMU Shared Virtual Addressing (SVA), and the
software input-output translation lookaside buffer (SWIOTLB). The Arm
configuration also enables the Arm System Memory Management Unit version 3
(SMMUv3); the x86 configuration enables Intel and Advanced Micro Devices (AMD)
IOMMUs. Both guest-visible device directories expose zero IOMMU groups. That
shared observation cannot establish the physical device connectivity or active
DMA path.

## Measured, inferred, and untested

- **Measured:** exact host identity, kernel and toolchains, meaning compiler,
  linker, and build-tool versions; configuration and Linux system filesystem
  (`sysfs`) visibility; build flags; process output and exit status; hashes;
  proof that source files remained unchanged; linked symbols; linker relocation
  records or direct
  calls; and decoded executable machine instructions (disassembly).
- **Derived:** none beyond file counts and cryptographic digests.
- **Inferred:** the hardware or compiler mechanisms that motivated a particular
  generated instruction sequence; no timing was used to attribute a
  performance cause.
- **Untested:** real device access; active IOMMU translation; map creation,
  removal, or the discarding of stale cached translations; input-output
  translation lookaside buffer (IOTLB) misses, where a recent device
  translation is absent; ATS device-cache misses; PRI requests for missing
  translations; cache synchronization; SWIOTLB bounce copies; VFIO isolation;
  memory-mapped input/output (MMIO) register ordering; and device or peer
  memory.

The result supports the portable contract checks, meaning checks whose declared
requirements do not depend on one host's extra instructions, and demonstrates
different linked implementations on these machines. It does not support an
instruction-set architecture ranking.
