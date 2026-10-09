# Primary references

Read on 2026-10-09. The experiment records deployed kernel and toolchain versions.

- [fallocate(2)](https://man7.org/linux/man-pages/man2/fallocate.2.html): allocation, keep-size, zero range, hole punching, and support failures.
- [lseek(2)](https://man7.org/linux/man-pages/man2/lseek.2.html): weak logical hole/data reporting contract.
- [stat(2)](https://man7.org/linux/man-pages/man2/stat.2.html): file length and allocated 512-byte units on Linux.
- [FIEMAP](https://docs.kernel.org/filesystems/fiemap.html): mapping flags, snapshot limits, mounted-device access prohibition.
- [Zoned storage overview](https://zonedstorage.io/docs/introduction/zoned-storage): size versus capacity, sequential write constraints, Zone Append.
- [Zoned Linux interface](https://zonedstorage.io/docs/linux/zbd-api): units and device resource limits.
- [zonefs](https://docs.kernel.org/filesystems/zonefs.html): sequential-file rules and failure reconciliation.

Do not infer NAND placement from FIEMAP, device requests from buffered application
writes, or zoned throughput from the arithmetic model.
