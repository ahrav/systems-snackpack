# Raw evidence archives

Each directory is named for the measured source commit's short identifier. The
outer `SHA256SUMS` manifest verifies archives after retrieval. Each archive also
contains the host runner's sealed manifest, process records, summaries,
generated code, binaries, host metadata, and gate logs.

The retrieved archives were compacted by removing the duplicated 296 mebibyte
source snapshot. The retained `source_identity.txt` and `run.status` files
record that snapshot's Secure Hash Algorithm 256-bit (SHA-256) digest. The
internal manifests were regenerated and checked after compaction; the outer
manifest covers the resulting archives.

The archives are evidence for their named source commit only. They are not
evidence for later documentation or code changes.
