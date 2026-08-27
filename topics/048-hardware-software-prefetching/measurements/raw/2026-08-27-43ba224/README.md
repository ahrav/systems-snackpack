# Topic 48 raw receipts

These receipts bind the final host campaigns to source commit
`43ba2249e862193a6b68fc5e4e72f06a377d40ef` and source archive SHA-256, a
256-bit content digest,
`07f941a479b51e2af8d57fc23d80b5ddec78ce2d9cd4af0d73474c84d6cd3f9b`.
Each host archive contains 104 measured process results: 88 randomized-gather
rows and 16 sequential-control rows. Smoke checks are separate from those
process-level replications.

## Source-identity stages

The platform blocked outbound transfer of the sealed source archive to the two
hosts. The execution-source identity remained exact:

1. Before either fresh campaign, the benchmark C file and campaign runner
   already present on each host were SHA-256 verified byte-identical to the
   committed candidate.
2. Each host compiled its verified C file, recorded the host-built binary hash,
   ran all 104 measured processes, retained raw rows and logs, and captured
   linked disassembly.
3. After retrieval, the analyzer and validator from the sealed candidate
   archive ran locally against each host receipt. Local sealing added the
   source archive, analysis, validation, and final internal manifest without
   rewriting the remote observations.

The archives preserve `REMOTE_SHA256SUMS.before-local-sealing` so readers can
distinguish files captured during host execution from files added during local
analysis and sealing.

## Bound hashes

| Item | SHA-256 |
|---|---|
| Source archive | `07f941a479b51e2af8d57fc23d80b5ddec78ce2d9cd4af0d73474c84d6cd3f9b` |
| Executed `prefetch_bench.c` | `903c84eaf5234fa5c72c8d805c2d704503fb0dc7cbd46cb346a9562ecf9ebd88` |
| Executed `run_campaign.py` | `4a3c53a31faff3f55d3d796e8a922758f60156f093560ca8e30d061c270a9b2e` |
| Candidate `analyze.py` | `fcbb84211b9f5db5cdbecb0da04406522e5141d1ae36f9e9229fc8ae59f79918` |
| Candidate `validate_receipts.py` | `741b508da019be6a483946baa35ddd90684fd24762ad0a8242ba48f0a7a7967a` |
| AArch64 binary | `4744bb740338745b475759c70289d09e607cafea1dbf2bee2bab7f92bd7ecc01` |
| `xxl` binary | `a38c402cb2059cdba82865794e1c7b791e6c1bf6f6afc72063e0be5068fff947` |

## Files

- `arm-results.tar.gz` contains the literal AArch64 target receipt.
- `xxl-results.tar.gz` contains the receipt from the runtime-resolved `xxl`
  target.
- `host-model-probes.txt` records the fresh Arm model-register and x86
  microcode probes after collection.
- `xxl-resolution.txt` records the Secure Shell alias resolution used for this
  run.
- `SHA256SUMS` records outer digests for every file in this directory.

Each host archive includes host and compiler data, build flags, execution-source
hashes, smoke outputs, the host-built binary and its hash, symbol addresses,
both kernel disassemblies, raw tab-separated rows, full process logs, the
pre-sealing host manifest, the sealed source archive, recomputed analyses,
`validation.json`, and a final internal `SHA256SUMS`.

Both `validation.json` files report `valid: true`, bind the source commit and
binary hash, and confirm 88 randomized plus 16 sequential rows. The raw
analyses also record zero timed faults, zero processor migrations, accepted
page-advice requests, and matching checksums for every measured process.
