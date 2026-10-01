# Kernel bypass and packet-buffer ownership

A finite Rust ledger separates receive supply, application ownership, transmit
publication, descriptor consumption, and completion. It also checks partial
transmit acceptance, aligned-frame aliases, and packet assembly across batches.
It does not open sockets, bind devices, implement concurrent rings, or measure
network performance. The ledger is sequential and cannot prove DMA ordering.

```sh
cargo test -p topic064-kernel-bypass
cargo run --release -p topic064-kernel-bypass --example contracts
sh topics/064-kernel-bypass/scripts/run-linux.sh
```

Nine tests cover early reuse, receive starvation, all 33 accepted-prefix lengths
for a 32-packet burst, atomic rejection, aliases, multi-batch assembly, bounded
malformed-packet cleanup, the wakeup predicate, and 3,200 complete frame cycles.
The assembly object owns identifiers only. Its caller retains actual payloads.
Completion is an input to this model, not a discovered hardware event or proof
of remote delivery. Invalid-descriptor recovery differs across kernel versions.

## Selection and cost

Keep socket semantics when the application needs the kernel transport stack.
Busy polling can change wakeup delay while keeping that stack. AF_XDP exchanges
packet descriptors with user space; validate actual copy/zero-copy mode and
queue matching. DPDK exposes driver-dependent burst interfaces. A partial
transmit transfers only the accepted prefix. Bifurcated drivers do not require
detaching the NIC from its kernel driver.

For one million packets/s, assumed 300 cycles/packet and 1,600 cycles/batch,
32 actual packets/batch cost 350 cycles/packet before empty polling. At an
assumed three billion cycles/core/s this is 0.117 core-equivalents. A dedicated
loop may still occupy a full core. Configured maximum burst size is not the
observed average batch size. None of these input costs was measured.

Waiting for 32 evenly spaced arrivals at 500,000 packets/s per queue adds
31 microseconds average formation delay. Processing up to 32 available packets
need not wait for a full batch. A 4,096-frame pool with 2,048-byte chunks occupies
8 MiB of frame storage. With 3,072 held frames, the remaining 1,024 buy at most
1.024 ms at the aggregate one-million-packet/s rate, assuming immediate correct
queue placement and one frame per packet. Capacity cannot repair a stalled owner.

Use [primary sources](references.md), then inspect [recorded evidence](rounds/01.md).
