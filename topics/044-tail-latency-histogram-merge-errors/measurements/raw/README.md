# Raw evidence

Each dated source directory binds two compressed host bundles to one archived
Git commit and its SHA-256 digest. Each bundle retains that source archive, the
exact executable, and every process output. Extract a bundle and run
`experiment/validate_receipts.py` with its recorded target label and resolved
hostname to recompute the eight-process, source-integrity, and generated-file
digest contract.
