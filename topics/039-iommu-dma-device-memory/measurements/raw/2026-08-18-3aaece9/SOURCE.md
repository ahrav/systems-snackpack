# Exact-source binding

Both host archives were produced from source commit
`3aaece99023cfa33440af7c5f90204c18840953d` and one `git archive` with SHA-256
digest `9da821782a8fd37023a05e4ca08e8e942831eabf3410eabe31e81128913765f8`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or ref receipt; the
pre-run remote-branch check is an orchestrator observation outside these
archives.

Each host recorded identical 1,789-entry pre/post source manifests with digest
`7719886b27fafae6ebd967074dc9190caeb8229d515b463a1fff6fae8f1c16dd`.
The runner itself had digest
`d19e414e7245f60123045ed0171951442adc408b510f012a77c7e34e96f58b01`.

Repository history must verify that the later evidence-only commit adds only
archives and summaries; the host bundles cannot prove that claim.

Verify the retrieved archives with:

```bash
shasum -a 256 -c SHA256SUMS
```

After extracting either archive, change into its `results` directory and run:

```bash
shasum -a 256 -c MANIFEST.sha256
```

Both 76-entry internal manifests passed after retrieval. The raw archives
contain host metadata, toolchain and target-feature records, package gates,
all 16 process streams and identities, source manifests, linked symbols,
relocations, complete disassembly, validation output, and completion status.
