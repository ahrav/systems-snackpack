# Distributed atomic commit

Topic 098 models durable prepare and decision ordering for one transaction.
The running example transfers 10 units from A to B. A third participant, when
present, records an audit entry with zero balance change.

## Run

```bash
cargo test -p distributed-atomic-commit
cargo run -p distributed-atomic-commit --example explore -- safe 2 > safe.tsv
python3 topics/098-distributed-atomic-commit/experiment/oracle.py safe.tsv
cargo run -p distributed-atomic-commit --example explore -- timeout 2 > timeout.tsv
python3 topics/098-distributed-atomic-commit/experiment/oracle.py timeout.tsv
cargo run -p distributed-atomic-commit --example explore -- early 2 > early.tsv
python3 topics/098-distributed-atomic-commit/experiment/oracle.py early.tsv
```

Safe output has zero violations. Fault modes require an agreement violation and
print the shortest discovered trace. A successful fault check means the checker
detected the intentionally broken protocol.

## Contract and model boundaries

Participant states are working (0), prepared (1), committed (2), aborted (3).
Prepare and terminal changes represent atomic durable records. Decision 0 means
undecided. The coordinator retains COMMIT (2) or ABORT (3) across restart.
Every YES follows preparation. Every safe COMMIT message follows durable COMMIT.
Terminal participants ignore conflicting messages and deduplicate repeated ones.

The participant set is fixed before exploration. Prepare requests are implicitly
available initially. Messages are monotone presence bits: they may be delayed
indefinitely and delivered repeatedly. Permanent loss is represented by never
scheduling delivery. Retransmission and identical duplicate messages collapse to
the same state. Each coordinator crash discards votes and volatile decisions.
Recovery has sole coordinator authority; an undecided recovered coordinator
persists ABORT. Prepared participants continue waiting for an authoritative decision.
A coordinator may also choose ABORT while undecided, representing cancellation.

The graph includes repeated crashes and recovery. Participant process crashes
are abstracted away because all participant state is durable; participant downtime,
volatile local work, disk failure, torn writes, competing coordinators, dynamic
membership, multiple transaction IDs, acknowledgment tracking, log reclamation,
real locks, reads, and physical network/storage I/O require a richer model.

The independent Python oracle projects each edge onto participant states. Its
abstract legal-step relation permits preparation, abort by a working participant
before any commitment, abort by a prepared participant only after durable ABORT,
and commitment after every participant prepared. It also checks terminal
stability, decision stability, agreement, commit validity, consistency between
terminal participants and the durable decision, and terminal balance
conservation. Reverse reachability checks that each safe state has some path to
uniform completion. This existential property permits unfair infinite executions;
it does not prove eventual termination. The Rust explorer owns graph completeness.

The timeout mutant permits a prepared participant to abort. The early mutant
allows COMMIT delivery from a volatile coordinator decision. A crash then loses
that decision, and recovery can persist ABORT. Both mutants can split outcomes.

## Costs and alternatives

For N participants, a simple acknowledged prepare/vote/decision/ack exchange
uses 4N messages. With parallel requests, RTT r, slowest prepare force p,
coordinator force c, and slowest terminal force f, a simplified model gives
r+p+c to durable decision and 2r+p+c+f to all acknowledgments. These are derived
costs. This example measures correctness only.

Co-location can reduce an operation to one local transaction. 2PC requires
prepared-state recovery and retains resources while outcomes are unresolved.
Replicating coordinator state improves availability under the replication
protocol's quorum assumptions. Sagas permit intermediate effects and require
business compensation. An outbox couples a local write to eventual messaging;
consumers still need duplicate handling. Isolation and request deduplication are
separate contracts from atomic commit.

## Sources

- [Gray and Lamport, Consensus on Transaction Commit](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-2003-96.pdf): abstract safety relation, 2PC, and Paxos Commit.
- [PostgreSQL PREPARE TRANSACTION](https://www.postgresql.org/docs/current/sql-prepare-transaction.html): durable preparation, retained locks, and vacuum effects.
- [PostgreSQL COMMIT PREPARED](https://www.postgresql.org/docs/current/sql-commit-prepared.html): completion from an eligible session.
- [CockroachDB transaction layer](https://docs.cockroachlabs.com/docs/stable/architecture/transaction-layer): staging records, intents, and Parallel Commits.

See [results](results/RESULTS.md) for exact-source validation and limits.
