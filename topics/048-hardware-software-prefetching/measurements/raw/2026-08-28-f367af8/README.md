# Topic 48 final exact-source receipts — 2026-08-28

These receipts bind the final checked-host campaign to source commit
`f367af8954de2626c8d0ef0b26f77eebf4dd6e99` and source archive Secure Hash
Algorithm 256-bit (SHA-256)
`58834c58bb98d296a1d10d7dc3990a7fca5a0387962f4159b036e209444ac3c2`.

The controller recorded each expected hostname and architecture before
transfer. Each target checked the controller-held archive digest before
extracting the runner. The runner checked that digest and controller identity
again, compiled the archived C source with GNU Compiler Collection (GCC)
11.5.0, ran smoke correctness and linked-code inspection, then collected 88
random and 16 sequential measured processes. A complete four-process block is
the analysis unit: 22 random blocks and 4 sequential blocks per host.

Both in-host validators report `valid: true` and
`codegen_binding: regenerated-from-binary`. They bind the controller-supplied
archive digest, source commit, hostname, architecture, host metadata, build
tokens, every executed experiment-source hash, binary hash, process schedule,
checksums, fault and endpoint-placement controls, recomputed timing fields, and
the architecture-specific linked hint. The independent publication validations
repeat the digest and identity checks; their code-generation boundary is the
manifest-bound recorded text because the publication host lacks the two Linux
cross-disassemblers.

## Bound hashes

| Item | SHA-256 |
|---|---|
| Source archive | `58834c58bb98d296a1d10d7dc3990a7fca5a0387962f4159b036e209444ac3c2` |
| Executed `prefetch_bench.c` | `a9030641b5646fc329317ba01906146132a89de8eef23fc5c9294628b0221a20` |
| Executed `run_host.sh` | `760f4dbd305d54b48086828c12421f14e5754ead70eaa0f56f7560deb52ec286` |
| Executed `run_campaign.py` | `8dc69a9006870dd96a5f79581f6b7b66d2abfca1616ccf993e9bd24c3e9b139b` |
| Executed `analyze.py` | `4d9e1254bb14689e7a45dc1673f78cada32836fe98d13c51efe8183ecd97d1c2` |
| Executed `validate_receipts.py` | `fa5bb4d479a1cb6eee81a66d46a6b8797d8d31531ee936cbe482b3c3390bc223` |
| AArch64 binary | `0e481c797b2b7c107d6ed71e55d7220e395ac28f9978ef4d6f695fe2cecc20e1` |
| `xxl` x86-64 binary | `e5abef158fef21a9daa0ef996e6c0f59c42c8341fd2eafb225fc88c2b26c2353` |
| Arm receipt archive | `3ea455a486959104a513ae20334285f6593bfc970e70f6757fa1746c774cd4eb` |
| `xxl` receipt archive | `b37e251b0d5058b1f7536320553671b8b0a2296425298bfebcf9d47453a17d35` |

## Files

- `arm-results.tar.gz` is the literal Arm target receipt.
- `xxl-results.tar.gz` is the receipt from the pre-resolved `xxl` target.
- `controller-targets.txt` records pre-transfer alias, hostname, and
  architecture evidence.
- `host-model-probes.txt` summarizes the sealed central processing unit (CPU),
  kernel, and toolchain boundary.
- `source.txt` records the commit, sealed archive, and executed-source identity.
- `publication-validation-arm.json` and `publication-validation-xxl.json`
  record independent receipt validation against controller-held values.
- `SHA256SUMS` records outer digests for every other file in this directory.
