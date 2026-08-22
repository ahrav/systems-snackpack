# Raw receipt layout

Each run directory contains the unchanged output from `experiment/run_host.sh`.
The retained `source-archive.tar.gz`, its embedded commit, and matching source
manifests bind the executing source to the archive SHA-256 digest. `host.txt`
records that identity with the requested target label, resolved hostname,
runtime hostname, architecture, kernel, affinity, toolchain, native build
flags, and available vulnerability strings.

The remaining required records are:

- `source-archive.tar.gz`, both source manifests, their empty diff,
  `correctness.txt`, `build.txt`, and `self-test.json`;
- `aa-processes.jsonl` and `aa-summary.json` for eight paired A/A blocks;
- `timing-processes.jsonl` and `timing-summary.json` for 24 three-process blocks;
- `codegen/` disassembly for the four stable symbols and its inspection result;
- `receipt-validation.json`, which recomputes both summaries and records the
  SHA-256 digest of every required input receipt.

Process logs preserve invalid output, nonzero exits, and timeouts. A failed
gate remains evidence about the attempted run, but it is not a publishable host
result.
