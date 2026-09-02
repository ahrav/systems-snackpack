# Raw evidence policy

Do not commit full experiment logs, binaries, data files, disassembly dumps, or
host snapshots. They are large and noisy.

For each accepted run, retain a sealed receipt outside Git under the curriculum
evidence directory. Commit only a small manifest containing the exact source
commit, archive digest, receipt digest, uncompressed manifest digest, validator
result, and paths to the compact host and comparison records. The x86-64
bundle must also retain a controller-side record that names the `xxl` alias,
its runtime SSH configuration hostname, the answering host's canonical name,
architecture, and observation time.
