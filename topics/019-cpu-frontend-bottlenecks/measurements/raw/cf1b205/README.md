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
commits fixed the generators, so seven recorded fields are stale. They fall into
three groups: defects 1, 5, and 7 are reporting or naming errors that can be
reinterpreted from the retained data, defects 2, 3, and 4 limit what the archives
can prove about provenance, and defect 6 limits only hash-level reproduction.

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
   `source-files.before.sha256` includes `rust-toolchain.toml`. But because
   `RUSTUP_TOOLCHAIN` was not swept (defect 3), and rustup honors it ahead of
   `rust-toolchain.toml`, these archives cannot establish which compiler ran the
   gates. Treat the recorded `rustc`/`cargo`/`target_cfg` blocks as the caller's
   default toolchain, and the gate toolchain as unproven. The C toolchain,
   kernel, and CPU blocks are unaffected.
3. **`swept_environment=none` is weaker than it looks.** The sweep at the time
   covered a narrower set than the current one, which now also clears the
   `CARGO_TARGET_*` and encoded Cargo flag variables, the rustc/rustfmt wrapper
   and tool overrides, the rustup toolchain override, the GCC implicit
   search-path and subprogram variables, and the Python import-path variables,
   and additionally rejects ancestor Cargo configuration files. `none` means no
   *then-swept* variable was set; it does not establish that any of the
   later-added overrides were absent.

   It also cannot rule out `RIPGREP_CONFIG_PATH`. The archived runner built both
   source manifests with a bare `rg --files`, and ripgrep reads that
   configuration file unless `--no-config` is passed, so `--glob` entries in it
   could have excluded paths from the before and after manifests identically. The
   comparison between them would still succeed while both omitted source that
   Cargo or Python compiled, so treat manifest *completeness* as resting on the
   same assumption as the rest of this entry. Current runs pass `--no-config` at
   every call site and clear the variable.
4. **Source manifests include ignored paths.** `source-files.before.sha256` and
   `source-files.after.sha256` were produced with an unrestricted scan, so
   ignored files present at run time would be hashed and attributed to
   `source_commit`. In checkout mode the manifest is now restricted to tracked
   files. The before/after comparison that proves the source did not change
   mid-run remains valid either way.

   Separately, and by design rather than by defect: in archive mode
   `source_commit` and `source_archive_sha256` are values the caller declared,
   which is why `host.txt` records
   `source_commit_verification=declared-archive`. Nothing in the runner verifies
   that the extracted tree corresponds to them. Current runs additionally record a
   `source_tree_digest` computed over the before-manifest, which is an identity
   for the bytes that were actually compiled and is the value to compare between
   runs; these archives predate it, so their per-file manifest is the only such
   record.
5. **PMU rows name the wrong perf timing field.** Every row in
   `experiment/perf/*.status.json` and `experiment/perf-summary.json` records
   the counter's running time under `time_enabled_ns`. `perf stat -x` places the
   *run time of counter* in that column, so the key is now `time_running_ns`.
   The recorded numbers are correct: every retained group reports
   `percent_running` of 100, where running time equals enabled time. Read those
   values as running time. For a multiplexed group they would have differed, and
   enabled time is recoverable as `time_running_ns / (percent_running / 100)`.
6. **The ELF hashes are not reproducible.** `artifact-identity.txt` records
   SHA-256 sums for `dense16` and `sparse4096` that were produced without a
   debug-prefix map. With `-g`, GCC embeds the absolute generated-source path,
   which lived under a fresh `mktemp` directory, so rebuilding the same generated
   C from a different scratch directory yields different ELF bytes and therefore
   a different hash. The builds now pass `-ffile-prefix-map` to a fixed
   placeholder, which makes the bytes identical across scratch directories, but
   these retained hashes cannot be reproduced from the recorded source and
   command line. The symbol addresses, sizes, spacing, and disassembly in the
   archives remain valid descriptions of the binaries that were measured.
7. **`interval_scope` describes the wrong kind of interval.**
   `experiment/summary.json` records the scope as "complete-block variation in
   this host, binary, workload, and single run window". The value is computed as
   `mean_log ± t · sd_log / √12` and exponentiated, which is a confidence
   interval for the geometric-mean ratio from between-block dispersion, not an
   interval covering what an individual block does -- a prediction interval would
   be roughly 3.5× wider here. The field now says so, and the narrative documents
   were corrected alongside it. The recorded bounds themselves are correct for the
   statistic that was computed; only the description of that statistic was wrong.

Defects 1, 5, and 7 are reporting and naming errors, and each can be recomputed
or reinterpreted from data the archives already contain: defect 1 from the
retained per-symbol sizes, defect 5 by reading `time_enabled_ns` as running time,
defect 7 by reading the interval as a confidence interval for the mean ratio. The
timing records, PMU counts, `percent_running` values, ELF metadata, and
disassembly are unaffected by those three. Defect 6 limits only hash-level
reproduction of the two binaries, not what was measured from them.

Defects 2, 3, and 4 are different in kind, and limit what the measurements
themselves prove. The recorded Rust toolchain is not the one that validated the
workspace, and because `RUSTUP_TOOLCHAIN` was not swept the gate toolchain cannot
be established at all. Because the narrower sweep cannot establish that the GCC
search-path, Python import-path, Cargo flag, or rustup override variables were
unset, because the Git repository-location variables (`GIT_DIR`,
`GIT_WORK_TREE`, `GIT_INDEX_FILE`) were not cleared before the Git probes, because
shell functions and aliases imported from the environment were not rejected, and
because ancestor Cargo configuration was not rejected, these archives cannot rule
out that a caller-supplied header, compiler subprogram, rustc flag, Python
module, tool wrapper, or alternate Git repository influenced the compiled
binaries, the recorded `source_commit`, or the evidence writer. Nothing retained
suggests that happened, and the recorded command lines, source hashes, and ELF
metadata are self-consistent, but the archives cannot exclude it. Treat the
measurements as reproducible only under the recorded source and command lines
plus the assumption that no such override was present.

