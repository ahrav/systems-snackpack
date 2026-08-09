# Raw evidence

Promoted evidence stores one compressed result archive per required Linux host
plus an outer `SHA256SUMS`. Extract an archive to inspect host metadata, source
identity, process receipts, generated code, validation output, and workspace
gate logs.

The historical `ad25198` archives are under [`ad25198/`](ad25198/). They
retain pre-protocol outputs for that source commit only. They predate the
current runner's loader and absolute-tool provenance controls and do not attest
later branch or merge commits.
