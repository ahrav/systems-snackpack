# Raw Linux evidence

`dev-dsk-2b/` and `dev-dsk-2c/` retain the initial source-run records.
`final-e3442c2/` retains the final rerun of exact source
`e3442c23f06ef9c060f869574f532caef46fd04a` on both hosts. Each final-host
directory contains:

- source and transfer provenance;
- uname, CPU identity, available CPUs, compiler, flags, and target features;
- the correctness example, path-fix proof, and command outcome;
- environment plus every result from 12 paired process blocks;
- Cargo JSON executable-selection proof, generated-code build output, focused
  function captures, and observations;
- compressed full library assembly.

`SHA256SUMS` covers all retained records. Some initial-run sidecars preserve the
original remote path as additional provenance.
