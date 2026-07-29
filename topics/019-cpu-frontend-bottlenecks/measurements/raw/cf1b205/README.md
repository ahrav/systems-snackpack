# Raw evidence archives

Both archives contain the unmodified output from `run_remote.sh`, including
host identity, toolchain, native target flags, build commands, gate logs,
source manifests, ELF metadata, compressed disassembly, 96 timing-process
records, timing CSV files, PMU attempt records, and summaries.

| Runtime alias | Evidence archive SHA-256 |
|---|---|
| `xxl` | `cb39834890ad443808bf1974bbcf0dada212fb4201e42d550f867f5d67c2ca61` |
| `alg` | `a720437f49a50097265f2d740ad860baf86f4c81f9232bef5c25b5c91145ba8a` |

Both runs used source commit
`cf1b205058a6985eac98dc70ef1b2ff1e35370c2` and source archive SHA-256
`717e59c0dc7284bbeb8749da6229d96004417acdcef79e9619cb36cfc9d52a21`.

Verify and extract:

```sh
sha256sum xxl-evidence.tar.gz alg-evidence.tar.gz
mkdir xxl alg
tar -xzf xxl-evidence.tar.gz -C xxl
tar -xzf alg-evidence.tar.gz -C alg
```

Each extracted archive contains `evidence/evidence.sha256`. That manifest hashes
every retained file present before the manifest itself was installed.
