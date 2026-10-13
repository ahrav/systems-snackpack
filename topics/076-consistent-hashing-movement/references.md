# Primary references

- Karger et al., STOC1997, https://people.csail.mit.edu/karger/Papers/web.pdf . Monotonic placement and expected view overlap.
- Thaler and Ravishankar, IEEE/ACMToN1998, https://www.cs.kent.edu/~javed/DL/papers/web/p1-thaler.pdf . Highest-random-weight mapping.
- Lamping and Veach2014, https://arxiv.org/pdf/1406.2294 . Dense bucket numbering and jump hash contract.
- Eisenbud et al., NSDI2016, https://www.usenix.org/system/files/conference/nsdi16/nsdi16-paper-eisenbud.pdf . Maglev table and connection tracking.
- Redis Cluster specification, https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/ . Slots, redirects, migration states. Read2026-10-13.

Derived here:adjacent modulo unchanged 1/(N+1); ideal equal-weight HRW replacement
endpoint 2/(N+1), fully materialized remove/add transfer events 2/N. Fixed rings and
finite keys need observed counts. Membership authority and safe cutover are outside
this single-process placement experiment.
