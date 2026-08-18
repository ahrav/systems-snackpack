# Exact-source binding

Both host archives were produced from final-reviewed source commit
`068d082c422efce23700949b01af80f3f2554572` and one `git archive` with SHA-256
digest `f34a828911083552792785c5ebe751f83efc25885489e895be9de3c44a6c9dc7`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or ref receipt; the
pre-run remote-branch check is an orchestrator observation outside these
archives.

Each host recorded identical 1,796-entry pre/post source manifests with digest
`1750399952b21e1470ba42a1574c7ff3679feb216917b6627ee0870fd6591c92`.
The runner itself had digest
`8243ff45cd0774f73addc4e82a06b20d3acc88504531dea051239a4322f7f2c1`.

Repository history must verify that later evidence-only commits add only
archives and summaries; the host bundles cannot prove that claim.

Verify the retrieved archives with:

```bash
shasum -a 256 -c SHA256SUMS
```

After extracting either archive, change into its result directory and run:

```bash
shasum -a 256 -c MANIFEST.sha256
```

Both 76-entry internal manifests passed after retrieval. The raw archives
contain host metadata, toolchain and target-feature records, package gates,
all 16 process streams and identities, source manifests, linked symbols,
relocations, complete disassembly, validation output, and completion status.
The local validator also rechecked both extracted process trees against the
checked-in expected output.
