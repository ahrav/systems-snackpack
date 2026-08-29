# Exact-source receipt bundle

This bundle publishes the accepted Topic 50 campaigns for source commit
`97572e93a6ee98e14bece7501068d5cedd962571`.

- `arm-results.tar.gz` is the sealed receipt from the literal AArch64 target.
- `xxl-results.tar.gz` is the sealed receipt from the runtime-resolved x86-64
  target.
- The controller-validation JSON files are independent revalidation results
  after extracting the host archives locally.
- `source.txt` binds the commit and path-limited Git archive digest.
- `xxl-resolution.txt` records the alias and backing hostname used by the
  controller.
- `host-model-probes.txt` records scheduler-ownership probes collected after
  the campaigns; they are not part of the sealed run windows.
- `SHA256SUMS` binds every published file in this directory except itself.

Each host receipt contains 64 raw attempts, 64 fresh process identifiers,
eight primary blocks, eight A/A blocks, source manifests, exact linked
disassembly, host metadata, and the independently recomputed summary.

The source archive SHA-256 is
`546dd1fa3cd205fd19bc937198281e0b7b6ca929a85d657c18f68d8312c4d035`.
The sealed Arm receipt archive SHA-256 is
`391dc2e87b885d6b3db16b0436c52581863676eb6fb03c167dd474629a0e6044`.
The sealed `xxl` receipt archive SHA-256 is
`a4febd55a16a5db46205bb2edd1a07a09d6be39955a5043ed85f5e6d6190712e`.
