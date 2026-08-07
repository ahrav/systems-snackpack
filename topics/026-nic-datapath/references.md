# Primary references

The measured hosts ran Linux 6.12.94. Current kernel documentation defines the
interfaces and invariants below, but its stated defaults can differ by kernel,
distribution, driver, and device. Host probes establish the measured settings.

- [Linux `struct sk_buff`](https://docs.kernel.org/networking/skbuff.html)
  defines the main packet metadata structure and its associated data buffers.
- [Linux dynamic DMA mapping guide](https://docs.kernel.org/core-api/dma-api-howto.html)
  defines CPU, physical, and device address spaces; network-buffer mappings;
  and descriptor ownership requirements for direct memory access (DMA).
- [Linux segmentation offloads](https://docs.kernel.org/networking/segmentation-offloads.html)
  defines TCP segmentation offload (TSO), UDP segmentation offload, Generic
  Segmentation Offload (GSO), Generic Receive Offload (GRO), feature flags, and
  tunnel header boundaries.
- [Linux checksum offloads](https://docs.kernel.org/networking/checksum-offloads.html)
  defines `CHECKSUM_PARTIAL`, software fallback, receive checksum states, and
  the relationship between GSO and checksum completion.
- [Linux network scaling](https://docs.kernel.org/networking/scaling.html)
  defines Receive-Side Scaling (RSS), Receive Packet Steering (RPS), Receive
  Flow Steering (RFS), accelerated RFS, and Transmit Packet Steering (XPS).
- [Linux NAPI](https://docs.kernel.org/networking/napi.html) defines receive
  polling budgets, interrupt masking, completion, software interrupt handling,
  and busy-poll controls.
- [Linux IP system controls](https://docs.kernel.org/networking/ip-sysctl.html)
  defines TCP buffer autotuning, `somaxconn`, `tcp_max_syn_backlog`, syncookies,
  and protocol-specific queue controls. The observed values, not the page's
  defaults, define a retained run.
- [`udp(7)`](https://man7.org/linux/man-pages/man7/udp.7.html) defines UDP
  message semantics, `UDP_SEGMENT`, `UDP_GRO`, error handling, and buffer
  controls for Linux applications.
- [`socket(7)`](https://man7.org/linux/man-pages/man7/socket.7.html) defines
  `SO_RCVBUF`, `SO_SNDBUF`, Linux's doubled accounting values, `SO_REUSEPORT`,
  and `SO_BUSY_POLL`.
- [`listen(2)`](https://man7.org/linux/man-pages/man2/listen.2.html) distinguishes
  the completed connection queue from the incomplete TCP SYN queue and states
  the `somaxconn` cap.
- [`sendmmsg(2)`](https://man7.org/linux/man-pages/man2/sendmmsg.2.html) defines
  multi-message transmission, partial completion, and the per-call vector
  limit. [`recvmmsg(2)`](https://man7.org/linux/man-pages/man2/recvmmsg.2.html)
  defines the matching receive batching contract and timeout caveat.
- [Linux network statistics](https://docs.kernel.org/networking/statistics.html)
  defines standard interface-statistics sources and explains why driver
  statistics do not share one universal schema.
- [Linux protocol counters](https://docs.kernel.org/networking/snmp_counter.html)
  defines selected IP, TCP, UDP, and extended counter meanings, including
  listen and receive-buffer failures.
- [Linux UDP GSO self-test at v7.1](https://github.com/torvalds/linux/blob/v7.1/tools/testing/selftests/net/udpgso.c)
  is a primary implementation example for `UDP_SEGMENT` and UDP GRO semantics.
- [Linux 6.13 ENA driver guide](https://docs.kernel.org/6.13/networking/device_drivers/ethernet/amazon/ena.html)
  describes the Elastic Network Adapter (ENA) driver queues, interrupt model,
  NAPI integration, and offload capability. It is adjacent documentation, not
  proof of behavior for the measured 6.12.94 kernels and ENA 2.17.2g driver.
- [AWS ENA network performance metrics](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-network-performance-ena.html)
  defines instance allowance counters. Those counters identify allowance
  events; they do not locate a Linux software bottleneck by themselves.
