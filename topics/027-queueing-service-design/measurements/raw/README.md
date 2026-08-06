# Raw evidence

No raw bundle is retained yet. Do not place exploratory or pre-commit results
here as exact-candidate evidence.

For each candidate and host, store one immutable bundle under
`<source-prefix>/<host-label>/` containing:

- the exact source archive, archive SHA-256, full source commit, and sorted
  source manifests verified before and after the run;
- host identity and alias resolution, kernel/CPU/affinity records, timer and
  toolchain identity, complete build log, final binary and digest, symbols, and
  final-image disassembly;
- calibration output, derived interval, committed schedule and seeds, an
  append-only attempt ledger, raw request rows, per-process receipts,
  stdout/stderr, exit statuses, and checksums;
- the exact analyzer and validator used, machine-readable and human-readable
  summaries, failure disposition, and `evidence.sha256` covering every retained
  file except the manifest itself.

The final status must report source, build, schedule, timestamp, count,
checksum, analysis, code-generation, and manifest gates separately. Exit zero
alone is insufficient. Never overwrite a failed or superseded bundle; give a
new candidate or rerun its own immutable identity. Large binary files use the
attributes in [`.gitattributes`](.gitattributes).
