# Linux network receive and transmit paths

A network interface controller (NIC) moves packets between a host and a
network. Linux must also move packet descriptions through sockets, protocol
code, queues, drivers, and central processing units (CPUs). A fast link can
still lose packets or consume a core when one of those stages reaches its work
or queue limit. Tune the stage that is full; no single offload or buffer setting
fixes the whole path.

## Terms and stage map

- A socket buffer, written `skb` after Linux's `struct sk_buff`, is the kernel's
  packet metadata object. Packet bytes live in buffers associated with it.
- Direct memory access (DMA) lets a device read or write mapped memory without
  making a CPU copy each byte. A descriptor is a small record that gives the
  device a buffer address, length, and operation. Drivers still manage
  descriptors, ownership, and completion.
- New API (NAPI), now treated as a name in Linux, is the driver's event-polling
  mechanism. A device-notification interrupt schedules a poll. The poll
  processes receive packets up to a budget and handles transmit completions.
- Internet Protocol (IP) supplies network addressing. A flow is a traffic
  stream identified by fields such as source and destination addresses, ports,
  and transport protocol.
- Transmission Control Protocol (TCP) segmentation offload (TSO) lets a
  capable device split one large TCP packet description into wire packets.
- Generic segmentation offload (GSO) delays packet splitting. Linux can split
  in software when the device cannot. `UDP_SEGMENT` exposes this model to a
  User Datagram Protocol (UDP) socket.
- Generic receive offload (GRO) joins compatible received packets before later
  protocol or socket work. UDP applications must opt in to `UDP_GRO` and split
  the returned aggregate using its control message, which is metadata attached
  to the receive operation.
- A checksum is a packet-derived value used to detect corruption. Checksum
  offload asks a later software layer or the device to finish or validate it.
- Receive-side scaling (RSS) lets a multi-queue NIC hash flows to receive
  queues. The queue normally selects the interrupt and initial processing CPU.
- Receive packet steering (RPS) hashes packets in software and queues later
  protocol work to another CPU.
- Receive flow steering (RFS) extends RPS by considering the CPU on which the
  consuming application runs.
- Transmit packet steering (XPS) maps a CPU or receive queue to transmit queues.
  It changes queue placement, not packet count.

The physical-device path has these boundaries:

```text
transmit
application -> send call -> socket -> skb -> queueing discipline
            -> GSO/TSO and checksum contract -> driver transmit queue
            -> DMA descriptors -> NIC -> network

receive
network -> NIC receive queue -> DMA completion and interrupt -> NAPI poll
        -> skb -> GRO -> IP and TCP/UDP -> socket receive queue -> application
```

A queueing discipline is the Linux scheduler between protocol output and a
device queue. The diagram shows ownership boundaries, not a promise that every
driver or virtual device executes a separate step. Loopback traffic bypasses
the physical NIC, DMA, hardware queues, and wire.

## Choose a technique for one named problem

### Reduce submission and packet work

| Technique | Problem and simple mechanism | What it does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| One `send` per UDP datagram | Preserves the simplest one-call, one-message path | Per-call and per-packet cost | System-call cost grows with packet rate | Rate is low or portability and simple error handling dominate |
| `sendmmsg` | Submits an array of independent messages in one system call | It does not create one GSO packet or reduce per-datagram protocol work | A partial return requires the caller to resume at the first unsent message | Two or more independent datagrams are ready together |
| TSO | Carries one large TCP `skb` to a capable device, which creates wire segments | UDP, receive work, and per-wire transmission | Checksum and header capabilities must match the packet, including tunnels | TCP transmit packet work is limiting and device support is verified |
| GSO or `UDP_SEGMENT` | Represents two or more output segments in one software submission and splits late | Wire packet count and residual per-segment work remain | Unsupported features force a later software split; size and segment limits apply | The protocol and route accept late segmentation |
| GRO or `UDP_GRO` | Combines compatible receive packets into fewer later-stack units | Work before aggregation and wire packet count remain | Aggregation can change batching latency and UDP delivery shape | Later receive-stack or application delivery work is limiting |
| Checksum offload | Marks checksum state so a later software layer or device completes or validates it | Copies, segmentation, and queue imbalance | A capture before completion can display an unfinished checksum; tunnels add contracts | Profiling shows checksum work and the exact feature path supports it |

### Place work on CPUs and queues

| Technique | Problem and simple mechanism | What it does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| RSS | The NIC hashes flows across receive queues | One large flow still maps to one queue | Hash collisions, indirection, interrupt affinity, and queue count can create hot CPUs | Hardware queues exist and many flows can run in parallel |
| RPS | Software sends later receive processing to a selected CPU | It does not move the original device interrupt | Cross-CPU queueing and wakeups add cache and scheduling cost | RSS cannot place work well enough and spare CPUs exist |
| RFS | Software steers toward the consuming application's CPU | It does not make a moving application stable | Flow tables and application placement can become stale | Cache locality matters and application CPU placement is observable |
| XPS | Software selects a transmit queue from CPU or receive-queue maps | It does not reduce transmit work | Poor maps create queue contention or extra cache movement | Multi-queue transmit contention or locality is the measured limit |

### Absorb bursts or trade CPU for wakeup delay

| Technique | Problem and simple mechanism | What it does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| TCP socket autotuning | Linux grows TCP buffers within recorded policy limits as demand changes | UDP and a sustained service-rate deficit | Larger queues consume memory and can increase delay | A TCP window or transient burst, not CPU service rate, limits throughput |
| UDP socket buffer | A larger receive queue holds a longer burst before dropping | Incoming rate above drain rate forever | Linux socket accounting includes metadata and doubles `SO_RCVBUF` values set by applications | Measured bursts exceed the current queue for a bounded time |
| `listen` backlog | Holds completed connections until `accept` drains them | The separate half-open synchronize (SYN) handshake queue or a slow acceptor | Linux silently caps the request at `somaxconn` | Short completed-connection bursts exceed the accept rate |
| Busy polling | A socket read polls a supporting device queue for a bounded time | Protocol work, overload, or unsupported devices | It spends CPU and power while reducing some wakeup delay | Tail-latency evidence repays the reserved CPU budget |

## Cost model

Batching helps only the costs above the boundary where items join. Every wire
packet still pays costs below a transmit split and above a receive merge.

Let `N` be eventual wire segments and `D` payload bytes. Let `S` be exposed
cost per system call, `U` cost per software submission, `R` residual cost per
wire segment, and `Y` cost per byte. Let `B` be a `sendmmsg` batch size and `G`
the GSO segments represented by one submission:

```text
C_scalar   = N*S          + N*U          + N*R + D*Y
C_sendmmsg = ceil(N/B)*S  + N*U          + N*R + D*Y
C_GSO      = ceil(N/G)*S  + ceil(N/G)*U  + N*R + D*Y
```

The model supports one decision: batch where the removed fixed components are
large enough to repay batch construction and delay. It does not assume that
`S`, `U`, or `R` stay constant after the representation changes. TSO can move
segmentation work to a device; it does not make per-wire work zero.

For receive, let `W` be wire packets, `A` packets per GRO unit, `P` work paid
for each wire packet, and `Q` later-stack work paid for each delivered unit:

```text
C_without_GRO = W*P + W*Q         + D*Y
C_with_GRO    = W*P + ceil(W/A)*Q + D*Y
```

GRO helps when `Q` dominates. It cannot remove `W*P`, which occurs before the
merge boundary.

Three queue identities prevent common sizing mistakes:

```text
TCP bytes in flight = bits_per_second * round_trip_seconds / 8
completed backlog need = max(0, connection_arrival_rate - accept_rate) * burst_seconds
UDP fill time = receive_capacity_bytes / (incoming_rate - drain_rate)
```

Round-trip time is abbreviated RTT. The UDP identity applies only when the
incoming rate exceeds the drain rate. If that deficit persists, every finite
buffer fills. The backlog identity covers completed connections; Linux controls
the half-open TCP SYN queue separately with `tcp_max_syn_backlog`.

[`src/lib.rs`](src/lib.rs) implements these accounting identities. They become
conditional predictions only when each input comes from the same host,
workload, configuration, and run window.

## Evidence model

Keep five claims separate:

1. **Capability:** device features, driver version, queue count, and kernel
   documentation say which paths can exist.
2. **Configuration:** feature flags, interrupt affinity, RSS indirection, RPS,
   RFS, XPS, NAPI settings, socket options, and system controls say which paths
   are requested.
3. **Representation:** system-call traces, `skb` or tracepoint observations,
   UDP GRO control messages, and final-image inspection say which work units
   crossed an observed boundary.
4. **Outcome:** application loss and latency, CPU time, soft-network backlog,
   protocol counters, and driver counters say what happened in one window.
5. **Physical mechanism:** device and driver evidence is required to attribute
   work to hardware queues, DMA, interrupts, or a NIC offload.

Capability does not prove use. A feature marked `on` does not prove that a
given tunneled packet took it. A valid checksum at the receiver does not locate
where it was computed. One aggregate `recvmsg` proves the socket delivery shape,
not physical-NIC GRO.

## Initial two-host observations: pre-artifact loopback only

The 2026-08-05 scratch experiment used the 256-bit Secure Hash Algorithm
(SHA-256). The source digest was
`99760da70a028de782ed88b885839840b55817b93eb4fa3a70f4c7cc56411d1e` and
the schedule-driver digest was
`e2f81092fda07556083ea1412d0a693dc3eb62291d4aa3a07d4fc69533631da5`.
It sent 32 UDP datagrams of 1,200 bytes per round over Internet Protocol version
4 (IPv4) loopback. CPUs 0 and 1 ran the sender and receiver and were distinct
physical cores on both hosts.

| Observation | Arm host | `xxl` x86 host |
|---|---|---|
| Requested target | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | Secure Shell (SSH) alias `xxl` |
| Resolved host | same as requested | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| `uname` machine and kernel | `aarch64`, `6.12.94-123.192.amzn2023.aarch64` | `x86_64`, `6.12.94-123.180.amzn2023.x86_64` |
| CPU evidence | `c7g.16xlarge`, Arm Main ID Register `MIDR_EL1=0x411fd401`, 64 CPUs | `c7i.48xlarge`, Intel Xeon Platinum 8488C, 192 CPUs |
| Toolchain | GNU Compiler Collection (GCC) 11.5, GNU C Library 2.34, Rust 1.95.0 with LLVM 22.1.2 as its compiler backend | GCC 11.5, GNU C Library 2.34, Rust 1.97.1 with LLVM 22.1.6 as its compiler backend |
| Default-interface evidence | Elastic Network Adapter (ENA) driver 2.17.2g, 8 receive and 8 transmit queues | ENA 2.17.2g, 16 receive and 16 transmit queues |

Both scratch binaries used `-O3 -g -std=gnu11 -D_GNU_SOURCE -fno-lto -fno-omit-frame-pointer -Wall -Wextra -Werror -pthread`.
The build did not pass an architecture-specific `-march` option.

Both hosts reported loopback maximum transmission unit (MTU) 65,536 bytes,
actual send and receive socket buffers of 212,992 bytes, `somaxconn=4096`,
`tcp_max_syn_backlog=4096`, `netdev_budget=300`, and
`netdev_budget_usecs=20000`. TCP receive autotuning was enabled. Busy polling
was disabled. The default interface's RPS and XPS CPU masks and per-queue RFS
flow counts were zero. It also had `napi_defer_hard_irqs=0` and
`gro_flush_timeout=0`. `ethtool` was absent. These default-interface facts did
not participate in the loopback traffic.

Each treatment used six complete four-process `ABBA` or `BAAB` blocks, or 24
fresh processes. Every process ran 100 warmup and 1,000 measured rounds. A
four-block, 16-process A/A diagnostic ran the same `sendmmsg` mode under both
labels. Seed `260805` fixed the schedule. The estimate is a geometric elapsed
ratio from complete-block log contrasts. Brackets are two-sided 95% Student-t
intervals. They use the observed variation between the six blocks and cover
process variation in this run window only. Their independence and normality
assumptions were not established, so they are descriptive rather than
fleet-level guarantees.

| Candidate divided by scalar elapsed time | Arm | `xxl` x86 |
|---|---:|---:|
| `sendmmsg` | 0.93496 [0.92535, 0.94467] | 0.94604 [0.94101, 0.95110] |
| `UDP_SEGMENT` | 0.92049 [0.91086, 0.93022] | 0.90141 [0.89800, 0.90483] |
| A/A right divided by left | 0.99940 [0.99234, 1.00652] | 0.99956 [0.98744, 1.01183] |

Median elapsed nanoseconds per logical datagram were 3,092.35 scalar, 2,894.67
`sendmmsg`, and 2,845.48 `UDP_SEGMENT` on Arm. They were 2,901.25, 2,727.37,
and 2,619.51 on `xxl`. Lower is better. On both hosts, a separate
`UDP_GRO` semantic control delivered 32 logical datagrams through one
`recvmsg`, with one control message reporting 32 segments.

The linked images called `send` in the scalar loop, retried `sendmmsg` for a
batch, and called `sendmsg` once for `UDP_SEGMENT`. This observed code shape and
the program's call counts support syscall and socket-representation claims.
They do not show ENA use, DMA, hardware segmentation, RSS, physical receive
queues, or wire behavior. The relative timings are loopback observations on
these two exact hosts and binaries, not results for Arm, x86-64, ENA, or a
physical network family.

## Exact-source retained result

Commit `750e9ea8729063d118409f9f73537d76cb8ad392` passed source
identity, correctness, fixed-schedule, code-generation, workspace, and sealed
receipt gates on both required hosts. Each host retained 82 fixed fresh-process
attempts: eight four-process blocks for each primary comparison, four A/A
blocks, and two semantic controls. No failed process was replaced.

| Candidate divided by scalar elapsed time | Arm host | runtime-resolved `xxl` |
|---|---:|---:|
| `sendmmsg` | 0.92617 [0.91796, 0.93445] | 0.93385 [0.92971, 0.93800] |
| `UDP_SEGMENT` | 0.95531 [0.93810, 0.97283] | 0.78461 [0.77940, 0.78985] |
| A/A right divided by left | 0.99402 [0.96581, 1.02305] | 0.99251 [0.98023, 1.00494] |

Brackets are descriptive 95% Student-t intervals over complete-block log
contrasts. They cover observed process-block variation in one run window;
independence and normality remain assumptions. Program-reported setup,
including payload construction, was outside the contiguous measured
send/receive/acknowledgement interval.

The four-round `UDP_GRO` control preserved all 128 logical datagrams and their
checksum on each host. Four control messages each described at most 32
segments. Linked Arm and x86-64 images retained the scalar `send`,
partial-aware `sendmmsg`, and one-`sendmsg` `UDP_SEGMENT` paths.

See the [Arm record](measurements/750e9ea-arm.md), [`xxl`
record](measurements/750e9ea-xxl.md), [cross-host
comparison](measurements/750e9ea-comparison.md), and [sealed raw
bundles](measurements/raw/750e9ea). The timings remain loopback observations
for these hosts, binaries, payloads, and run windows. They do not establish
physical-NIC behavior or an Arm-versus-x86 mechanism.

## Exact-source measurement contract

A promoted record must:

- name the commit, archive the exact topic source, hash a sorted source
  manifest before and after the run, and hash the final binary;
- record requested and resolved hosts, architecture, CPU model, kernel,
  compiler, build flags, CPUs, driver, interface, queues, socket controls,
  steering maps, offload state, and available counters;
- run each timed treatment in a fresh process under the fixed, order-balanced
  schedule and retain every attempt;
- record logical datagrams, call counts, buffers, sender and receiver CPUs,
  elapsed and CPU time, payload checksum, expected checksum, and explicit
  payload-verification status;
- keep the UDP no-GRO and `UDP_GRO` controls separate from the timed estimator;
- inspect the linked image for the three intended send paths;
- validate the complete bundle and seal it with an evidence hash manifest.

See [round 1](rounds/01.md) for the design and [measurements](measurements/README.md)
for the retained record contract.

## Conventional advice that fails

- **“Enable every offload.”** Offloads move work across boundaries. Unsupported
  headers can force software fallback, while aggregation can change latency and
  observability. Measure the named path.
- **“More queues mean more throughput.”** RSS preserves flow ordering, so one
  large flow can remain on one queue. Extra queues can add cache movement and
  contention.
- **“Increase buffers until drops stop.”** A larger buffer absorbs a longer
  burst. It cannot repair a sustained arrival-rate deficit and can add queueing
  delay and memory use.
- **“Increase the listen backlog.”** The setting absorbs completed-connection
  bursts. It cannot raise the acceptor's service rate or size the half-open SYN
  queue.
- **“A bad checksum in a capture proves corruption.”** A capture before
  checksum completion can observe the partial offload contract. Compare capture
  point, receiver validation, and device counters.
- **“Busy polling is free latency.”** It exchanges CPU time and power for less
  wakeup delay, and it requires a supporting receive device.
- **“Loopback proves NIC offload speed.”** Loopback exercises socket and kernel
  paths but bypasses the physical device path.

## Practical selection guide

Start with packet rate, byte rate, loss, latency, CPU time by context, and queue
occupancy over the same interval. Use `sendmmsg` when call count is the limit;
use GSO or TSO when per-submission packet work is the limit; use GRO when later
receive work is the limit. Use RSS first for many flows, then add software
steering only when placement evidence justifies its cross-CPU cost. Size
buffers and backlogs from measured bursts, not from peak link rate. Reserve busy
polling for a measured latency target with an explicit CPU budget.

## Run the focused checks

Run the model checks from the repository root:

```bash
cargo test -p nic-datapath-cost-model --lib
cargo test -p nic-datapath-cost-model --doc
```

The socket experiment requires Linux headers and Linux UDP socket options. Run
it from the repository root on Linux:

```bash
cc -O3 -g -std=gnu11 -D_GNU_SOURCE -fno-lto \
  -fno-omit-frame-pointer -Wall -Wextra -Werror -pthread \
  topics/026-nic-datapath/experiment/udp_batch.c -o /tmp/udp-batch
/tmp/udp-batch scalar 1000 100
/tmp/udp-batch sendmmsg 1000 100
/tmp/udp-batch udp_segment 1000 100
/tmp/udp-batch udp_segment 1 0 --gro
```

Each command prints one machine-readable observation. A passing result reports
32 logical datagrams per round and matching payload verification. The scalar
mode completes one message per datagram. A complete `sendmmsg` batch and
`UDP_SEGMENT` each complete one send operation per 32-datagram round. Interrupted
or partial calls can add attempts, which the result records. The GRO control
reports one control message and a maximum of 32 segments. Exact timings will
vary; the semantic checks must not.

Use the fixed process schedule and exact-source host wrapper as described in
[round 1](rounds/01.md). Primary operating-system sources are in
[references](references.md).
