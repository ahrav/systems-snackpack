# Raw Linux evidence

Each host directory contains:

- `provenance.txt`: source commit and archive hash;
- `host-env.txt` and `cpu-identity.txt`: uname, CPU identity, available CPUs,
  compiler, build flags, and native target features;
- `workspace-gates.txt`: exact-source validation and correctness example;
- `processes.txt`: equivalence result and all 12 paired blocks;
- `codegen-build.txt` and `codegen-inspection.txt`: assembly build and initial
  symbol search;
- `hot-functions.s`: complete emitted `scan_count` and `contains_exact`
  functions;
- `release.s.gz`: compressed full library assembly, with a sidecar checksum.

`SHA256SUMS` covers these records. The sidecar checksums retain the original
remote path as additional provenance.
