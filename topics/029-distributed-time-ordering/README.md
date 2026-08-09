# Distributed time and ordering

A wall-clock timestamp can place a causally later update before its predecessor.
Sorting those timestamps gives a deterministic result, but not a causal proof or
an agreed order. This topic separates local duration, physical-time estimates,
causal order, concurrency detection, and protocol agreement.

The executable probe injects one backward physical-clock reading. It does not
change host time or benchmark local comparison instructions.

## One running example

Replica A records `paid` at wall time `1000 ms`, then sends that update to
replica B. B receives it and records `packed` while its wall clock reads
`900 ms`.

```text
A: paid, wall=1000 ----message----> B: packed, wall=900
```

`paid` *happens before* `packed`: B could not pack the order before learning
about payment. Last-write-wins (LWW), which retains the larger wall timestamp,
selects the causal predecessor `paid`.

Two independent updates need a different answer. Vectors `[1,0]` and `[0,1]`
are incomparable, so neither update includes the other's history. That means
they are concurrent in the message graph, not that they ran at the same
physical instant.

## The contracts differ

- A wall clock estimates civil time. Its offset and rate can change.
- A monotonic clock measures local elapsed time. It is not comparable across
  hosts.
- A Lamport clock gives causal predecessors smaller scalar values.
- A vector clock detects causal dominance and concurrency in its modeled
  participant set.
- A Hybrid Logical Clock (HLC) preserves the Lamport condition while retaining
  a physical-time-like component.
- A consensus log establishes an agreed sequence. A sortable timestamp alone
  does not establish agreement or finality.

## Technique boundaries

| Technique | Solves | Does not solve | Main catch |
| --- | --- | --- | --- |
| Wall time plus LWW | Compact physical-time label and deterministic winner | Causality, concurrency, agreement | Clock error can reverse a causal chain |
| Lamport clock | One-way causal precedence with constant metadata | Physical time or general concurrency detection | Unequal values can be causal or concurrent |
| Vector clock | Causal order and concurrency | Winner selection or total order | Metadata and comparison grow with participants |
| HLC | One-way causality plus physical-time affinity | Concurrency detection or external consistency by itself | Future timestamps, restart, and counter overflow need policy |
| Bounded uncertainty plus commit protocol | Real-time-respecting transaction order | Free ordering from a point timestamp | Bound enforcement and commit wait |
| Consensus log | One durable order inside one group | Civil time or cross-group order | Quorum, persistence, and recovery cost |

## Cost model

Let real event times be `T_A < T_B`, true separation be
`delta = T_B - T_A`, clock errors be `e_A` and `e_B`, and reported wall times
be `P_i = T_i + e_i`. Wall-time order reverses when:

```text
P_B < P_A
e_A - e_B > delta
```

If the two readings have valid symmetric error bounds `u_A` and `u_B`, physical
time proves A before B only when:

```text
P_A + u_A < P_B - u_B
```

Overlapping intervals mean physical time cannot determine the order. They do
not prove concurrency because a message can still establish happens-before.

Let `R` be the number of stable replica dimensions and `b` the bytes per
counter. A dense vector carries about `R * b` counter bytes and takes work
proportional to `R` to merge or compare. Wall, Lamport, and HLC timestamps use
constant fields independent of `R`. Constant metadata does not include the
cost of persistence, validation, message delivery, uncertainty wait, or
agreement.

For a symmetric physical-time interval with half-width `epsilon`, choosing the
upper endpoint and waiting until it is definitely past starts with an interval
gap near `2 * epsilon`. If `p` seconds of useful protocol work overlap that
gap, an idealized residual wait is:

```text
wait = max(0, 2 * epsilon - p)
```

This is a decision model, not a universal latency prediction.

## Failure boundaries

- Coordinated Universal Time (UTC) standardizes a time scale; it does not
  synchronize hosts.
- Linux `CLOCK_MONOTONIC` is nondecreasing but frequency-adjusted and excludes
  suspend. `CLOCK_BOOTTIME` includes suspend.
- Network Time Protocol (NTP) and Precision Time Protocol (PTP) improve
  physical-time estimates. Neither creates causal order.
- Adding a node identifier to a Lamport or HLC timestamp creates a deterministic
  comparator, not total-order broadcast.
- Lost counters, reused identities, or silent wrap can make logical time move
  behind durable history.
- A remote timestamp far in the future can push HLC state forward. Production
  receivers need an offset admission policy.
- Vector dimensions cover only the causal channels that propagate them.
- Conflict detection does not define the business merge for `cancelled` versus
  `shipped`.

## Run locally

From the repository root:

```bash
cargo test --locked --package distributed-time-ordering
cargo build --locked --release --package distributed-time-ordering \
  --bin ordering-probe

target/release/ordering-probe --self-check

python3 topics/029-distributed-time-ordering/experiment/run_processes.py \
  target/release/ordering-probe \
  /tmp/topic29-local

python3 topics/029-distributed-time-ordering/experiment/validate_receipts.py \
  /tmp/topic29-local \
  target/release/ordering-probe
```

The output directory must not exist. The local command launches eight fresh
processes without replacement. The retained Linux run repeats those eight
processes for both generic and native builds. Every process must produce the
same deterministic receipt. The validator recomputes every output and digest.

The expected state changes are:

```text
wall LWW: paid@1000 beats packed@900 -> causal predecessor selected
Lamport: paid=1, packed=2 -> causal order preserved
vector: [1,0] < [1,1]; [1,0] || [0,1]
HLC: paid=(1000,0), packed=(1000,1) with B wall=900
interval: [990,1010] and [1000,1020] overlap -> physical order unknown
self-check: PASS
```

No timing metric is reported. Timing these pure compare and maximum operations
would not estimate network, metadata, persistence, wait, or quorum cost.

Use [`rounds/01.md`](rounds/01.md) for the experiment contract,
[`measurements/README.md`](measurements/README.md) for exact-source promotion,
and [`references.md`](references.md) for the claim-to-source map.
