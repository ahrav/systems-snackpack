# Raw receipt layout

Each host result archive contains the unchanged output from
`experiment/run_host.sh`. `host.txt` records the full source commit and archive
SHA-256 digest. Matching executing-tree and archive-tree manifests bind the
executing source to that retained archive. `host.txt` also records the requested
target label, resolved and runtime hostnames, architecture, kernel, selected
CPU, capture-process affinity, toolchain, native build flags, and available
vulnerability strings. The A/A and timing process records retain each
`taskset` command used to pin a measurement process.

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
