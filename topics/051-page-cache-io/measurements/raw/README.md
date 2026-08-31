# Raw receipt layout

Keep full host receipts outside Git. Each sealed receipt contains:

```text
host.json
source-archive.tar.gz
source-manifest-before.sha256
source-manifest-after.sha256
source-manifest.diff
source-files.sha256
build/
bin/
codegen/
controls/
campaign/
cleanup.json
receipt-validation.json
MANIFEST.sha256
SEALED
```

The `campaign` directory contains the fixed schedule, append-only attempt journal, attempt index, raw standard output and error, per-attempt status, completion marker, and independent summary for each scenario. Inner 4 KiB reads are subsamples inside one process. A complete four-process block is the analysis unit.

Before deleting a remote receipt, retrieve it, verify `MANIFEST.sha256`, archive it, record the archive SHA-256 digest, and run `validate_receipts.py` locally. Remove only task-owned exact paths. Do not remove a path whose ownership or retrieval state is unclear.
