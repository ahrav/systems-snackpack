# Replication, quorum systems, and consistency costs

A quorum response must establish a precise promise. Fixed-set overlap lets reads
discover retained completed writes. It does not by itself prevent successive
reads from moving backward after an incomplete write.

Run the deterministic model:

```bash
cargo run -p quorum-consistency-costs --example quorum
cargo test -p quorum-consistency-costs
```

The example first returns version 1, then version 0. Waiting for read write-back
protects all nine pairs of three-replica majority sets. Tests enumerate overlap
for all valid read/write sizes through seven replicas. They also check completed
writes and read write-back with three, five, and seven replicas, delayed messages,
invalid sets, fallback replicas, and response-threshold costs.

## Contract

Tags represent successive writes by one writer. Replicas retain the highest tag.
Membership is fixed. This is a finite mechanism model, not a complete ABD
implementation or a proof covering arbitrary concurrent histories. It omits
network execution, durable storage, restarts, tag allocation, membership changes,
malicious replicas, and multi-key transactions. Read/write atomicity does not
make a read followed by a write an atomic conditional operation.

## Boundaries and costs

- An acknowledgment may mean receipt, durable storage, or applied visibility.
  Define the boundary before counting replicas.
- A client timeout may leave an applied update. It does not prove rollback.
- With N fixed replicas, R read responses and W write acknowledgments,
  R + W > N forces overlap. For N=3 and R=W=2, minimum overlap is one.
- Background repair after returning cannot replace required read write-back.
- Sloppy quorum fallback changes the replica universe. A/D and B/C are disjoint
  even if the home set is A/B/C and both response counts are two.
- For parallel phase completion times d_i and coordinator cost c, latency is
  approximately c + d_(k), where d_(k) is the kth smallest response time.
  Invented times 1/4/20 ms with k=2 and c=0.2 ms give 4.2 ms. Two such sequential
  phases give 8.4 ms. These are model inputs, not measurements or percentiles.
- Sending a payload S from a leader to N-1 peers at rate lambda costs roughly
  (N-1)*S*lambda payload bytes/s. N=3, S=1024 bytes, lambda=1000/s gives
  2,048,000 bytes/s, excluding headers, retries and repair.
- Both reads and writes remain reachable with at most min(N-R,N-W) missing
  replicas. For N=3 and R=W=2, that is one. This is not a probability estimate.

Use a proven register protocol for independent reads/writes. Use a proven
consensus-backed state machine for operations conditional on prior state.
Asynchronous replication needs explicit staleness and loss limits. Conflict
resolution needs domain rules. Safe leader reads require current authority and
application of the required committed prefix.

See [sources](references.md), [round notes](rounds/01.md), and
[evidence](measurements/README.md).
