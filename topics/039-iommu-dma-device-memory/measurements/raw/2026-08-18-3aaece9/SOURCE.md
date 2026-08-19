# Exact-source binding

Both host archives were produced from source commit
`3aaece99023cfa33440af7c5f90204c18840953d` and one `git archive` with Secure
Hash Algorithm 256-bit (SHA-256) digest, a content fingerprint,
`9da821782a8fd37023a05e4ca08e8e942831eabf3410eabe31e81128913765f8`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or Git reference (ref)
receipt, which would record the named reference and the commit it resolved to.
The pre-run remote-branch check is an observation by the controlling local
process, or orchestrator, outside these archives.

Each host recorded identical 1,789-entry pre/post source manifests. A source
manifest is a sorted inventory of file paths and their SHA-256 digests. The
manifest digest was
`7719886b27fafae6ebd967074dc9190caeb8229d515b463a1fff6fae8f1c16dd`.
The runner itself had digest
`d19e414e7245f60123045ed0171951442adc408b510f012a77c7e34e96f58b01`.

Repository history must verify that the later evidence-only commit adds only
archives and summaries; the host bundles cannot prove that claim.

Verify the retrieved archives against the outer checksum-list file, literally
named `SHA256SUMS`, with:

```bash
shasum -a 256 -c SHA256SUMS
```

After extracting either archive, change into its `results` directory and verify
the internal manifest file, literally named `MANIFEST.sha256`, with:

```bash
shasum -a 256 -c MANIFEST.sha256
```

Both 76-entry internal manifests passed after retrieval. The raw archives
contain host metadata; toolchain versions; target-feature records listing
compiler-reported instruction capabilities; package-gate results from format,
test, lint, documentation, and build commands; and the standard output,
standard error, exit status, and executable identity for all 16 processes. They
also contain source manifests, linked symbol records that identify named
functions, relocation records that show linker fixups used to resolve calls,
complete disassembly that renders generated machine instructions as text,
validation output, and completion status.
