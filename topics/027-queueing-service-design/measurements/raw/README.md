# Raw evidence

The `bf93921` directory retains one compressed evidence archive per required
host. Exploratory and failed pre-measurement results are not retained here as
exact-candidate evidence.

For each candidate and host, store one immutable archive or directory under
`<source-prefix>/` containing:

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

## `bf93921` archives

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| `topic27-bf93921-arm-results.tar.gz` | `71,062,778` | `0b90a950edf6c8cb702017872b595487b7d3f439d7ab6dddd2d515e5040083e2` |
| `topic27-bf93921-xxl-results.tar.gz` | `71,231,109` | `90a25e24ebd18f6ee0f38ee1fa9c9dde35d6a54515b48cf659159350752f2b36` |

Verify an archive after extraction:

```bash
cd topics/027-queueing-service-design/measurements/raw/bf93921
sha256sum --check SHA256SUMS
mkdir /tmp/topic27-arm
tar -xzf topic27-bf93921-arm-results.tar.gz -C /tmp/topic27-arm
cd /tmp/topic27-arm/results
sha256sum --check evidence.sha256
```

Use a new empty extraction directory. The `xxl` archive has the same internal
layout and verification command.
