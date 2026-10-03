# Primary sources

Accessed 2026-10-01. Rolling documentation is not a deployed-kernel guarantee.

- [Linux AF_XDP](https://docs.kernel.org/networking/af_xdp.html): FILL/RX/TX/COMPLETION ownership, queue matching, copy-mode negotiation, need_wakeup, and current invalid-descriptor completion behavior. The configuration sections qualify some older overview text.
- [Linux v6.12 AF_XDP](https://raw.githubusercontent.com/torvalds/linux/v6.12/Documentation/networking/af_xdp.rst): pinned reference for aligned chunk aliases and multi-buffer descriptor batches. Do not infer newer invalid-TX reclaim behavior for v6.12.
- [libxdp xsk.h](https://github.com/xdp-project/xdp-tools/blob/main/headers/xdp/xsk.h): acquire/release ring helpers. The model does not implement these atomics.
- [Linux NAPI](https://docs.kernel.org/networking/napi.html#busy-polling): socket and epoll busy polling, NAPI-ID grouping, CPU tradeoffs. Verify availability on the actual kernel.
- [DPDK 24.11 Ethernet device guide](https://doc.dpdk.org/guides-24.11/prog_guide/ethdev/ethdev.html): queue ownership, burst processing, and driver-dependent capability exceptions.
- [DPDK 24.11 Ethernet API](https://doc.dpdk.org/api-24.11/rte__ethdev_8h.html): rte_eth_tx_burst return and buffer lifetime contracts.
- [DPDK v24.11 Linux driver guide](https://raw.githubusercontent.com/DPDK/dpdk/v24.11/doc/guides/linux_gsg/linux_drivers.rst): bifurcated drivers and driver binding requirements.

The cost arithmetic and finite ledger are this artifact's models, not performance
results from these sources. AF_XDP and DPDK remain distinct implementations;
accepted-prefix handling is a DPDK-inspired abstraction, not an AF_XDP ring API.
