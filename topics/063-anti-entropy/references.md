# Primary sources and claim boundaries

- [Demers et al., Epidemic Algorithms for Replicated Database Maintenance (1987)](https://www.cs.cornell.edu/courses/cs614/2004sp/papers/p1-demers.pdf): persistent anti-entropy versus finite rumor spreading. Our fixed schedule does not measure randomized dissemination time.
- [Dynamo (2007), sections 4.4 and 4.7](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf): causal version comparison, application conflict resolution, and Merkle comparison of shared key ranges. Historical Dynamo, not a claim about current DynamoDB.
- [SWIM (2002)](https://www.cs.cornell.edu/projects/Quicksilver/public_pdfs/SWIM.pdf): membership dissemination and failure detection are separate from application-data repair.
- [Riak causal context](https://docs.riak.com/riak/kv/latest/learn/concepts/causal-context/index.html): context must accompany a resolving write. The fixture uses fixed vectors and does not implement Riak's dotted version vectors.
- [Cassandra 4.1 read repair](https://cassandra.apache.org/doc/4.1/cassandra/operating/read_repair.html): `BLOCKING` versus `NONE`, monotonic quorum reads versus partition-level write atomicity. Product/version-specific; our read coverage example is not Cassandra execution.
- [Cassandra repair](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/repair.html): selected-node range coverage, full versus incremental repair, and repair completion before deletion evidence expires.
- [Cassandra tombstones](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/compaction/tombstones.html): resurrection and local compaction eligibility. Elapsed grace alone does not prove every replica is current.

Accessed 2026-09-30. The arithmetic and finite-state workload are original
illustrations. They establish no production throughput or architecture ranking.
