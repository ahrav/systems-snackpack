# Primary references

- [NVM Express specifications](https://nvmexpress.org/specifications/) indexes
  the ratified NVMe Base and transport specifications.
- [NVMe Base Specification 2.4](https://nvmexpress.org/wp-content/uploads/NVM-Express-Base-Specification-Revision-2.4-Ratified-2026.07.31.pdf)
  defines submission queues, completion queues, command identifiers, phase
  tags, and controller queue behavior.
- [NVMe over PCIe Transport Specification 1.4](https://nvmexpress.org/wp-content/uploads/NVM-Express-NVMe-over-PCIe-Transport-Specification-Revision-1.4-Ratified-2026.07.31.pdf)
  defines host-memory queues, doorbells, interrupts, and PCI Express transport
  behavior.
- [Linux multiqueue block input/output queueing](https://docs.kernel.org/block/blk-mq.html)
  defines software staging queues, hardware dispatch queues, tags, and the
  optional scheduling layer.
- [Linux block-layer statistics](https://docs.kernel.org/admin-guide/iostats.html)
  defines the device counters retained around each experiment process.
- [Linux `io_submit(2)`](https://man7.org/linux/man-pages/man2/io_submit.2.html)
  defines native asynchronous request submission.
- [Linux `io_getevents(2)`](https://man7.org/linux/man-pages/man2/io_getevents.2.html)
  defines native asynchronous completion collection.
- [Linux `open(2)`](https://man7.org/linux/man-pages/man2/open.2.html) scopes the
  alignment and cache-bypass contract of `O_DIRECT`.
- [Linux NVMe PCI driver source](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/drivers/nvme/host/pci.c?h=v7.2.2)
  is implementation evidence for current queue, tag, interrupt, and polling
  behavior. The experiment hosts run older Amazon Linux 6.12 kernels, so this
  source is not used as proof of their exact implementation.
- [Linux blk-mq source](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/block/blk-mq.c?h=v7.2.2)
  is current implementation evidence for request allocation, dispatch, and
  completion. It is not substituted for host observation.

Sources were checked on 2026-09-01. The current upstream source links identify
Linux v7.2.2. Both required hosts run vendor 6.12 kernels. Specifications and
source explain mechanisms; the retained receipts describe only the observed
hosts and workload.
