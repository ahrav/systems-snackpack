# Raw evidence

Each dated source directory binds two compressed host bundles to one archived
Git commit and its SHA-256 digest. Each bundle retains that source archive, the
exact executable, and every process output.

To revalidate a bundle, extract it and its embedded `source.tar.gz`. Run the
archived
`topics/044-tail-latency-histogram-merge-errors/experiment/validate_receipts.py`
against the bundle directory. Pass the recorded identity through
`--expected-label` and `--expected-resolved-host`. The validator recomputes the
eight-process, source-integrity, and generated-file digest contract.
