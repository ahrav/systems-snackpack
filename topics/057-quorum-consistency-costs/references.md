# Primary sources

- [Herlihy and Wing, Linearizability (1990)](https://www.cs.cmu.edu/~wing/publications/HerlihyWing90.pdf): real-time single-object history contract.
- [Attiya, Bar-Noy and Dolev (1995)](https://groups.csail.mit.edu/tds/papers/Attiya/JACM95.pdf): single-writer atomic register, majority query and propagation, retained tags and progress assumptions.
- [Attiya, Robust Simulation of Shared Memory (2010)](https://hagit.net.technion.ac.il/files/2015/09/EATCScolumn.pdf): read propagation and broader register constructions.
- [Dynamo (2007), sections 4.5-4.6](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf): quorum-like operation, sloppy membership, hinted handoff. Historical Dynamo, not present-day DynamoDB.
- [Raft, section 8](https://raft.github.io/raft.pdf): linearizable reads need current-term commit knowledge and current authority; local leader state alone is insufficient.
- [PostgreSQL 18 WAL configuration](https://www.postgresql.org/docs/18/runtime-config-wal.html): remote_write, on, remote_apply and synchronous-standby configuration boundaries.

Sources checked 2026-09-06. Set arithmetic and the numerical cost substitutions
are derived here. Finite tests demonstrate the modeled schedules only.
