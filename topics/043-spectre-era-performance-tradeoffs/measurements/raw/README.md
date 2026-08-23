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
  `correctness.txt`, `build.txt`, `probe.sha256`, and `self-test.json`;
- `aa-processes.jsonl` and `aa-summary.json` for eight paired A/A blocks;
- `timing-processes.jsonl` and `timing-summary.json` for 24 three-process blocks;
- `codegen/` disassembly for the four stable symbols and its inspection result;
- `receipt-validation.json`, which recomputes both summaries and records the
  SHA-256 digest of every required input receipt.

The runner also retains `source-manifest-post-run.sha256` and its empty diff,
recomputed after every experiment and validation step.

Process logs preserve invalid output, nonzero exits, and timeouts. A failed
gate remains evidence about the attempted run, but it is not a publishable host
result.

## Provenance of the committed bundles

The committed `2026-08-22-977f78c` bundles were produced and validated by the
protocol embedded in their retained source archives (commit `977f78c`). That
protocol measures the mutable workspace binary, checks the source manifest
only before the run, and emits neither `probe.sha256` nor post-run manifests.
The current validator therefore does not certify these bundles; their
validation claims are scoped to the embedded protocol version. Publishing new
measurement claims requires regenerating host bundles with the current runner.
