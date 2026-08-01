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

## Known reporting defects in these archives

These archives are the original `cf1b205` outputs and are **not** regenerated:
the hashes above pin them, and re-running requires both original hosts. Later
commits fixed the generators, so five recorded fields are stale. The defects are
in derived reporting and field naming, not in the measured values.

1. **`code_size_equal` overstates its scope.** `experiment/layout.json` and
   `experiment/summary.json` record `code_size_equal=true`, but the check behind
   it only compared leaf symbols. The alignment treatment moved non-leaf code
   generation on AArch64: the same records show `run_rounds` at 116 bytes dense
   and 112 sparse (x86-64 stayed at 77/77). The field is now split into
   `leaf_code_size_equal` and a computed `run_rounds_size_equal`. The per-symbol
   sizes in these archives are correct and show the difference directly.
2. **`host.txt` names the wrong Rust toolchain.** The `rustc`, `cargo`, and
   `target_cfg` probes ran in the caller's directory instead of the repository
   root, so they recorded the host default rather than the pinned toolchain:
   `1.97.1` for `xxl` and `1.95.0` for `alg`, while the source pins `1.93.1`.
   The Cargo gates did run from the repository root, and
   `source-files.before.sha256` includes `rust-toolchain.toml`, so the gates
   resolved `1.93.1`. Treat the recorded `rustc`/`cargo`/`target_cfg` blocks as
   describing the caller's default toolchain, not the one that validated the
   workspace. The C toolchain, kernel, and CPU blocks are unaffected.
3. **`swept_environment=none` is weaker than it looks.** The sweep predated
   clearing `RUSTUP_TOOLCHAIN`, `RUSTFMT`, `RUSTC_WRAPPER`,
   `RUSTC_WORKSPACE_WRAPPER`, and `CARGO_ENCODED_RUSTFLAGS`, and the GCC
   implicit search-path and subprogram variables (`CPATH`, `C_INCLUDE_PATH`,
   `CPLUS_INCLUDE_PATH`, `OBJC_INCLUDE_PATH`, `LIBRARY_PATH`, `COMPILER_PATH`,
   `GCC_EXEC_PREFIX`). `none` means no *then-swept* variable was set; it does
   not establish that these overrides were absent.
4. **Source manifests include ignored paths.** `source-files.before.sha256` and
   `source-files.after.sha256` were produced with an unrestricted scan, so
   ignored files present at run time would be hashed and attributed to
   `source_commit`. In checkout mode the manifest is now restricted to tracked
   files. The before/after comparison that proves the source did not change
   mid-run remains valid either way.
5. **PMU rows name the wrong perf timing field.** Every row in
   `experiment/perf/*.status.json` and `experiment/perf-summary.json` records
   the counter's running time under `time_enabled_ns`. `perf stat -x` places the
   *run time of counter* in that column, so the key is now `time_running_ns`.
   The recorded numbers are correct: every retained group reports
   `percent_running` of 100, where running time equals enabled time. Read those
   values as running time. For a multiplexed group they would have differed, and
   enabled time is recoverable as `time_running_ns / (percent_running / 100)`.

The timing records, PMU counts and `percent_running` values, ELF metadata, and
disassembly are unaffected. Defect 5 is a key name only, and defect 1 can be
recomputed from the per-symbol sizes the archives already contain.

