# Packet steering and interrupt architecture: RSS, RPS, RFS, and XPS

Packet steering is a placement problem. It decides which queue and CPU pay for
receive or transmit work. A useful design names the stage first. RSS chooses a
hardware receive queue. IRQ affinity chooses where that queue interrupts. RPS
can move later receive processing to another CPU. RFS adds application locality
to that software choice. XPS chooses a transmit queue.

Those mechanisms are related, but they are not interchangeable. A queue count,
an interrupt count, a NAPI identifier, a CPU identifier, and a socket owner are
observations from different stages. Treating them as one thing hides the real
bottleneck.

This crate keeps the planning arithmetic executable. Its Linux experiment uses
byte-checked UDP request and echo pairs across the required Arm and x86-64
hosts. The experiment checks flow stability and records queue, interrupt, NAPI,
CPU, route, source, and binary evidence. It does not infer an RSS key or
indirection table when the host cannot expose one.

## The path to keep in mind

A simplified receive path is:

```text
packet on the wire
  -> NIC receive hash and RSS indirection
  -> hardware RX queue and descriptor ring
  -> queue interrupt on its affinity CPU
  -> driver NAPI poll and receive softirq work
  -> optional RPS or RFS choice
  -> optional target-CPU backlog and IPI
  -> protocol processing and socket queue
  -> application thread
```

A simplified transmit path is:

```text
application CPU or remembered RX queue
  -> XPS map and cached TX queue choice
  -> qdisc and driver
  -> hardware TX queue
  -> NIC
```

The diagram marks control points, not a promise that every driver uses one NAPI
instance per hardware queue or one interrupt vector per queue. Drivers can
share or combine those objects.

## Four steering mechanisms

| Mechanism | Decision point | Input | Result | Main cost or limit |
|---|---|---|---|---|
| RSS | NIC receive path | Packet hash and indirection table | Hardware RX queue | One flow normally stays on one queue; device support and table shape matter |
| RPS | Host receive path after the driver hands up a packet | Packet hash and an RX queue CPU mask | CPU for later receive processing | Hashing, backlog enqueue, cache transfer, and sometimes an IPI |
| RFS | RPS CPU selection | Flow hash plus the CPU where the application last consumed or sent on the socket | Receive processing closer to the application | Flow-table lookup, table aliases, migration rules, and workload churn |
| XPS | Host transmit path | Sending CPU or RX queue and a TX queue map | Hardware TX queue | Mapping and queue locality can help, but XPS does not move receive work |

### RSS and IRQ affinity

Receive Side Scaling runs before host software sees the packet. The NIC hashes
selected packet fields, indexes an indirection table, and places the packet on
an RX queue. The queue's interrupt vector is then delivered according to IRQ
affinity. NAPI polling often keeps a burst of later packets out of the hard-IRQ
path, so interrupt deltas are not packet counts.

RSS spreads flows, not packets within one ordinary flow. Adding queues does not
split one hot tuple. It can also add cache and coordination cost when the host
has more queues than useful receive CPUs.

`ethtool -l` and `ethtool -x` are the usual ways to inspect channel counts,
the RSS indirection table, and the hash key. If those interfaces are missing,
queue fanout and positive NAPI identifiers can support a narrower observation,
but they do not reveal the exact hash fields, key, or table.

### RPS

Receive Packet Steering runs in software. For each enabled RX queue, the
`rps_cpus` mask names CPUs that may receive later protocol work. A remote choice
uses the target CPU's backlog and may send an inter-processor interrupt.

RPS does not move the hardware descriptor, queue interrupt, or initial driver
poll. It acts after those costs have already happened. On a multiqueue NIC with
well-placed RSS, RPS can duplicate work and harm locality. It is more useful
when hardware fanout is weak or absent, such as a single-queue device, `veth`,
or `tun` path.

### RFS

Receive Flow Steering extends RPS with application locality. A global socket
flow table records the CPU where the application most recently consumed or
sent on a flow. A per-RX-queue flow table records the CPU currently processing
that flow. Linux delays a CPU migration until packets already queued to the old
CPU have drained. That ordering guard matters because a fast migration that
reorders packets is not a win.

Software RFS needs both `net.core.rps_sock_flow_entries` and per-queue
`rps_flow_cnt` entries. The Linux scaling guide recommends 65,536 global
entries as a starting point and dividing them among the active RX queues.
Accelerated RFS has three extra gates: `CONFIG_RFS_ACCEL`, a driver that
implements `ndo_rx_flow_steer`, and enabled n-tuple filtering. A configured
table alone does not prove that hardware filters were installed.

### XPS

Transmit Packet Steering maps the sending CPU, or an RX queue in an
RX-queue-based configuration, to eligible TX queues. The goal is to keep the
producer, queue metadata, completions, and related receive work close together.
Linux caches a TX queue choice in the socket, so a long-lived flow does not
necessarily re-evaluate the map for every packet.

XPS cannot repair an overloaded receive queue. It also cannot prove that a
particular completion CPU is local without queue, IRQ, and driver evidence.

## Interrupts, NAPI, and moderation

The interrupt path sets the first host CPU that notices receive work. NAPI then
polls packets in batches with interrupts masked. Moderation and polling trade
interrupt cost against delay.

A small planning model is:

```text
interrupts_per_second ~= packets_per_second / packets_per_interrupt
CPU_seconds_per_second = interrupts_per_second * seconds_per_interrupt
```

At 3.2 million packets per second, 32 packets per interrupt, and 0.8
microseconds of fixed interrupt work:

```text
interrupts_per_second = 3,200,000 / 32 = 100,000
CPU_seconds_per_second = 100,000 * 0.0000008 = 0.08
```

If the average batch falls to eight packets, the same assumptions yield
400,000 interrupts per second and 0.32 CPU-second per second. These are
planning substitutions. Real interrupt batches depend on the device, driver,
moderation settings, load shape, and ambient traffic.

IRQ affinity and RPS solve different placement problems. Moving IRQ affinity
changes where the queue interrupt and initial poll run. Enabling RPS leaves
that work in place and moves a later stage. Measure both stages before choosing
one.

## Running example: Orchid

Orchid has eight RX queues, eight TX queues, 16 worker threads, and 64 flows.
Each flow offers 50,000 packets per second, so total offered load is:

```text
lambda_total = 64 * 50,000 = 3,200,000 packets/second
```

### Queue capacity and skew

For queue `q`:

```text
lambda_q = sum(A[i,q] * lambda_i)
mu_q = cycles_per_second / cycles_per_packet
rho_q = lambda_q / mu_q
```

`A[i,q]` is one when flow `i` maps to queue `q`. Assume a 3.0 GHz CPU budget and
700 cycles of receive work per packet. One queue can then serve about:

```text
mu_q = 3,000,000,000 / 700 = 4,285,714 packets/second
```

With eight equal flows per queue:

```text
lambda_q = 8 * 50,000 = 400,000 packets/second
rho_q = 400,000 / 4,285,714 = 0.0933
```

Now replace one ordinary flow with a 5 million packet-per-second elephant. The
queue still receives seven ordinary flows:

```text
lambda_hot = 5,000,000 + 7 * 50,000 = 5,350,000 packets/second
rho_hot = 5,350,000 / 4,285,714 = 1.2483
```

The system has spare aggregate CPU, but the hot queue is unstable. More idle
workers do not fix that queue. The design must split traffic before the hot
stage, change the flow shape, or raise service capacity there.

### RPS CPU cost

An idealized RPS cost model is:

```text
cores = packets_per_second
      * (hash_cycles
         + enqueue_cycles
         + remote_probability
           * (remote_cache_cycles + IPI_cycles / IPI_batch))
      / usable_cycles_per_core_second
```

Substitute 3.2 million packets per second, 40 hash cycles, 80 enqueue cycles, a
remote probability of one, 60 remote-cache cycles, 900 IPI cycles, an IPI batch
of 32, and 3.0 billion usable cycles per core-second:

```text
cycles_per_packet = 40 + 80 + 1 * (60 + 900 / 32) = 208.125
cores = 3,200,000 * 208.125 / 3,000,000,000 = 0.222
```

That cost can be worthwhile when RPS removes a queue bottleneck. It is waste
when RSS already placed work well.

### RFS locality and churn

Model the net RFS cost per packet as:

```text
net_cycles = lookup_cycles
           + migration_cycles / packets_between_migrations
           - locality_cycles_saved
```

For a stable flow with a 30-cycle lookup, 2,000-cycle migration, 10,000 packets
between migrations, and 80 locality cycles saved:

```text
net_cycles = 30 + 2,000 / 10,000 - 80 = -49.8 cycles/packet
```

At Orchid's rate, that is a modeled saving of:

```text
3,200,000 * 49.8 / 3,000,000,000 = 0.0531 core
```

For a churning flow that moves every 100 packets and saves only 20 locality
cycles:

```text
net_cycles = 30 + 2,000 / 100 - 20 = 30 cycles/packet
```

RFS now adds work. Table aliases add another risk. For `F` active flows hashed
uniformly into `T` entries, the chance that a selected flow shares its entry is
approximately:

```text
P(alias) = 1 - (1 - 1/T)^(F - 1)
```

For 10,000 flows and 65,536 entries, the approximation is 0.141. With eight
equal RX queues, a 65,536-entry global table implies 8,192 per-queue entries.
This probability model is a planning aid, not a kernel guarantee.

### XPS locality

Suppose an unplaced TX path spends 120 extra cycles per packet on queue lock and
cache transfer, while a well-placed path spends 40. The modeled saving is:

```text
cores_saved = 3,200,000 * (120 - 40) / 3,000,000,000
            = 0.0853
```

The arithmetic states the break-even question. Only queue counters, CPU cost,
and end-to-end behavior can show whether the assumed saving exists.

Run the checked planning substitutions from this topic directory:

```bash
cargo test
cargo run --example steering_costs
```

## Focused Linux experiment

The probe keeps every client socket alive, gives each flow a distinct source
port, and validates every request and echo payload. It records
`SO_INCOMING_NAPI_ID` and `SO_INCOMING_CPU` separately. A stable peer does not
count as stable NAPI or CPU placement unless each field is stable on its own.

The equal-total comparison uses:

```text
one-flow case:   1 flow   * 256 request/echo pairs = 256 pairs
many-flow case: 128 flows *   2 request/echo pairs = 256 pairs
```

Fresh processes follow balanced `ABBA` and `BAAB` blocks. Identical-case A/A
blocks expose label, order, and host noise. Both routes must use a physical
interface rather than loopback. The host runner records the route, interface,
queue maps, RPS and RFS state, XPS state, interrupts, softnet counters, source
digest, binary digest, and probe output.

The low-level probe interface is:

```text
udp_steering_probe <server|client> <IPv4> <port> <flows> \
  <packets-per-flow> <source-sha256>
```

The host wrapper provides `prepare`, `snapshot`, and `seal` operations. The
controller runs the probe in both directions. See both script interfaces before
running them:

```bash
experiment/run_host.sh
experiment/run_cross_host.sh
```

Only a run built from the final path-limited Git archive qualifies as retained
publication evidence. A scratch copy, even one with matching source text, is
exploration.

## Preliminary observation, not retained evidence

The pre-commit cross-host check ran over `eth0` in both directions. It kept 128
simultaneously open UDP client sockets and completed two byte-validated
request/echo pairs per flow. All 128 flows kept a stable peer, incoming CPU,
and incoming NAPI identifier in each direction.

The Arm client observed eight positive NAPI identifiers and the x86-64 client
observed 16. The hosts exposed eight and 16 RX queues respectively. Every
per-queue `rps_cpus`, `rps_flow_cnt`, `xps_cpus`, and `xps_rxqs` value read zero,
and `net.core.rps_sock_flow_entries` read zero. That combination is consistent
with receive fanout before software RPS or RFS. It does not prove the RSS hash
fields or indirection table because `ethtool` was absent on both hosts.

The shared server socket reported one incoming NAPI identifier and incoming
CPU `-1`. That is a result for this socket topology and API observation. It is
not evidence that RFS would choose one CPU. IRQ deltas were also affected by
ambient traffic and moderation, so they are retained as diagnostics rather
than packet counts. An earlier DNS probe routed through loopback and was
discarded as physical-path evidence.

## Evidence boundary

Keep these evidence classes separate:

- **Sourced mechanism:** Linux documentation and pinned v6.12 source explain
  where RSS-adjacent IRQ handling, RPS, RFS, and XPS act.
- **Direct observation:** Host files, route output, probe output, digests, and
  counters describe the exact host and run that produced them.
- **Calculation:** Rates, utilization, CPU cost, and alias estimates follow
  from stated formulas and inputs.
- **Inference:** Positive NAPI fanout with software steering disabled is
  consistent with hardware receive-queue fanout. It is not direct observation
  of an RSS table.

The experiment does not isolate CPU architecture, infer the NIC's selected
hash fields, prove accelerated RFS support, or turn an interrupt delta into a
packet count. It does not show that more queues are always better. It also does
not show throughput or latency improvement because the focused probe is a
correctness and placement experiment, not a calibrated load test.

## Failure checklist

- One hot flow normally stays on one RSS queue. More worker threads do not split
  it.
- An indirection table can be legal and still skew the workload's actual flow
  set.
- IRQ affinity can concentrate initial poll work even when later RPS work looks
  balanced.
- RPS can move work onto a remote cache domain and add backlog or IPI cost.
- RFS can lose when workers migrate often, tables alias, or the application
  does not keep stable CPU ownership.
- Accelerated RFS needs kernel, driver, and n-tuple support. One missing gate
  leaves hardware steering unavailable.
- XPS can spread TX queue work while receive placement remains broken.
- Interrupt moderation can lower interrupt rate while adding wait time.
- `/proc/interrupts` includes ambient traffic, and moderation breaks any
  one-interrupt-per-packet assumption.
- `/proc/net/softnet_stat` column 2 covers backlog drops, not every physical NIC
  receive drop. Column 3 is deferred work, not loss.
- A loopback route bypasses the physical queue and IRQ path.
- A nonzero configuration file proves configuration, not execution or benefit.

## Selection rule

Start at the first overloaded stage. If hardware queues are skewed, inspect RSS
and IRQ affinity. If hardware fanout is adequate but a single software receive
CPU is overloaded on a path that can use RPS, test RPS and account for backlog,
IPI, and cache cost. Add RFS only when application ownership is stable enough
to repay table and migration work. Use XPS for a transmit-queue locality or
contention problem. After any change, require the attributed stage counter and
the end-to-end metric to improve without moving the bottleneck to an adjacent
stage.

See [the measurement contract](measurements/README.md), [the first
round](rounds/01.md), and [the source ledger](references.md).
