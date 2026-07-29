# Measurement contract

The retained runs are:

- [Linux AArch64, 2026-07-28](2026-07-28-linux-aarch64.md);
- [Linux x86-64, 2026-07-28](2026-07-28-linux-x86-64.md);
- [cross-host interpretation](2026-07-28-linux-cross-host.md).

Each record applies only to its named source commit, archive digest, binaries,
host, toolchain, target features, build flags, inputs, CPU affinity, run window,
and retained raw process rows.

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
- `gates/` retains every repository and script validation log;
- `source-files.before.sha256` and `source-files.after.sha256` prove that the
  included non-`.git`, non-`target` file bytes did not change;
- `source-files.commit.sha256` appears only for a checkout run, where it carries
  the manifest rebuilt from `git archive <source_commit>`; the run aborts unless
  it equals `source-files.origin.sha256`, which is what ties a checkout tree to
  its commit rather than to a clean `git status`;
- `source-provenance.txt` records the verified archive and extracted-manifest
  identities and the immutable source snapshot used by every build and
  non-Git gate, plus the selected experiment Rust toolchain;
- `process.log` retains the complete driver output;
- `experiment/raw.csv` retains every completed timed process, any failed
  attempt, block order, checksum, and both clocks;
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
  versions, linker-driver and linker versions, and invocations;
- `experiment/binary-sha256.before.json` and
  `experiment/binary-sha256.json` bind inspection and measurement to unchanged
  binaries and prove that the identity-control copy has the baseline hash;
- `experiment/post-link-tools.json` records BOLT and `perf` tool availability;
- `evidence.sha256` covers the retained evidence files.

For an extracted Git archive, `SOURCE_COMMIT`, `SOURCE_ARCHIVE_PATH`,
`SOURCE_ARCHIVE_SHA256`, and `SOURCE_MANIFEST_SHA256` are required. The wrapper
hashes the transferred archive and the extracted per-file manifest before any
build. The archive has no Git index or parent tree, so its remote
`git-diff-check.log` records `not-applicable`.

```bash
archive=/tmp/topic18-source.tar
scratch="$(mktemp -d)"
git archive --format=tar --output="$archive" <source_commit>
tar -xf "$archive" -C "$scratch"
(cd "$scratch" && rg --files -uu -g '!.git/' -g '!.git' -g '!target/' -0 \
  | LC_ALL=C sort -z | xargs -0 sha256sum --) > /tmp/topic18-source-files.sha256
sha256sum "$archive" /tmp/topic18-source-files.sha256
```

The retained archive and manifest digests bind the transferred archive and
extracted bytes to the source-candidate receipts. They do not bind those bytes
to the commit id: an extracted archive carries no object store, so the receiving
host cannot recompute `git archive <source_commit>`. In archive mode
`source_commit` is therefore a sender declaration, and
`source_commit_verification=verified-archive-and-manifest` names the archive and
manifest digests it does verify. A checkout run establishes the commit directly
and additionally rejects any scanned file absent from `git ls-files`.

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
