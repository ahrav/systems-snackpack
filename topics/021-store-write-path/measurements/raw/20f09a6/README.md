# Retained raw evidence

`arm` and `xxl` contain the validated 128-process records, host inventory,
workspace-gate logs, focused and compressed full disassembly, source manifests,
binary metadata, and per-directory `retained.sha256` files for commit
`20f09a6ef066df02ba4a180cb04b06a96e4dc633`.

The executable binaries are not checked in. Their SHA-256 values and generated
code are retained. Each directory's checksum file covers every retained file
except itself. Generated text with tool-emitted trailing whitespace is retained
losslessly as a deterministic gzip stream so `git diff --check` remains clean.

Chain of custody: the runner sealed its original outputs in `evidence.sha256`.
Retention transformed some files (the gzip streams above) and dropped the
executable binaries, so that original manifest no longer matched and was not
retained; each directory's `retained.sha256` re-seals the retained set and
supersedes the runner's seal. Hashes of untransformed files are unchanged
between the two manifests.

The retained runs predate the runner's pinned-toolchain gate: the workspace
pins rustc 1.93.1, while `xxl` measured with rustc 1.97.1 and `arm` with
rustc 1.95.0, as recorded in each `host.txt`. The published intervals are
bound to those recorded toolchains, not to the pin.
