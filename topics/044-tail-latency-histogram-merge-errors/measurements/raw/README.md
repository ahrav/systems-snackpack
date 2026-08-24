# Raw evidence

Each dated source directory binds two compressed host bundles to one archived
Git commit and its SHA-256 digest. Each bundle retains that source archive, the
exact executable, and every process output.

To revalidate a bundle, extract it and run the current checked-in
`topics/044-tail-latency-histogram-merge-errors/experiment/validate_receipts.py`
against the bundle directory. Pass the recorded identity through
`--expected-label` and `--expected-resolved-host`. The checked-in validator is
the hardened one: it recomputes the eight-process, source-integrity, and
generated-file digest contract, and additionally seals every command receipt,
verifies artifact contents, and requires the host-side validation receipts.
The copy embedded in a bundle's `source.tar.gz` is the weaker revision that
ran on the host; do not use it for revalidation.
