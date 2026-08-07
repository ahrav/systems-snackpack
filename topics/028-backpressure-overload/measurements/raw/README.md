# Raw evidence

Each source-prefix directory retains one immutable archive from the required
Arm host and one from the runtime-resolved `xxl` host. A promoted archive
contains exact source identity, host and toolchain receipts, workspace gates,
the final binary and code-generation evidence, the fixed process schedule, raw
logical and physical receipts, analysis, independent validation, final status,
and an internal `evidence.sha256` manifest.

`SHA256SUMS` binds the two outer archives. Verify both the outer digest and the
internal manifest after extracting into a new empty directory. Never overwrite
a failed or superseded bundle; a new run or source correction receives a new
identity.
