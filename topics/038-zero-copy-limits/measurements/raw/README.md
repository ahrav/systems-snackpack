# Raw receipts

[`2026-08-17-c6b76b4/`](2026-08-17-c6b76b4/) retains the two result archives
for measured source commit
`c6b76b4429272814c7e3ab57a199c9d2c2d8ce66`. Its `SOURCE.md` binds that commit,
the source archive, both result archives, and the retrieval and internal
manifest checks. Its `SHA256SUMS` is the compact integrity manifest for the two
retained archives.

Verify the retrieved repository artifacts from that directory with:

```bash
shasum -a 256 -c SHA256SUMS
```

Each result archive also contains a `MANIFEST.sha256` over its 272 receipt
files. Verify that manifest from the root of a separately extracted archive.
The archives include raw process streams and binaries, so they are retained as
opaque evidence rather than expanded into the repository.
