# Anti-entropy and state reconciliation

This finite catalog model separates causal comparison, sibling retention,
delivery coverage, and deletion history. Three stable writer identities label
versions. Merge keeps maximal histories, including concurrent delete/edit pairs.
Missing history is not a deletion.

```sh
cargo test -p topic063-anti-entropy
cargo run --release -p topic063-anti-entropy --example contracts
sh topics/063-anti-entropy/scripts/run-linux.sh
```

The tests exhaust 32 fixture subsets for idempotence, 1,024 pairs for
commutativity, and 32,768 triples for associativity. They also check stale
resolution context, duplicate delivery, isolation, cold-key repair coverage,
history identity reuse, and retained versus forgotten tombstones.

`differing_ranges` is an exact comparison oracle over fixed ranges. It includes
causal and deletion metadata. It does not implement hashes or a Merkle tree.
Neither the oracle nor a matching digest determines conflict semantics.

## Cost boundary

For one million 256-byte serialized records, a one-direction full payload is
256,000,000 bytes. With ten differing 1,000-record leaves and 220 exchanged
32-byte digests, the illustrative selective payload is 2,567,040 bytes.
The digest count is an assumed protocol input, not a general tree bound.
Fresh summary construction may still scan all records. Network savings do not
establish disk savings. At 100,000,000 scan bytes/s, the byte-only lower bound
is 2.56 seconds. No rate here was measured.

An illustrative 30,000,000-byte repair backlog drains in ten seconds with
5,000,000 repair bytes/s and 2,000,000 new debt bytes/s. Both rates must use the
same work units and remain constant for that fluid estimate. Launch frequency
does not establish completed range/replica coverage.

## Limits

This is a correctness experiment, not a storage engine, network simulator,
gossip performance model, quorum protocol, or safe tombstone collector. It has
no persisted counters, writer retirement, changing ownership, cryptographic
hashing, or crash recovery. It rejects two payloads with one history identity.
Finite passing schedules do not prove arbitrary delivery will converge.

Use prompt dissemination for recent updates, scheduled anti-entropy for cold
data, causal metadata for supersession, and explicit application rules for
concurrent edits. A failure detector supplies reachability evidence, not data
agreement. Retire deletion evidence only under a protocol covering returning
replicas, old messages, and restored backups.

See [sources](references.md) and [round evidence](rounds/01.md).
