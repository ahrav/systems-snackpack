# Measurement contract

Each glibc Linux record applies only to its named source commit, source archive,
ELF hashes, host, toolchain, flags, workload, CPU affinity, and run window.
An extracted Git archive has no index or parent tree, so its remote
`git-diff-check.log` records `not-applicable`. The source commit must pass
`git diff --check` before archiving as a separate local gate. Archive mode
requires the declared archive SHA-256; that digest and the before/after
per-file manifests bind the remote run to the extracted bytes.

The declared commit is not self-attesting, so check it against the retained
manifest rather than trusting the recorded value. The manifest reproduces
byte-exactly from the named commit:

```sh
tmp="$(mktemp -d)"
git archive <source_commit> | tar -x -C "$tmp"
(cd "$tmp" && rg --files -uu -g '!/.git/' -g '!/target/' -0 \
    | sort -z | xargs -0 sha256sum --) \
    | cmp - measurements/raw/<commit>/<host>/source-files.before.sha256
```

A declared commit that does not name the measured tree fails this comparison.
The retained archive digest identifies the transfer artifact only; the archive
itself is not retained, so that field carries no independent verification.

The primary treatment uses one lazy-linked ELF. `A` removes `LD_BIND_NOW`; `B`
sets `LD_BIND_NOW=1`. Each outcome contains 12 complete blocks. Even-numbered
blocks use `ABBA`; odd-numbered blocks use `BAAB`. Every letter launches a fresh
process, for 48 processes per outcome.

The block statistic is the log of the geometric `B/A` ratio. The point estimate
exponentiates the mean of 12 block contrasts. The interval exponentiates the
mean plus or minus the Student-t critical value times the block sample standard
deviation divided by the square root of 12.

`startup_ns` spans the parent-observed `subprocess.run` call, from immediately
before child creation through child exit. `first_use_ns` uses
`CLOCK_MONOTONIC_RAW` around one call to each generated import and excludes
pre-main work. `steady_ns` follows an untimed workload-sized warm-up in the same
child.

The interval covers block-to-block variation in one run window. It does not
cover independent builds, future load, other hosts, an ISA, or a vendor family.
The A/A control uses identical environments for both labels. The driver reports
its interval but does not enforce an acceptance threshold. Define that threshold
before interpreting the corresponding A/B outcome.

`LD_DEBUG` output is diagnostic and never wraps a retained benchmark sample.
The diagnostic child still emits its internal timer value; the analysis excludes
that value. The `now` and `noplt` executables are separate linked images; their
metadata and disassembly are structural evidence, not causal timing arms.
