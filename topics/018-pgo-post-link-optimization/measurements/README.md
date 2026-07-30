# Measurement contract

The retained runs are:

- [Linux AArch64, 2026-07-28](2026-07-28-linux-aarch64.md);
- [Linux x86-64, 2026-07-28](2026-07-28-linux-x86-64.md);
- [cross-host interpretation](2026-07-28-linux-cross-host.md).

Each record applies only to its named source commit, archive digest, binaries,
host, toolchain, target features, build flags, inputs, CPU affinity, run window,
and retained raw process rows.

Both retained host runs declare source commit `aa3e0fe`. They ran in archive mode, so
that commit is a sender declaration rather than something either host verified — see the
archive-mode note below — and the wrapper at that commit predates the current
caller-isolation hardening. Every measured row in the two host records therefore carries
the [pre-hardening caveat](2026-07-28-linux-cross-host.md) recorded with the launch
command. The cross-host file is their joint interpretation and reports no rows of its own.

## Experimental unit

Each comparison contains six `ABBA` and six `BAAB` blocks scheduled by a fixed,
recorded shuffle seed. Every block launches four fresh processes and contains
two observations per binary. The driver also shuffles comparison order within
each block. The ratio direction is `right/left`, as recorded in
`experiment.json` and `summary.csv`.

For a steady-state comparison, `elapsed_ns` spans only the loop inside
`pgo_probe`; it excludes process launch and argument parsing. The parent
`process_wall_ns` spans `subprocess.run`, including child creation, program
startup, the workload, output, and exit. A `noop` comparison reports only the
parent-observed process interval because its internal elapsed value is zero.

Each block contrast subtracts the mean log duration of its two left-arm
processes from the mean log duration of its two right-arm processes. The point
estimate is the geometric mean of the 12 block ratios. The two-sided 95%
Student-t interval uses the sample standard deviation among those 12 log
contrasts. It covers process-block variation within one host and run window. It
does not cover independent builds, later load, other hosts, an ISA, or a vendor
family. The 20,000,000 loop iterations and four positions inside a block are not
independent samples. The interval treats block contrasts as independent; the
retained lag-one log-ratio correlation is a serial-dependence diagnostic, not
proof of independence.

One discarded warm-up runs each binary for each comparison. The driver trains
each profile in one separate process with training seed `1`, then measures with
seed `2`. Training iterations produce the profile and do not count as timing
replicates.

## Retained evidence

The remote wrapper writes all evidence outside the source tree:

- `host.txt` records `uname`, CPU identity, CPU count, affinity, kernel,
  workspace and experiment toolchains, native Rust target configurations, and
  available post-link tools;
- `gates/` retains every repository and script validation log. A run executes the
  gates from an empty environment with the repository toolchain's own binaries
  first, a scratch `CARGO_HOME`, a scratch target directory, and no Cargo
  configuration above the snapshot. The retained logs below predate that
  isolation: their wrapper removed only `RUSTUP_TOOLCHAIN`, so they record a gate
  result obtained under whatever Cargo environment and configuration the operator
  had, not one established against the pinned source and toolchain alone;
- `source-files.before.sha256` and `source-files.after.sha256` prove that the
  included non-`.git`, non-`target` file bytes did not change;
- `source-files.commit.sha256` appears only for a checkout run, where it carries
  the manifest rebuilt from `git archive <source_commit>`; the run aborts unless
  it equals `source-files.origin.sha256`, which is what ties a checkout tree to
  its commit rather than to a clean `git status`;
- `source-files.archive.sha256` is the archive-mode counterpart, carrying the
  manifest rebuilt from the extracted `SOURCE_ARCHIVE_PATH`; it ties the measured
  tree to the archive whose digest is retained, which the two independent digest
  comparisons alone do not establish. It is absent from the retained runs below,
  which predate the check;
- `source-provenance.txt` records the verified archive and extracted-manifest
  identities and the immutable source snapshot used by every build and
  non-Git gate, plus the selected experiment Rust toolchain;
- `process.log` retains the complete driver output;
- `experiment/raw.csv` retains every completed timed process, any failed
  attempt, block order, checksum, and both clocks. A run gives each timed
  process a fixed empty environment, recorded as `probe_environment` in
  `experiment.json`, because `execve` copies the environment and the loader walks
  it, so an inherited `PATH` sits inside `process_wall_ns`. The retained runs
  below predate that and carry no `probe_environment` field: their
  `process_wall_ns` and `noop` rows include the launching environment's startup
  cost, so those values compare within their own run rather than across runs or
  hosts. The in-process `elapsed_ns` rows are unaffected;
- `experiment/summary.csv` and `experiment/experiment.json` retain point
  estimates, dispersion, intervals, and experiment parameters;
- `experiment/correctness.json` and `experiment/discarded-warmups.json` retain
  correctness checks and excluded warm-ups;
- `experiment/*-dispatch.txt`, `experiment/codegen-verification.json`, and
  `experiment/symbol-layout.txt` retain observed final code generation, checked
  call forms, and symbol addresses;
- `experiment/profiles/`, `experiment/profile-artifacts.json`, and
  `experiment/*-profile-summary.txt` retain the raw and merged profiles plus
  their hashes;
- `experiment/*-pgo-build.log`, `experiment/tool-versions.json`, and
  `experiment/build-commands.txt` retain compiler diagnostics, matching tool
  versions, linker-driver and linker versions, and invocations. A run records
  each command with the environment assignments that decide its result,
  including `RUSTUP_TOOLCHAIN` and `LLVM_PROFILE_FILE`, so the entry is a
  complete account of what executed. It is a log, not a runnable script: the
  commands name absolute paths inside the snapshot and work directories, and the
  wrapper deletes that scratch tree on exit, so replaying one requires
  reconstructing those paths. The retained transcripts below additionally
  predate the assignment recording, so they omit the profile destination and the
  toolchain selection as well;
- `experiment/tool-versions.json` distinguishes the linker driver (`cc`), the
  `ld` found on `PATH` (`ld_on_path`), and the toolchain's bundled `rust-lld`
  (`rust_lld`, `rust_lld_path`), because rustc may hand the link to the bundled
  linker rather than the one on `PATH`. The retained runs below record only
  `ld`, which named the `PATH` tool; their x86-64 build logs show `rust-lld`
  performed the link;
- `experiment/binary-sha256.before.json` and
  `experiment/binary-sha256.json` bind inspection and measurement to unchanged
  binaries and prove that the identity-control copy has the baseline hash. The
  builds pass `--remap-path-prefix` for the snapshot and work directories, so
  these digests depend on the source, toolchain, and flags rather than on the
  scratch paths a run happens to receive. The retained runs below predate that
  flag, so their digests still carry their own scratch paths and compare only
  within their run;
- `experiment/post-link-tools.json` records BOLT and `perf` tool availability;
- `evidence.sha256` covers the retained evidence files of the run that wrote it,
  which is the files under that run's own directory. `raw/aa3e0fe/host-resolution.txt`
  sits beside those directories and is therefore in neither manifest, so the host
  records cite a receipt that neither advertised verification covers; read it as an
  operator note rather than as authenticated evidence.

For an extracted Git archive, `SOURCE_COMMIT`, `SOURCE_ARCHIVE_PATH`,
`SOURCE_ARCHIVE_SHA256`, and `SOURCE_MANIFEST_SHA256` are required. The wrapper
hashes the transferred archive and the extracted per-file manifest before any
build. The archive has no Git index or parent tree, so its remote
`git-diff-check.log` records `not-applicable`.

Run this from an environment the sender controls, not an inherited one. The receiver
can verify the archive and manifest against the digests it is given, but it can never
recompute `git archive <source_commit>` — it has no object store — so a caller-supplied
`git`, `tar`, or `sha256sum` here produces a self-consistent handoff for bytes that are
not the committed ones, and nothing downstream can detect it. Name the programs by
absolute path or start from a `PATH` chosen for this purpose, for the same reason the
wrapper is launched that way. Order matters: the system directories come first so that
`git`, `tar`, `sha256sum`, `sort`, `xargs`, and `sh` resolve from them, and the
user-writable Cargo directory comes last because `rg` normally lives there and nothing
else in this recipe should. Adjust the directories to this host. `set -euo pipefail`
so that a failing proof stops the recipe: without it an interactive shell carries on
past a mismatched `diff` and prints digests a receiver would accept, and the receiver
cannot recheck the commit binding those digests are standing in for:

```bash
set -euo pipefail
# Refuse an inherited loader or libc namespace before running anything. `LD_PRELOAD`
# and `LD_AUDIT` interpose on every process below, including the `git` that produces
# the archive and the `git`, `tar`, `rg`, and `sha256sum` that prove it matches the
# commit — so a preload can forge an archive and a manifest that agree with each
# other. The receiver refuses these variables for its own run, but archive mode can
# only take the commit-to-bytes binding on the sender's word, so this is the one place
# it can be established. `GLIBC_TUNABLES` and the `MALLOC_*` knobs are swept for the
# same reason the wrapper sweeps them. Refuse rather than clear: a value here means
# something already chose it, and that choice is not recorded anywhere.
for loader_variable in $(env | sed -n 's/^\(LD_[A-Z_]*\|GLIBC_[A-Z_]*\|MALLOC_[A-Z_]*\)=.*/\1/p'); do
  printf 'loader environment must be unset for the handoff proof: %s\n' \
    "$loader_variable" >&2
  exit 2
done
# Start Bash privileged for the same reason the wrapper does: privileged mode does not
# process `BASH_ENV` or `ENV` and does not import the caller's shell functions, and an
# imported `git` or `command` function answers ahead of the program and can forge
# `archive`, `rev-parse`, and `ls-tree` output. Run this recipe as
# `bash -p handoff.sh`, not by pasting it into an interactive shell.
[[ -o privileged ]] || { printf 'run this recipe with bash -p\n' >&2; exit 2; }
export PATH="/usr/bin:/bin:$HOME/.cargo/bin"
archive=/tmp/topic18-source.tar
scratch="$(mktemp -d)"
unset TAR_OPTIONS
# Clear Git's local repository environment before any command below. `GIT_DIR`,
# `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY`, `GIT_INDEX_FILE`, and the rest of
# `git rev-parse --local-env-vars` redirect both the archive and the `ls-tree`
# proof to another object store, so the two would agree with each other while
# describing a commit that is not the checkout being handed off. The receiver
# refuses these variables, but it can never recheck the commit-to-bytes binding
# established here, so this is the only place it can be got right.
unset $(git rev-parse --local-env-vars)
GIT_NO_REPLACE_OBJECTS=1 git -c tar.umask=0 archive \
  --format=tar --output="$archive" <source_commit>
# `--same-permissions` because ordinary-user extraction applies the umask, which
# would strip the executable bits that `git archive -c tar.umask=0` just
# preserved. The proof below derives `100755` from `-x`, so a sender umask such as
# `0111` would otherwise make a correct archive fail this comparison.
tar --same-permissions -xf "$archive" -C "$scratch"
# The archive must be the whole commit, byte for byte, with its modes.
# `export-ignore` omits paths and `export-subst` rewrites contents, from a
# tracked `.gitattributes` or from the sender-local `$GIT_DIR/info/attributes`,
# and repacking an extracted tree can store an executable as `0644` — while the
# manifest is computed from the filtered, substituted, or repacked tarball. The
# receiver can only compare the measured tree against the archive, never back to
# <source_commit>, so this is the only place those three are checkable. Compare
# mode, blob identity, and path against the object database, which no archive
# attribute touches, with replace refs disabled on both sides. The mode column
# assumes the tree holds no symlinks; `git ls-tree -r` reporting any `120000`
# entry means this comparison needs extending before it can be trusted.
# `--no-filters` because a `filter.<driver>.clean` command selected by tracked
# `.gitattributes` or by the sender-local `$GIT_DIR/info/attributes` otherwise runs
# during this hash, and the comparison would then be between the filtered result and
# the commit blob rather than between the archived bytes and the commit blob.
LC_ALL=C diff \
  <(GIT_NO_REPLACE_OBJECTS=1 git ls-tree -r \
      --format='%(objectmode) %(objectname) %(path)' <source_commit> \
      | LC_ALL=C sort) \
  <(cd "$scratch" && rg --no-config --files -uu -g '!.git/' -g '!.git' \
      -g '!target/' -0 \
      | xargs -0 -n1 sh -c \
          'if [ -x "$0" ]; then mode=100755; else mode=100644; fi
           printf "%s %s %s\n" "$mode" \
             "$(GIT_NO_REPLACE_OBJECTS=1 git hash-object --no-filters -- "$0")" "$0"' \
      | LC_ALL=C sort)
(cd "$scratch" && rg --no-config --files -uu -g '!.git/' -g '!.git' -g '!target/' -0 \
  | LC_ALL=C sort -z | xargs -0 sha256sum --) > /tmp/topic18-source-files.sha256
sha256sum "$archive" /tmp/topic18-source-files.sha256
```

The retained archive and manifest digests bind the transferred archive and
extracted bytes to the source-candidate receipts. A run also rebuilds the
manifest from the extracted archive, so the measured tree is tied to the archive
rather than only to its own declared digest; the retained runs below predate that
check and retain no `source-files.archive.sha256`, so for them the archive digest
and the tree manifest remain two independent comparisons. They do not bind those
bytes to the commit id: an extracted archive carries no object store, so the
receiving host cannot recompute `git archive <source_commit>`. In archive mode
`source_commit` is therefore a sender declaration, and
`source_commit_verification=verified-archive-and-manifest` names the archive and
manifest digests it does verify. A checkout run establishes the commit directly
and additionally rejects any tree that does not reproduce from it.

## Measured and inferred claims

Elapsed clocks, process orders, checksums, compiler output, binary hashes,
profile summaries, symbol addresses, instruction text, host identity, CPU model,
and tool availability are measured or directly observed. The experiment does
not measure branch-misprediction cost, instruction-cache pressure, optimizer
pass attribution, BOLT benefit, or a production workload distribution.

A guarded direct call in `pgo-alpha` establishes profile-conditioned code
generation for that compiler and binary. It does not prove that the guard caused
a timing ratio. A host-specific timing result does not generalize to its
architecture or CPU vendor. Explain any mechanism as an inference and name the
additional counter, trace, or perturbation required to test it.
