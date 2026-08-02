# Experiment

`run_processes.py` executes the fixed-size, seed-recorded schedule and rejects
malformed, missing, or partial results. It flushes `attempts.csv` after every
process, then writes `raw.csv` and `summary.json` after a complete run.

`run_remote.sh` validates a clean checkout or a Git archive whose SHA-256 digest
the caller supplies and whose embedded commit id and extracted tree both match,
records the host and toolchain, runs every workspace gate, builds the native
probe with `-C target-cpu=native -C lto=no -C codegen-units=1`, captures both
walker bodies, runs executable smoke checks, executes the process schedule, and
verifies that the source manifest did not change. Rust unit tests are the
correctness gate.

Archive mode requires:

```bash
SOURCE_COMMIT=<40-hex-commit> \
SOURCE_ARCHIVE_SHA256=<64-hex-digest> \
SOURCE_ARCHIVE_PATH=/path/to/source.tar.gz \
topics/020-memory-level-parallelism/experiment/run_remote.sh \
  /path/to/extracted/source /outside/repository/evidence 0
```

In archive mode the caller-supplied `SOURCE_ARCHIVE_SHA256` is the trust root.
`git get-tar-commit-id` reads a pax global header comment that no digest inside
the archive covers, so the embedded commit id is a claim carried by
digest-verified bytes rather than independent proof. `host.txt` records which
root a run used as `source_trust_root`.

`TOPIC20_NODES` and `TOPIC20_LOADS` override the workload. The defaults are
`4194304` nodes, a 256 MiB working set, and `33554432` loads per process. Both
change the reported result; `summary.json` records the values a run used.

The output directory must be absent or empty and outside the source tree.
`evidence.sha256` covers every retained file except itself.

The wrapper records best-effort PMU smoke attempts with a structured usability
verdict. PMU smoke data is not paired with the timed comparison and cannot
support a mechanism claim. Review `codegen-one.txt` and `codegen-eight.txt`
before interpreting elapsed time; symbol presence alone is insufficient.
