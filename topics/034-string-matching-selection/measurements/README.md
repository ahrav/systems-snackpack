# Measurement contract

This topic retains correctness, elapsed-time, process-order, and generated-code
evidence for three source-defined exact byte matchers.

## Required records

Each promoted host record names:

- the source commit and shared source-archive Secure Hash Algorithm 256-bit
  (SHA-256) digest;
- the Secure Shell (SSH) target, resolved hostname, architecture, kernel,
  central processing unit (CPU) identity, and available CPU count;
- Rust, Cargo, C compiler, binary-tools versions, reported target features,
  build flags, affinity, and binary digest;
- generic and native correctness outcomes;
- the frozen repetition map and deterministic schedule;
- every raw process row, exit status, and external wall time;
- 12 complete-block contrasts per candidate-versus-baseline family, case, and
  mode;
- four same-method schedule-check blocks, kept separate from those families;
- independent receipt-validation output; and
- linked symbols and disassembly for all three matchers.

## Interpretation

Elapsed time measures the exact executable, input, host, affinity, and run
window. The complete-block ratio compares methods inside that window. Its sample
standard deviation covers variation among complete block contrasts, not other
machines, compiler versions, corpora, or future runs. Inner repetitions do not
increase the independent run count.

Generated instructions establish linked code shape only. They do not prove
that one instruction caused a timing difference or that another compiler emits
the same shape. Host CPU model and feature flags are vendor evidence, not a
license to generalize the timing to an instruction-set architecture or vendor
family.

The probe's logical throughput counts bytes presented to the search API. It is
not physical memory traffic or memory bandwidth. The deterministic synthetic
cases expose mechanisms and traps; they do not represent a production workload
distribution.

Raw logs are stored as one compressed archive per required host. An outer
`SHA256SUMS` file verifies each retrieved archive.

## Retained exact-source result

Source commit `b8d7f88a25aede60fb589099239c771285450293` passed on both
required hosts:

- [Arm exact-source record](b8d7f88-arm.md)
- [`xxl` exact-source record](b8d7f88-xxl.md)
- [Two-host comparison](b8d7f88-comparison.md)
- [Raw archive hashes](raw/b8d7f88/SHA256SUMS)

### Source binding of the retained archives

Both archives were produced before the host runner checked the source tree
in-run, so their `source_identity.txt` carries the caller-supplied commit
without the `source_commit_verified` marker later runs record. The binding was
instead confirmed after the fact from the archives themselves: each
`results/source_manifest.before.sha256` matches the manifest recomputed at
`b8d7f88`, entry for entry and digest for digest. The single difference is the
local checkout's own `.git` pointer file, which the hosts' extracted trees did
not contain.

```bash
git worktree add --detach /tmp/t34-b8d7f88 b8d7f88
(cd /tmp/t34-b8d7f88 && rg --files --hidden -g '!target/**' -g '!.git/**' -0 |
    LC_ALL=C sort -z | xargs -0 sha256sum) >/tmp/t34-recomputed.sha256
mkdir -p /tmp/t34-xxl && tar -xzf \
    topics/034-string-matching-selection/measurements/raw/b8d7f88/topic34-b8d7f88-xxl-results.tar.gz \
    -C /tmp/t34-xxl
diff <(sort /tmp/t34-recomputed.sha256) \
    <(sort /tmp/t34-xxl/results/source_manifest.before.sha256)
```

The manifest covers every non-ignored file in the tree, so it constrains the
source more tightly than a `git rev-parse HEAD` comparison would. It also names
file contents rather than a commit object, so the check needs a tree with those
digests, not the `b8d7f88` commit specifically. That commit is an ancestor of
this branch and this repository merges topic branches with merge commits, which
keeps it reachable from `main` after the merge; verifying from a squashed copy
of the history means recovering the tree some other way first.
