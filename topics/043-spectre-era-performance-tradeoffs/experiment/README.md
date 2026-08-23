# Focused experiment

This experiment tests the elapsed-time cost of three equivalent lookup shapes
on one pinned Linux logical CPU. A fresh process performs setup, a fixed warmup,
and one timed interval. The experiment does not execute a transient-disclosure
attack, test whether a mitigation covers every exploitable instruction sequence
(a gadget), or support a security claim.

`run_host.sh` applies this fixed protocol:

1. Require and record an authorized target label, a matching runtime hostname,
   a 40-hex source commit, and a 64-hex source-archive digest. Verify the
   supplied Git archive's digest and embedded commit, compare the executing
   source tree with the archive, and reject a target whose architecture does
   not match its authorized label.
2. Record the kernel, CPU model, logical CPU count, affinity, Rust toolchain,
   native target features, `-C target-cpu=native` build flag, compiler version,
   and available kernel vulnerability strings.
3. Run locked deterministic tests from the extracted archive, build its release
   probe in a private target with native CPU features, and run the cross-mode
   checksum self-test with that probe.
4. Capture the four stable symbols. Linux x86-64 must contain `cmp`/`sbb` and
   `lfence`. Linux AArch64 must contain `cmp`/`sbc`/`CSDB` and `DSB NSH` plus
   `ISB`.
5. Run eight A/A blocks. An A/A screen gives two labels the same `plain`
   treatment to detect imbalance under alternating label order. The screen
   fails when the geometric mean `b/a` ratio falls outside `exp(-0.10)` through
   `exp(0.10)`.
6. Run 24 timing blocks. Each block starts one fresh process per mode. Every one
   of the six mode orders occurs four times, and every mode occupies each
   ordinal position eight times.
7. Compute `mask/plain` and `barrier/plain` from within-block log ratios. The
   95% Student-t confidence interval uses 24 ratios and 23 degrees of freedom.

Each process uses workload seed `0x243f6a8885a308d3`, the requested iteration
count, a 200,000-iteration warmup, and a separate timed interval. The 24-block
schedule uses seed `0x43_2026_08_22`. The harness records setup and warmup but
excludes them from the comparison. It appends, flushes, and synchronizes each
JSON Lines record, one JSON object per line, before starting the next process.
Invalid output, nonzero exits, and timeouts remain in the raw log and fail
analysis after the fixed schedule ends.

Every probe receives only `LANG=C`, `LC_ALL=C`, `PATH=os.defpath`, and `TZ=UTC`.
The self-test and process rows record this allowlist, and offline validation
rejects different environments.

Each probe record also states that 4,096 words are addressed through an 8,192
index space. About half the generated indices are therefore out of bounds, and
the barrier mode executes its barrier only for in-bounds indices.

```bash
SOURCE_COMMIT=<40-hex-commit> \
SOURCE_ARCHIVE_SHA256=<64-hex-archive-digest> \
SOURCE_ARCHIVE_PATH=/tmp/source-archive.tar.gz \
SSH_TARGET_LABEL=<authorized-target-label> \
SSH_RESOLVED_HOSTNAME=<hostname-f-output> \
topics/043-spectre-era-performance-tradeoffs/experiment/run_host.sh \
  /tmp/topic43-receipts [CPU] [ITERATIONS]
```

The source archive must be the archive containing the executing source tree.
The output path must not exist and must remain outside the repository. Omitted
`CPU` selects the first CPU in the caller's affinity set; omitted `ITERATIONS`
selects 20,000,000. `validate_receipts.py` recomputes both summaries from the
process logs, checks required files and code generation, and records SHA-256
digests in `receipt-validation.json`.

The interval describes between-block variation for this host, build, input,
placement, and run window. Serial correlation, thermal drift, frequency changes,
and shared-machine interference can remain. Review raw order, generated code,
and host state before attributing a ratio to one instruction.
