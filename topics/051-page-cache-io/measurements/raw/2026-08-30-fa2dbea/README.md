# Exact-source receipt bundle

This directory publishes compact evidence for the accepted Topic 51 campaigns
from source commit
`fa2dbeab31589618b8710096dd7b6f5a8e1fff89`.

- `arm-results.external.txt` names the read-only sealed receipt from the literal
  Arm target and binds its digests.
- `xxl-results.external.txt` names the read-only sealed receipt from the
  runtime-resolved x86-64 target and binds its digests.
- The controller-validation JSON files are independent revalidation results.
  The controller extracted `validate_receipts.py` from the retained source
  archive rather than using a mutable worktree copy.
- `source.txt` binds the commit and path-limited Git archive digest.
- `xxl-resolution.txt` records the alias, backing hostname, architecture, and
  `uname` observed before execution.
- `SHA256SUMS` binds every checked-in file in this directory except itself.

Each host receipt contains 80 raw attempts with 80 distinct process
identifiers: 32 primary attempts in eight balanced blocks, 32 A/A attempts,
meaning the same method under both labels, in eight balanced blocks, and 16
direct-I/O attempts in four balanced blocks. The runners used a fixed horizon,
stopped on invalid data, and did not replace attempts. Both receipts contain
complete semantic controls, source manifests, host and toolchain identity,
generated assembly, linked disassembly, cleanup records, and a read-only seal.

The source archive SHA-256 is
`05d940c7f05dbb40bb4a039ad7d87d1897068c0379712a28355553b56de244d0`.
The sealed Arm receipt is stored outside Git at
`/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-051/2026-08-30-fa2dbea/arm-results.tar.gz`.
Its SHA-256 is
`3f9cd8fca945d0ac82f31aaffcb32f6ac5ac2ebfff2ec1fd88e65de3da139f1e`.
The sealed `xxl` receipt is stored outside Git at
`/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-051/2026-08-30-fa2dbea/xxl-results.tar.gz`.
Its SHA-256 is
`bdc866008d1ceafb87fd6377920233c406737fa5a2920a2b5155075a412e8955`.
The uncompressed Arm and `xxl` receipt-manifest SHA-256 values are
`8bda60aba9d24fe3178f903df0cd9aa22862f57cb81e2799c30540cb34b7dc77`
and
`18dcb74622c1cbcb6b97ce594e4124170d360ef35a95d5bb5872f8f1408d2c34`.

Local validation used these expected identities:

```text
Arm label: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com
Arm host:  dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com
Arm arch:  aarch64
xxl label: xxl
xxl host:  dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com
xxl arch:  x86_64
commit:    fa2dbeab31589618b8710096dd7b6f5a8e1fff89
archive:   05d940c7f05dbb40bb4a039ad7d87d1897068c0379712a28355553b56de244d0
```

Both independent validation outputs report `pass: true`, `sealed: true`, and
80 fresh processes. Earlier candidate commits failed before sealing because of
tool-path and direct-I/O alignment assumptions. Their partial scratch trees are
not included in this accepted bundle.
