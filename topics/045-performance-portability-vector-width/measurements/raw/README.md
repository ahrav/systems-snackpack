# Raw receipt layout

Each retained run directory contains the exact source archive plus one untouched
host bundle per required target. A host bundle contains:

- source commit, archive digest, pre-run manifest, post-run manifest, and their
  empty diffs;
- target label, resolved and runtime hostname, architecture, central processing
  unit (CPU) topology, kernel, compiler versions, features, affinity, and
  selected CPU;
- crate tests, C build command, correctness output, supported modes, and binary
  digest;
- full disassembly, per-kernel disassembly, symbols, and a machine-checked width
  inspection;
- every process attempt, every complete-block contrast, summaries, and the
  independent validation result.

Process logs preserve nonzero exits, invalid output, placement mismatches, and
counter failures. A failed bundle records an attempted run but cannot support a
published measurement claim.

Before extraction, reject absolute paths, `..` components, duplicate members,
unsupported member types, and unexpected archive roots. Then run the
`validate_receipts.py` script extracted from the retained `source.tar.gz`
against each host bundle, passing the recorded source commit, archive digest,
target label, and resolved hostname. Its output must be byte-identical to the
corresponding host-side `receipt-validation.json`.

The retained 2026-08-24 run is in
[`2026-08-24-edc75b26/`](2026-08-24-edc75b26/). Its `SHA256SUMS` checksum
manifest binds the source archive, both untouched host bundles, fresh
target-resolution records, the Arm model supplement, and both independent
validation reports.
