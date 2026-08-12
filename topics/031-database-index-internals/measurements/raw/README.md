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

The archives were then repacked to drop the macOS AppleDouble sidecar files
(`._*`) that the retrieval host added. Those sidecars carried extended
attributes rather than measurement bytes, and no internal manifest listed them,
so each archive held 40 files that its own `SHA256SUMS` did not cover. Every
remaining file is byte-identical: each internal manifest verified before the
repack and verifies after it, and each archive now holds exactly its 35 listed
files plus the manifest itself. The outer manifest was regenerated for the
repacked archives.

The archives are evidence for their named source commit only. They are not
evidence for later documentation or code changes.
