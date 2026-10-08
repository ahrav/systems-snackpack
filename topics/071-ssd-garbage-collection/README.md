# SSD garbage collection and write amplification

This volatile page model compares round-robin reclamation, full-scan greedy selection, and four random block probes with a round-robin fallback. It performs no device I/O. Physical media latency, durability, wear, placement separation and steady-state convergence are not modeled.

```bash
cargo test -p ssd-gc
cargo run --release -p ssd-gc --example compare -- greedy 64 90 uniform 20000 9215 71
python3 topics/071-ssd-garbage-collection/run.py /tmp/topic071-results
```

The example accepts policy, block count, occupancy percent, trace pattern, measured writes, warmup writes and seed. Patterns are uniform, hot and cyclic. See [the frozen experiment](EXPERIMENT.md), [round notes](rounds/01.md), [primary sources](references.md), and [measurements](measurements/README.md).

The physical-page array and logical mapping form a bijection over live values. Invalidating a page does not move the append frontier backward. One erased block remains reserved for relocation. Every victim has at least one invalid slot, so copying its survivors leaves room for a host write. The independent oracle checks every final logical value; unit tests also check intermediate invariants.

For B pages per block, E erases, H host writes, C copied pages and change dF in writable-page inventory: dF=B*E-H-C. Window WAF=(H+C)/H. A complete cycle copying V pages and accepting B-V host writes gives B/(B-V), but an arbitrary window can pay for capacity used later or consume earlier free inventory.

The hot generator sends 90% of requests into the first tenth of logical pages and 10% across the whole space, so about 91% reach the hot set. Round robin uses physical indices, not age/FIFO ordering. Sample4 samples with replacement, including ineligible blocks; fallback can scan all blocks. Greedy scans maintained live counts, not page contents. A bucketed greedy implementation is outside this comparison.

`write` invalidates the old mapping before allocation only because this teaching model has no interruption or crash recovery. Never use that ordering as a persistence protocol.
