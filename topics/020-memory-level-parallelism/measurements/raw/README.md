# Raw evidence

`635f868/arm/evidence.tar.gz` and
`635f868/x86-live/evidence.tar.gz` preserve the complete successful runner
outputs byte for byte. Each adjacent `SHA256SUMS` covers the archive and its
post-run host or endpoint supplements. Inside each archive:

- `evidence.sha256` covers the runner output as it existed at finalization;
- `run.status` must report `exit=0` and `source_manifest=match`;
- `experiment/attempts.csv` retains every invoked process;
- `experiment/raw.csv` contains only the complete fixed schedule.

Both `635f868` bundles predate the runner's build-hygiene changes. Their
`host.txt` records `source_commit`, `source_verification`, and
`source_archive_sha256` but not `source_trust_root`, `swept_environment`, or
`cargo_home`, because at `635f868` the runner did not yet sweep the
codegen-affecting environment, point `CARGO_HOME` at an empty directory, or pin
the `-C target-cpu=native` build to the selected CPU. Read them as evidence from
that runner revision, not from the one in this tree.

That gap does not invalidate the retained numbers, and on the x86 host it is
answered directly: `dev-dsk-ahrav-2c-32182091` has no `~/.cargo/config.toml` and
no `RUSTC*`, `RUSTFLAGS`, or `CARGO_*` override set, so there was nothing for
the newer guards to catch. The AArch64 bundle carries no equivalent record in
either direction, which is what the newer fields exist to close. Any rerun that
needs those fields present has to be a fresh run on both hosts.

`211f8b8-failed` retains the sealed exit-141 records from the rejected archive
verification implementation. No performance observation came from that
candidate. Each host directory has a `SHA256SUMS` file covering the finalizer
manifest, run status, and wrapper exit.

`local-smoke-20260730` retains the fixed-order, single-process macOS smoke run.
Its `SHA256SUMS` covers the host record, output streams, and binary digest.
