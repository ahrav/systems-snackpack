# Packet steering and interrupt architecture: RSS, RPS, RFS, and XPS

Packet steering is a placement problem. It decides which queue and CPU pay for
receive or transmit work. A useful design names the stage first. RSS chooses a
hardware receive queue. IRQ affinity constrains the CPUs eligible to handle an
interrupt vector; the driver's queue, vector, and NAPI mapping determines what
that vector represents, and polling can run elsewhere. RPS can move later
receive processing to another CPU. RFS adds application locality to that
software choice. XPS chooses a transmit queue.

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
  -> driver-defined interrupt vector on an eligible affinity CPU
  -> driver NAPI poll and receive softirq work, possibly on another CPU
  -> optional RPS or RFS choice
  -> optional target-CPU backlog and IPI
  -> protocol processing and socket queue
  -> application thread
```

A simplified transmit path is:

```text
application CPU or remembered RX queue
  -> XPS map and cached netdevice TX queue choice
  -> qdisc and driver
  -> hardware TX queue when the device has one
  -> NIC
```

The diagram marks control points, not a promise that every driver uses one NAPI
instance per hardware queue or one interrupt vector per queue. Drivers can
share or combine those objects, and IRQ affinity does not by itself identify the
polling CPU.

## Four steering mechanisms

| Mechanism | Decision point | Input | Result | Main cost or limit |
|---|---|---|---|---|
| RSS | NIC receive path | Packet hash and indirection table | Hardware RX queue | One flow normally stays on one queue; device support and table shape matter |
| RPS | Host receive path after the driver hands up a packet | Packet hash and an RX queue CPU mask | CPU for later receive processing | Hashing, backlog enqueue, cache transfer, and sometimes an IPI |
| RFS | RPS CPU selection | Flow hash plus the CPU where the application last consumed or sent on the socket | Receive processing closer to the application | Flow-table lookup, table aliases, migration rules, and workload churn |
| XPS | Host transmit path | Sending CPU or RX queue and a TX queue map | Netdevice TX queue | Mapping and queue locality can help, but XPS does not move receive work |

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
flow table records the desired CPU where the application most recently consumed
or sent on a flow. A per-RX-queue flow-table slot records the CPU currently
processing the hashed flow and a backlog-tail marker. An ordinary matched-entry
desired-CPU change waits for the recorded old backlog tail to drain before
changing targets. That guard aims to preserve order for that transition, not to
provide a global ordering guarantee across table-alias fallback, offline,
hardware-filter, or cross-queue paths. An unset or offline old target is an
explicit exception.

Software RFS needs both `net.core.rps_sock_flow_entries` and per-queue
`rps_flow_cnt` entries. The v6.12 scaling guide recommends 32,768 global
entries. Current upstream guidance, added later, suggests 65,536 and larger
tables for large servers. Both are empirical starting points, not sizing laws;
per-queue sizing must reflect active flows on that queue.
Accelerated RFS is build-gated by `CONFIG_RFS_ACCEL`. After an allowed
desired-CPU change, Linux attempts programming only when the skb has a recorded
RX queue, a CPU-to-RX-queue map exists, n-tuple filtering is enabled, the mapped
RX queue differs, and that target queue has an RFS flow table. Only a
non-negative driver `ndo_rx_flow_steer` result records a filter. The packet that
triggers programming has already arrived and still takes the software path. A
configured table alone does not prove that a later hardware filter was
installed or that a queue transition preserves order.

### XPS

Transmit Packet Steering maps the sending CPU, or an RX queue in an
RX-queue-based configuration, to eligible TX queues. The goal is to keep the
producer, queue metadata, completions, and related receive work close together.
In the generic `netdev_pick_tx` path, Linux may cache the chosen queue only on a
full socket with a destination cache, so an eligible long-lived flow does not
necessarily re-evaluate the map for every packet. A driver's `ndo_select_queue`
policy bypasses that generic path, and a driver can initialize XPS, so neither
an empty assumed default nor generic socket caching is universal.

That cache rule is versioned. Current upstream can expire an eligible
full-socket cache using `net.core.txq_reselection_ms`, which defaults to 1,000
milliseconds; pinned v6.12 does not have that time-based path. Selection can
also be reconsidered when the cache is invalid or `skb->ooo_okay` permits a
move.

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

Here `packets_per_interrupt` is an effective ratio measured from aligned packet
and NIC-interrupt deltas. It is not the NAPI budget. Shared vectors, TX
completions, repolling, busy polling, and adaptive moderation can invalidate the
simple ratio.

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
changes which CPUs may handle the interrupt vector. It can move the initial
hard-IRQ work, but driver-defined queue, vector, and NAPI relationships mean it
does not by itself prove where polling runs. Enabling RPS leaves the descriptor
and initial driver work in place and moves a later stage. Measure both stages
before choosing one.

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

Use one stage-local work unit throughout. Wire packets, RX descriptors, and
post-GRO skbs are not interchangeable.

`A[i,q]` is one when flow `i` maps to queue `q`. For a hypothetical queue with
one dedicated 3.0-billion-cycle/s service budget and 700 cycles of receive work
per packet, the model gives:

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

The model predicts that the hot single-server stage cannot drain its offered
load. If one CPU services several queues, their cycle demand must be summed
before dividing by that CPU's measured usable budget. Nominal GHz is not a
measured budget under DVFS, SMT, memory stalls, or competing work. More idle
workers do not fix the modeled hot stage.

### RPS CPU cost

RPS keeps the driver and selection work on the source path and moves later
backlog and upper-stack work. A stage model is:

```text
rho_RPS_source[s] = (lambda_attempt[s] * (driver_cycles[s] + select_cycles[s])
                     + sum_t(lambda_attempt[s,t] * enqueue_cycles[s,t])
                     + sum_t(RPS_IPI_send_rate[s,t] * IPI_send_cycles[s,t]))
                    / source_cycles_per_second[s]
rho_RPS_target[t] = (lambda_delivered[t] * (dequeue_cycles[t] + upper_cycles[t])
                     + RPS_IPI_rate[t] * IPI_handle_cycles[t])
                    / target_cycles_per_second[t]
```

Here `lambda_attempt[s] = sum_t(lambda_attempt[s,t])` and
`lambda_delivered[t] = sum_s(lambda_delivered[s,t])`. Each pairwise attempted
minus delivered rate exposes backlog or flow-limit loss instead of charging
dropped skbs as target work. All
lambda values are skbs per second at the RPS handoff. The target IPI rate is
the sum of source-to-target IPI event rates. Each `driver_cycles`,
`select_cycles`, `enqueue_cycles`, `dequeue_cycles`, and `upper_cycles` term is
cycles per corresponding skb. Each IPI rate is events per second, each IPI cost
is cycles per event, and each source or target budget is usable cycles per
second. The two rho terms are RPS-path components, not total CPU utilization.
Add separately measured IRQ and unrelated work. Measure RPS IPI rate: same-CPU
backlog scheduling sends no IPI, while remote notifications can batch. Enqueue,
dequeue, and upper-stack costs can vary by LLC or NUMA distance. RPS can increase
total CPU while still lowering the hottest stage. It cannot recover packets
already dropped in the ring or driver before its handoff point. If one physical
CPU is both source and target, sum both demands and every queue it services
before comparing with its budget.

For a coarse total-work sensitivity check, let the rate be skbs/s at the RPS
handoff. A GRO skb is not necessarily one wire packet:

```text
cores = skbs_per_second
      * (hash_cycles
         + enqueue_cycles
         + remote_probability
           * (remote_cache_cycles
              + IPI_cycles / measured_remote_skbs_per_IPI))
      / usable_cycles_per_core_second
```

For a hypothetical sensitivity check, assume 3.2 million skbs per second at this
handoff, 40 hash cycles, 80 enqueue cycles, a remote probability of one, 60
remote-cache cycles, 900 IPI cycles, 32 remote-enqueued skbs per remote IPI, and
3.0 billion usable cycles per core-second:

```text
cycles_per_skb = 40 + 80 + 1 * (60 + 900 / 32) = 208.125
cores = 3,200,000 * 208.125 / 3,000,000,000 = 0.222
```

That 0.222-core result is a modeled incremental total-work fraction. It does
not show which source or target stage is hottest. The cost can be worthwhile
when measured stage pressure and the end-to-end objective improve. It is waste
when RSS already placed work well.

### RFS locality and churn

Against an RPS-only baseline with the same backlog and IPI path, model the net
RFS cost per skb at the lookup as:

```text
net_cycles_per_skb = lookup_cycles_per_skb
           + target_transition_cycles / skbs_between_transitions
           - locality_fraction_improvement * locality_cycles_saved
```

For a hypothetical stable flow with a 30-cycle lookup, 2,000-cycle target
transition, 10,000 skbs between transitions, a locality fraction improvement of
one, and 80 locality cycles saved per skb that gains locality:

```text
net_cycles_per_skb = 30 + 2,000 / 10,000 - 80 = -49.8 cycles/skb
```

At a hypothetical measured software-RFS input rate of 3.2 million skbs per
second, not Orchid's wire-packet rate, that is a modeled saving of:

```text
3,200,000 * 49.8 / 3,000,000,000 = 0.0531 core
```

For a hypothetical churning flow whose target changes every 100 skbs, suppose
the measured average locality term
`locality_fraction_improvement * locality_cycles_saved` is 20 cycles per skb:

```text
net_cycles_per_skb = 30 + 2,000 / 100 - 20 = 30 cycles/skb
```

An RSS-only comparison must also add the RPS backlog and IPI costs. RFS now adds
modeled work in this RPS-relative example. Table aliases add another risk. For `F` active flows
hashed independently and uniformly into `T` entries, the chance that a selected
flow shares its entry is:

```text
P(alias) = 1 - (1 - 1/T)^(F - 1)
```

For 10,000 flows and 65,536 entries, the approximation is 0.141. With eight
equal RX queues, an independent equal-allocation plan would set 8,192 entries
per queue; the global and per-queue tables are configured separately. For a
per-queue table, use that queue's `F_q` and `T_q`; dividing entries evenly
preserves the ratio only if flow load is also balanced. This probability is a
planning model for approximate locality-table sharing. It does not predict
packet loss or reordering and is not a kernel guarantee.

### XPS locality

Suppose matched-rate measurement at a hypothetical queue-selection input rate of
3.2 million skbs per second shows an unplaced TX path spends 120 in-scope cycles
per skb across selection, queue lock, and completion or cache effects, while a
placed path spends 40. This skb rate is an explicit model input, not Orchid's
wire-packet rate; a GSO skb is not one wire packet. At that common reference
rate, the observed-average delta implies:

```text
cores_saved = 3,200,000 * (120 - 40) / 3,000,000,000
            = 0.0853
```

The arithmetic states the break-even question. Contention is nonlinear and TX
queue choice can be socket-cached, so only queue counters, qdisc/requeues,
completion IRQs, CPU cost, and end-to-end behavior can establish the saving.
If completed skb rates differ, let `lambda_base` and `lambda_xps` be the
baseline and candidate queue-selection skb rates. Compare total demand as
`(lambda_base * cycles_base - lambda_xps * cycles_xps) / cycles_per_core_second`
instead of multiplying both costs by one arm's rate.

Run the checked planning substitutions from this topic directory:

```bash
cargo test
cargo run --example steering_costs
```

## Focused Linux experiment

The probe keeps every client socket alive, gives each flow a distinct source
port, and validates every request and echo payload. It records
`SO_INCOMING_NAPI_ID` and `SO_INCOMING_CPU` separately. On the pinned v6.12
receive path these are socket snapshots, not metadata attached to the exact
datagram returned to userspace, and valid NAPI-ID reporting depends on
`CONFIG_NET_RX_BUSY_POLL`. Connected UDP updates both fields continuously;
unconnected UDP marks NAPI once and does not continuously update incoming CPU.
A stable peer does not count as stable NAPI or CPU placement unless each field
is stable on its own.

The equal-total comparison uses:

```text
one-flow case:   1 flow   * 256 request/echo pairs = 256 pairs
many-flow case: 128 flows *   2 request/echo pairs = 256 pairs
```

Fresh processes follow balanced `ABBA` and `BAAB` blocks. Identical-case A/A
blocks expose label, order, and host noise. Both routes must use a non-loopback
interface. The host runner records the route, interface,
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
with multi-NAPI ingress while classic generic RPS and software RFS were
unconfigured on the inspected ingress queues. It does not
prove RSS was the unique cause, match queues one-to-one with NAPI instances, or
reveal the RSS hash fields or indirection table because `ethtool` was absent on
both hosts.

The shared server socket reported one incoming NAPI identifier and incoming
CPU `-1`. That is a result for this socket topology and API observation. It is
not evidence that RFS would choose one CPU. IRQ deltas were also affected by
ambient traffic and moderation, so they are retained as diagnostics rather
than packet counts. An earlier DNS probe routed through loopback and was
discarded as non-loopback datapath evidence.

## Exact-source accepted observation

The final campaign built source commit
`d20ee11bbb3c2cef2e98a69194d287783c5e29d6` from one path-limited archive on
both hosts. It ran 24 fresh periods in both directions and passed independent
validation of both 149-file sealed receipts.

Every connected client flow kept a stable peer, known incoming CPU, and
positive stable NAPI identifier. Each 128-flow run observed eight CPUs and
eight NAPI identifiers on the Arm host, and 16 of each on `xxl`. The hosts
exposed eight and 16 RX queues respectively. On the relevant `eth0` queues, all
observed classic generic RPS, software-RFS, and XPS maps remained zero,
including the global and per-queue RFS state. These observations support
multi-NAPI ingress and show that the CPU snapshots cannot be attributed to
classic generic RPS or software RFS on the inspected ingress queues. They do
not prove RSS was the unique steering mechanism,
establish a queue-to-NAPI mapping, or expose the RSS hash or indirection table.
See the [accepted comparison](measurements/2026-09-04-comparison.md).

## Evidence boundary

Keep these evidence classes separate:

- **Sourced mechanism:** Linux documentation and pinned v6.12 source explain
  where RSS-adjacent IRQ handling, RPS, RFS, and XPS act.
- **Direct observation:** Host files, route output, probe output, digests, and
  counters describe the exact host and run that produced them.
- **Calculation:** Rates, utilization, CPU cost, and alias estimates follow
  from stated formulas and inputs.
- **Inference:** Positive connected-socket NAPI-ID fanout supports multi-NAPI
  ingress for the observed flows. The readable `eth0` queue maps plus global
  RFS state were zero, which excludes classic generic RPS and software RFS only
  on those inspected ingress queues. It is not direct observation of RSS, an
  RSS table, or CPU fanout. Dedicated filters, RSS contexts, driver topology, or
  other earlier steering can produce similar observations.

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
- RFS can lose when workers migrate often, observed table sharing drives churn
  or poor locality, or the application does not keep stable CPU ownership.
- Accelerated RFS needs kernel, queue-map, target-table, driver, and n-tuple
  support. One missing gate leaves hardware steering unavailable.
- XPS can spread TX queue work while receive placement remains broken.
- Interrupt moderation can lower interrupt rate while adding wait time.
- `/proc/interrupts` includes ambient traffic, and moderation breaks any
  one-interrupt-per-packet assumption.
- `/proc/net/softnet_stat` column 2 covers backlog drops, not every physical NIC
  receive drop. Column 3 marks a budget/time exit; it is not loss and does not
  alone prove work remained.
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
