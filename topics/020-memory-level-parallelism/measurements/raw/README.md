# Raw evidence

`635f868/arm/evidence.tar.gz` and
`635f868/x86-live/evidence.tar.gz` preserve the complete successful runner
outputs byte for byte. Each adjacent `SHA256SUMS` covers the archive and its
post-run host or endpoint supplements. Inside each archive:

- `evidence.sha256` covers the runner output as it existed at finalization;
- `run.status` must report `exit=0` and `source_manifest=match`;
- `experiment/attempts.csv` retains every invoked process;
- `experiment/raw.csv` contains only the complete fixed schedule.

`211f8b8-failed` retains the sealed exit-141 records from the rejected archive
verification implementation. No performance observation came from that
candidate. Each host directory has a `SHA256SUMS` file covering the finalizer
manifest, run status, and wrapper exit.

`local-smoke-20260730` retains the fixed-order, single-process macOS smoke run.
Its `SHA256SUMS` covers the host record, output streams, and binary digest.
