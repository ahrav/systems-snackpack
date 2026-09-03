# Primary references

- [Linux Scaling in the Networking Stack](https://docs.kernel.org/networking/scaling.html)
  defines RSS, RPS, RFS, accelerated RFS, XPS, CPU maps, flow tables, and the
  ordering rule used during RFS migration.
- [Linux NAPI documentation](https://docs.kernel.org/networking/napi.html)
  defines the interrupt and polling model, persistent NAPI configuration, and
  related coalescing and busy-poll interfaces.
- [Linux SMP IRQ affinity](https://docs.kernel.org/core-api/irq/irq-affinity.html)
  defines `/proc/irq/<IRQ>/smp_affinity` and `smp_affinity_list`.
- [Linux networking sysctls](https://docs.kernel.org/admin-guide/sysctl/net.html)
  defines host networking controls that include receive processing budgets and
  backlog limits. Defaults can vary by kernel version and configuration.
- [Linux v6.12 `net/core/dev.c`](https://github.com/torvalds/linux/blob/v6.12/net/core/dev.c)
  is pinned implementation evidence for receive backlog selection, RPS CPU
  choice, inter-processor signaling, NAPI receive processing, and transmit
  queue selection. Vendor kernels may backport later behavior.
- [Linux v6.12 `net/ipv4/udp.c`](https://github.com/torvalds/linux/blob/v6.12/net/ipv4/udp.c)
  is pinned implementation evidence for the different incoming CPU and NAPI
  updates on connected UDP sockets and a wildcard-bound shared server socket.
  This is why the experiment uses connected client sockets for per-flow
  placement observations and labels the server values as socket-wide only.
- [Amazon EC2 ENA queue guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ena-queues.html)
  describes queue availability and queue-count considerations for ENA-backed
  instances.
- [Amazon EC2 network latency guidance](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ena-improve-network-latency-linux.html)
  describes ENA interrupt moderation and CPU placement guidance. Treat it as
  provider guidance, not as evidence that a given host uses a setting.

## Source boundary

The Linux documentation pages track current upstream documentation. The source
link is pinned to v6.12 because both required experiment hosts run Amazon Linux
vendor 6.12 kernels. A matching major and minor version does not prove matching
source. Distro and provider kernels backport changes.

Documentation and source establish mechanism and interface contracts. Host
receipts establish only what the scripts observed on the named host. When an
inspection tool such as `ethtool` is missing, the evidence must say so instead
of reconstructing an RSS key, hash-field set, or indirection table from packet
placement.

Useful claims and their evidence class:

| Claim | Evidence |
|---|---|
| RSS selects a hardware RX queue before the host stack | Linux scaling documentation |
| RPS can enqueue receive work to another CPU backlog | Linux scaling documentation and pinned v6.12 source |
| RFS delays migration until old queued work drains | Linux scaling documentation and pinned v6.12 source |
| XPS maps CPUs or RX queues to TX queues | Linux scaling documentation and pinned v6.12 source |
| A named host exposed a queue count or zero steering map | Exact-run host receipt |
| Positive NAPI fanout with RPS and RFS disabled is consistent with hardware fanout | Inference from exact-run observations |
| A particular RSS key or indirection entry caused a flow placement | Requires direct device inspection; not established when `ethtool` is absent |
