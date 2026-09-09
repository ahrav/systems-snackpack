# Evidence

Initial scratch runs on both required Linux hosts passed the lease-pause and
joint-quorum example before repository mutation. Their common source SHA-256 is
`e924e95e7f6fce605169615afa27e654a45435459f098943ec99e8416d087b3f`.

The committed-source campaign is recorded after the source commit. It uses
`experiment/run_host.sh` to check host, architecture, archive, runner, source,
correctness, and generated-code identities. Full receipts and replay assets are
retained outside Git; compact results and their exact identities are added here.

This is deterministic correctness evidence. There are no measured network,
lease-expiry, failover, disk-durability, or cross-architecture performance claims.
