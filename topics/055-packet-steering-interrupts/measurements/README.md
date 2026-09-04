# Measurement records

This directory holds compact records from exact-source runs on the required Arm
and x86-64 Linux hosts. Full receipts stay in the retained external evidence
bundle.

Each accepted host record must bind:

- the pushed source commit, topic path, path-limited archive SHA-256, and archive
  member list;
- target label, runtime-resolved hostname, architecture, kernel, CPU model,
  virtualization, compiler, compile flags, source digest, and binary digest;
- the peer address, route, source address, interface, and proof that the tested
  path did not use loopback;
- driver identity and version, online CPU set, NUMA topology, RX and TX queue
  counts, and any available RSS channel, key, hash-field, and indirection data;
- every `rps_cpus`, `rps_flow_cnt`, `xps_cpus`, and `xps_rxqs` value, plus
  `net.core.rps_sock_flow_entries`;
- IRQ affinity and `/proc/interrupts` snapshots, with interrupt deltas labeled
  as diagnostics rather than packet counts;
- `/proc/net/softnet_stat` snapshots with column count and version-aware field
  interpretation;
- the one-flow and 128-flow equal-total cases, balanced block order, and an A/A
  control;
- every client's source endpoint, peer endpoint, byte-integrity result,
  incoming NAPI identifier, and incoming CPU observation;
- a check that all client sockets remained open together and all source ports
  were distinct;
- peer, NAPI, and CPU stability calculated as separate fields rather than one
  combined pass condition;
- the source and runner equality checks on both hosts;
- the independent receipt validator result and the sealed external bundle's
  SHA-256 and manifest digest.

The equal-total cases are:

```text
1 flow   * 256 request/echo pairs = 256 pairs
128 flows *   2 request/echo pairs = 256 pairs
```

A compact comparison must keep four evidence classes separate:

- **Observed:** Exact host files, commands, routes, probe records, and digests.
- **Calculated:** Counts, deltas, stability summaries, and planning formulas
  derived from recorded inputs.
- **Sourced:** Linux and provider contracts cited in `references.md`.
- **Inferred:** The narrow mechanism explanation consistent with both the
  observations and the sourced contracts.

The records must state these limits:

- A positive NAPI identifier does not reveal the RSS hash fields, key, or
  indirection table.
- Multiple NAPI identifiers do not by themselves prove multiple CPUs, RSS as
  the unique cause, or a one-to-one queue/NAPI mapping.
- On the pinned v6.12 UDP path, incoming CPU and NAPI ID are socket snapshots
  updated before enqueue rather than metadata bound to the exact datagram read;
  valid NAPI-ID reporting also depends on build-time
  `CONFIG_NET_RX_BUSY_POLL`.
- A queue count does not prove that the experiment used every queue.
- A stable flow does not prove that a specific hardware hash caused its
  placement.
- Zero RPS and RFS files exclude classic generic RPS and software RFS on the
  inspected ingress queues. They do not exclude redirects or another device or
  driver path.
  Zero XPS map files establish only those map families are empty; they do not
  exclude every driver TX-queue policy. None establishes a universal default or
  a guarantee about another host.
- A shared server socket's incoming CPU or NAPI observation describes that
  socket topology only.
- IRQ deltas include moderation and ambient traffic. They are not packet
  counts.
- `/proc/net/softnet_stat` backlog drops do not cover every physical receive
  path drop. Its rows aggregate devices per CPU, `processed` is receive-stack
  passes, and `time_squeeze` does not by itself prove ksoftirqd ran.
- The focused probe checks correctness and placement. It is not a throughput or
  latency benchmark and does not isolate architecture effects.
- A missing `ethtool` result is missing capability evidence. It must not be
  filled in by inference.

Pre-commit exploration is not publication evidence. Only receipts built from
the final path-limited Git archive qualify.

## Accepted campaign

The accepted `2026-09-04` campaign is summarized in the [Arm
record](2026-09-04-arm.md), [`xxl` record](2026-09-04-xxl.md), and [cross-host
comparison](2026-09-04-comparison.md). Compact validator outputs and retained
receipt locators are under [`raw/2026-09-04-d20ee11`](raw/2026-09-04-d20ee11/README.md).
