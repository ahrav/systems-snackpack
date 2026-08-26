# Source identity

- Commit: `e4fb542f6640566f8f7fbcd220eb1f52c388df04`.
- Git archive prefix: `systems-snackpack-e4fb542f/`.
- Archive SHA-256:
  `f0b8c64c9cacfb27314ae7e4ac90102c6ec9709a03e4b2ded759209a3eb0385b`.
- Archive size: 351,645,818 bytes.
- Runner path:
  `topics/046-cache-coherence-false-sharing/experiment/run_host.sh`.

Each host verified the archive digest, embedded Git commit, archived runner,
source manifest before and after execution, runner hash, and measured binary
hash. Each sealed host bundle contains the full process attempt stream,
disassembly, validation receipt, and an evidence manifest.

The host bundles omit their duplicate copy of the 351-megabyte Git archive. The
archive includes historic raw curriculum evidence already present in the Git
commit. The commit, archive prefix, exact digest, byte count, and the original
archive's digest in each host evidence manifest bind the retained results
without adding three more copies of that corpus to this repository.
