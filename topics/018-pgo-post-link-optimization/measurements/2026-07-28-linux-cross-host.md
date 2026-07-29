# Linux cross-host note: 2026-07-28

Both current dev machines ran the same declared source commit, transferred archive,
extracted-file manifest, Rust source, compiler flags, training inputs, measurement
inputs, CPU-0 affinity, and process schedule. Both runs record
`source_commit_verification=verified-archive-and-manifest`, so what each host checked is
the archive and manifest digests it was given; neither can recompute
`git archive <source_commit>` from an extracted tree, and the commit id is a sender
declaration on both sides. The cross-host agreement below is therefore agreement about
the same archive bytes, which is what makes it a comparison of hosts rather than of
source. Each host independently
verified the archive, all 993 extracted source files, and every retained
file listed in `evidence.sha256`.

Both hosts ran this command after receiving and extracting the named archive:

```bash
SOURCE_COMMIT=aa3e0fe2872072f40d45a1dd211f5c69bf72dc65 \
SOURCE_ARCHIVE_PATH=/tmp/topic18-retained-aa3e0fe2872072f40d45a1dd211f5c69bf72dc65/source.tar \
SOURCE_ARCHIVE_SHA256=ac1b28886484c5927443309a58a7bac0fbb01fd1e9def498fd35081dc9a01b7c \
SOURCE_MANIFEST_SHA256=52844b8aeab140fdfeba14e6aaf96c005d1ec20460fc2ad876726aa918bc13fa \
bash /tmp/topic18-retained-aa3e0fe2872072f40d45a1dd211f5c69bf72dc65/source/topics/018-pgo-post-link-optimization/experiment/run_remote.sh \
  /tmp/topic18-retained-aa3e0fe2872072f40d45a1dd211f5c69bf72dc65/source \
  /tmp/topic18-retained-aa3e0fe2872072f40d45a1dd211f5c69bf72dc65/evidence
```

That command launched the wrapper with plain `bash`, and the wrapper at
`aa3e0fe` predates the current caller-isolation hardening: it did not start the
run in privileged mode, so an exported shell function or a `BASH_ENV` hook on
either host would have run before the first retained receipt and could have
answered the provenance commands. It also predates the `GIT_*` refusal and the
`tools.txt` receipt, so neither the repository environment nor the resolved paths
of `git`, `tar`, `rg`, and `sha256sum` are recorded for these runs. Nothing
indicates that happened — both hosts verified the archive, all 993 extracted
files, and every file in `evidence.sha256` — but the retained receipts cannot
exclude it, so read these rows as conditional on the two hosts having had no
startup hook, exported function, or `GIT_*` override set. Regenerating them with
the documented isolated launcher is what would remove the caveat rather than
narrow it.

At the `2026-07-28T15:03:24Z` probe, the requested historical x86 hostname,
`dev-dsk-ahrav-2c-b89a08b3.us-west-2.amazon.com`, returned a WSSH 403 because
it no longer resolved. The current `xlg` alias resolved to
`dev-dsk-ahrav-2c-a9191cb6.us-west-2.amazon.com`; that canonical host was probed
as x86-64 and ran the experiment. The AArch64 hostname remained
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`. The
[resolution receipt](raw/aa3e0fe/host-resolution.txt) scopes this mapping to
that probe.

Alpha-trained PGO / baseline on the alpha workload measured 1.01187 on the
probed AArch64 host and 1.11151 on the probed x86-64 host. On the beta workload,
the same comparison measured 1.01077 and 1.14762. Each estimate uses 12
balanced process blocks and 48 fresh processes. Host-specific records report
the intervals and separate parent-process observations.

The candidate-to-candidate comparison differed. Neither workload resolved
alpha-trained from beta-trained PGO on the AArch64 host. On the x86-64 host,
each profile's candidate was faster on its own training workload relative to
the other PGO candidate. This is direct evidence that profile choice affected
the resulting binaries and their relative elapsed times in that run.

Both baselines retained an indirect dispatch. Both compilers emitted a guarded
direct call to the trained target plus an indirect fallback in each PGO
candidate. The concrete instruction forms differed by ISA. Final binary hashes
also differed by host and candidate.

These are two host-specific observations, not a controlled architecture or
vendor comparison. The machines used different compiler patch releases and
LLVM versions for the experiment, and the emitted binaries differ. The larger
x86-64 slowdown has no ISA, vendor, compiler-pass, or microarchitectural
attribution. Testing those mechanisms would require additional builds and
hardware-event or trace evidence.

Neither host exposed `llvm-bolt`, `perf2bolt`, or `merge-fdata` on `PATH`. The
post-link portion of this round is therefore a provenance and decision-boundary
exercise, not a BOLT performance measurement.
