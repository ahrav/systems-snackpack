# Exact source and result identity

- Measured source commit:
  `c6b76b4429272814c7e3ab57a199c9d2c2d8ce66`
- Source archive SHA-256:
  `f6e75b525d82964437d23f74494758ccdddd1bc0da31e3b2971cdf4d9cd913e4`
- Source archive prefix: `systems-snackpack-c6b76b4/`
- Source archive size: 317,085,834 bytes
- Arm result archive: `arm-results.tar.gz`, SHA-256
  `dcea29d8131846a50fd1f3da3a9efa618a0a0068d953bfd4734b9f159a494877`
- `xxl` result archive: `xxl-results.tar.gz`, SHA-256
  `7403a907c3dd5f882b7dc77bdd8b977ef2571b784db3cd830a0fcff60592d995`
- Arm host receipt capture: `2026-08-17T14:48:57Z`
- `xxl` host receipt capture: `2026-08-17T14:48:59Z`
- Arm native transfer executable SHA-256:
  `4590898f29d980adce4717cdef03b7686c0b26a391209802a3c1702e52cb9e8f`
- `xxl` native transfer executable SHA-256:
  `ca21e78e3958f786db37b3f95c0bd4e06715768614146725ade212f77d9d13f0`

Each host verified the source-archive digest before extraction, located the one
Topic 38 host runner inside the archive, and verified that the invoked runner
matched the archived runner. Its pre-run and post-run source manifests each
contain 1,773 entries and are byte-identical, with SHA-256
`0b2ceed67acaf154b8aaf1bbf75d05f629c1b39d279dc003555cc3690b222688`.
The enumerated extracted source therefore did not change between those capture
points on either host.

After retrieval, both result archives were hashed again at the paths retained
in this directory. Each archive was extracted separately, and
`shasum -a 256 -c MANIFEST.sha256` passed for all 272 entries in each result
tree. Those internal manifests cover the summary, recomputed analyses, raw
process streams, correctness and completion controls, source manifests,
toolchain and host receipts, strict generated-code inspection, binaries,
runner, and validator.

For each host, strict call-site receipts contain five transfer calls and three
completion-control calls in each generic and native executable. The validators
recomputed the retained analyses exactly and checked consistency between every
completion's `ee_code` and copied-fallback field.

The 317,085,834-byte source archive is bound here by its full commit and digest;
it is not duplicated in this directory. A later evidence-only commit adds these
retained archives and documentation without changing the measured experiment
source identified above.
