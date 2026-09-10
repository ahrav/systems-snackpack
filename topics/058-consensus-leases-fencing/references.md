# Primary sources

Read on 2026-09-09. Models and arithmetic in this topic are illustrative.

- [Raft extended paper, 2014](https://raft.github.io/raft.pdf): Sections 5.2-5.4
  describe elections, persisted state, and commitment; Section 6 describes joint
  membership. The set model here covers quorum arithmetic only.
- [Chandra and Toueg, Unreliable Failure Detectors, 1996](https://www.cs.cornell.edu/courses/cs734/2000FA/cached%20papers/ct96.pdf):
  separates detector completeness and accuracy from consensus progress.
- [Chubby, 2006, Section 2.4](https://storage.googleapis.com/gweb-research2023-media/pubtools/4444.pdf):
  recipient validation of lock sequencers and the imperfect lock-delay fallback.
- [Kleppmann, How to do distributed locking, 2016](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html):
  paused owners and resource-side fencing. This crate adds an explicit generation
  installation event to name the resource's handoff boundary.
- [etcd Raft library](https://github.com/etcd-io/raft): quorum-confirmed and
  clock-dependent lease reads; transport and persistence integration boundaries.
  This is a live repository reference, not a pinned dependency of this crate.
- [etcd learner design](https://etcd.io/docs/v3.6/learning/design-learner/):
  non-voting catch-up and availability hazards of unready voters. The page retains
  v3.4 history and proposed features; do not infer current limits from it.
- [etcd tuning](https://etcd.io/docs/v3.6/tuning/): network and storage delays both
  affect heartbeat processing. This experiment does not validate timeout values.
