# Consensus, leases, and fencing

A timeout can start recovery while an old worker remains alive. Consensus can
order a replacement grant, but the resource must enforce the handoff.

This crate models one invoice resource and the voting sets of a five-machine
membership transition. It is not a consensus or storage implementation.

```bash
cargo test -p consensus-leases-fencing
cargo run -p consensus-leases-fencing --example handoff
```

Expected example output:

```text
stale_accepted=false final_value=20
union_majority=true joint_majority=false
```

## Contracts

- A trusted authority issues increasing, nonzero generations. `install` models
  applying a grant at the resource. It is not token authentication.
- Each installation and write is one serialized transition. After generation 42
  is installed, writes from 41 fail. Issuance elsewhere alone has no such effect.
- A real sink must atomically check and apply the write, retain enforcement state
  through recovery, and keep resource and generation identities from being reused.
- Equal generations may write repeatedly. Fencing does not deduplicate retries,
  order writes within one ownership grant, or make an external payment exactly once.
- The quorum helpers use distinct configured identifiers. Joint acceptance needs
  separate old and new majorities, not a majority of their union.

For old `{A,B,C}` and new `{C,D,E}`, `{A,B,C}` is a union majority but has only one
new voter. Old `{A,B}` and new `{D,E}` can decide independently under an unsafe
configuration switch. The exhaustive test checks all 1,024 ordered pairs of
five-voter subsets for the modeled intersection properties. This does not prove
configuration activation, log persistence, election safety, or a complete protocol.

See [the round](rounds/01.md), [sources](references.md), and
[validation and evidence](measurements/README.md).
