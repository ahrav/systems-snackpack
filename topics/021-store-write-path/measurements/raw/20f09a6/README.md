# Retained raw evidence

`arm` and `xxl` contain the validated 128-process records, host inventory,
workspace-gate logs, focused and compressed full disassembly, source manifests,
binary metadata, and per-directory `retained.sha256` files for commit
`20f09a6ef066df02ba4a180cb04b06a96e4dc633`.

The executable binaries are not checked in. Their SHA-256 values and generated
code are retained. Each directory's checksum file covers every retained file
except itself. Generated text with tool-emitted trailing whitespace is retained
losslessly as a deterministic gzip stream so `git diff --check` remains clean.
