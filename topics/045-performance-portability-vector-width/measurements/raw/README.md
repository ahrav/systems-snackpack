# Raw receipt layout

Each retained run directory contains the exact source archive plus one untouched
host bundle per required target. A host bundle contains:

- source commit, archive digest, pre-run manifest, post-run manifest, and their
  empty diffs;
- target label, resolved and runtime hostname, architecture, CPU topology,
  kernel, compiler versions, features, affinity, and selected CPU;
- crate tests, C build command, correctness output, supported modes, and binary
  digest;
- full disassembly, per-kernel disassembly, symbols, and a machine-checked width
  inspection;
- every process attempt, every complete-block contrast, summaries, and the
  independent validation result.

Process logs preserve nonzero exits, invalid output, placement mismatches, and
counter failures. A failed bundle records an attempted run but cannot support a
published measurement claim.
