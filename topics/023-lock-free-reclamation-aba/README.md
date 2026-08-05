# Lock-free reclamation and ABA

A compare-and-swap validates one bit pattern at one instant. A complete
lock-free design separately proves linearization, node lifetime, logical
identity, and end-to-end progress.

## State boundary

Unlinking stops new traversals from acquiring a node. Retiring records that old
operations can still hold it. A reclamation protocol makes it reclaimable only
after those operations can no longer dereference it. Reuse can then assign the
same storage to a different logical object.

Hazard pointers publish individual protected objects. Epoch-based reclamation
protects every object reachable during a pinned operation. Linux RCU waits for
pre-existing readers in the selected RCU flavor. A generation tag distinguishes
head histories but does not protect the tagged node's lifetime.

## Cost boundary

For `P` participants, `h` hazard slots per participant, and retire batch `R`, a
hazard scan examines `P * h` publications and amortizes that work across `R`
retirements. An epoch or RCU backlog scales with the retirement rate times the
oldest relevant reader delay. An unbounded pinned interval therefore creates an
unbounded retained-memory term even when the structure continues completing
operations.

A `v`-bit generation rejects a stale head only while fewer than `2^v` relevant
head changes can occur during the snapshot lifetime. The fixture uses a 32-bit
generation and does not claim a non-wrap proof for an unbounded execution.

## Focused experiment

The binary forces `A -> B -> empty -> A` with fixed integer-index nodes. The raw
head accepts a stale `A -> B` update and makes removed B reachable. Packing the
generation and index into the same `AtomicU64` rejects the stale update. Fixed
storage keeps the witness free of use-after-free undefined behavior.

Run the correctness control:

```bash
cargo run -p lock-free-reclamation-aba --bin aba_lab -- check
```

Run one hot-CAS treatment outside a full evidence collection:

```bash
cargo run --release -p lock-free-reclamation-aba --bin aba_lab -- bench raw 5000000
cargo run --release -p lock-free-reclamation-aba --bin aba_lab -- bench tagged 5000000
```

The timing arms use the same 64-bit atomic and two successful CAS operations per
iteration. They measure generation packing on one uncontended hot atomic. They
do not measure hazard scans, epoch advancement, RCU grace periods, allocation,
destruction, stalled readers, or contention.

On the exact source candidate `6b20b1f`, the tagged/raw elapsed-time ratio was
`1.038854` with a 95% interval of `[1.038506, 1.039203]` on the resolved `xxl`
host and `1.002938 [1.001997, 1.003880]` on the required Arm host. Each estimate
uses 12 order-balanced blocks and 48 fresh timed processes. Both raw/raw A/A
intervals included one. These host-specific results do not rank reclamation
protocols or generalize to an ISA.

See the [first-round decision record](rounds/01.md), [measurement contract](measurements/README.md),
and [primary sources](references.md).
