# Raw evidence

Store one immutable bundle below `<source-prefix>/<host-label>/` for each host
and candidate. A complete bundle contains:

- the exact source archive, its SHA-256, and sorted pre-run and post-run source
  manifests;
- requested endpoint, alias expansion, resolved host, topology, affinity,
  memory policy, page-size, transparent-huge-page, and automatic-balancing
  records;
- compiler identity, complete build command and environment boundary, build
  log, final binary, binary SHA-256, and final-image disassembly excerpt;
- the predeclared schedule and seed, an append-only attempt ledger, raw process
  rows, placement queries, fault counts, checksums, standard output/error, and
  wrapper exit status;
- the analysis program, summary, and a final `SHA256SUMS` covering every
  retained file except the manifest itself.

The bundle's status must say whether source verification, build, fixed schedule,
placement, affinity, zero-fault read phase, checksum, analysis, and hashing
passed. Exit zero by itself is not a successful measurement.

Never overwrite a failed or superseded bundle. Give a new candidate its own
source prefix and explain the disposition in the corresponding measurement
note. Large binary files use the attributes in [`.gitattributes`](.gitattributes)
so code review does not render meaningless textual diffs.

## Provenance of the `8edc181` bundles

Raw bundles are immutable snapshots bound to their recorded source commit.
Review commits changed the experiment sources after these bundles were
recorded; those changes apply to future runs only. The current validator
verifies each bundle against the recorded commit's blobs (`source-identity.txt`
hashes resolved through `git show <source_commit>:<path>`), so exact-source
validation still holds for the retained bundles even though the working-tree
experiment files have since changed.
