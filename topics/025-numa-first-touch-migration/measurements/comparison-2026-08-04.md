# Cross-host comparison: 2026-08-04

Both required hosts ran commit
`8edc18103c6649949ce393cfcf7a099327fcf92c` with the same source archive,
SHA-256 `b970b772411ea8e72cb416689624938790e1db82c32a3c406e37208480f056a0`.
Both passed the workspace, source, placement, checksum, code-generation, and
receipt gates.

The Arm host exposed one NUMA node, so it supplied a correctness control and no
remote-memory estimate. The `xxl` host exposed two nodes and supplied reciprocal
performance contrasts. On that exact x86 host, a four-pass dependent chase was
1.5610 times slower with node-1 pages from a node-0 worker and 1.5540 times
slower in the reverse direction. A/A controls included 1.0.

The cross-host difference is topological, not an instruction-set comparison.
The Arm host cannot answer the remote-memory question because it has no remote
node. Both final binaries preserved the intended scalar dependency chain, but
their elapsed values must not be compared as if the hosts offered the same
treatment.

The pre-artifact scratch observations in the topic README are now superseded by
these exact-source records. They remain labeled because they used different
source and a shorter experimental design.
