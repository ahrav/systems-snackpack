# Measurements

Topic 28 promotes no timing claim from an uncommitted or working-tree run. Each
host result must bind one exact candidate to its source, final binary, fixed
schedule, raw receipts, analysis, host, CPU boundary, and run window.

## Required host record

Retain:

- full source commit, deterministic source archive and SHA-256, pre-run and
  post-run tracked-source manifests, pre-run and post-run `HEAD`, and clean
  worktree receipts;
- swept and effective build environments, compiler/Cargo/Python identity,
  complete optimized build command, retained binary and SHA-256;
- final-image symbol table, complete disassembly, targeted
  `topic28_origin_work` disassembly, and evidence that the measured call path
  reaches that symbol;
- requested endpoint, host label, resolved hostname, architecture, CPU model,
  kernel, allowed and selected CPUs, timer source, and UTC run window;
- calibration target, work iterations, observed calibration mean and checksum,
  settings hash, key digest, waiter and origin caps, retry limits, schedule
  seeds, all 48 analysis assignments, and both semantic-control assignments;
- append-only subprocess attempts with commands, stdout/stderr, timeout and exit
  status, plus every logical-caller and physical-attempt row;
- per-period summaries, complete-block primary analysis, A/A diagnostic,
  independent receipt-validation output, final run status, and an
  `evidence.sha256` manifest covering every retained file.

## Exact count gates

For the default settings, every main naive period must retain exactly 64
logical rows, 64 flights, 192 physical attempts, 128 retry attempts, 128
transient attempts, 64 successful attempts, and 64 logical completions. Every
controlled period, including A/A, must retain 64 logical rows, one leader, 63
followers, one flight, three physical attempts, two retries, two transient
attempts, one successful attempt, and 64 logical completions. No default period
sheds a caller. Origin activity must remain at or below four and admitted
callers at or below 64.

The waiter-saturation control (`N=128, W=64, Q=2`) must retain 128 logical
rows, 64 completions, 64 shed callers, one leader, 63 followers, one flight,
three attempts, and two retries. The exhaustion control (`N=64, W=64, Q=1`)
must retain 64 logical rows, 64 shared retry-exhausted results, no completion or
shedding, one leader, 63 followers, one flight, two transient attempts, and one
retry.

The validator must derive these counts from raw rows, not trust summary fields.
It must also verify assignment order, unique process IDs, binary and settings
hashes, retry-token transitions, timestamp order, non-overlapping attempts in
each flight, permit-cap conformance, shared controlled results, checksums,
terminal status, and exact reproduction of the retained analysis.

## Promotion rule

1. Commit the candidate before either host run.
2. Run one immutable bundle on runtime alias `xxl`; resolve and record its
   backing hostname at run time.
3. Run the same commit on the required literal Arm endpoint.
4. Reject outcome-dependent replacement. Any failed period invalidates the
   complete run; a retry repeats the fixed schedule under a new run identity.
5. Verify source stability, all gates, the final binary and code shape, every
   raw receipt and derived value, and the evidence manifest independently for
   each host.
6. Only then add host notes and a cross-host comparison. Do not turn a
   cross-host timing difference into an ISA or vendor claim.

## Claim labels

- **Measured:** raw monotonic durations, logical and physical events, and host
  provenance from one retained run.
- **Derived:** exact counts, ratios, hashes, bounds, and block estimates
  recomputed from raw receipts.
- **Inferred:** mechanism explanations tied to the one-key model.
- **Unsupported:** real DNS/network/resolver behavior, TTL caching, backoff,
  outage recovery, multiple keys, global key admission, fleet capacity, and
  architecture effects.

## Retained layout

Store immutable host archives under `raw/<source-prefix>/`, with outer archive
hashes in `SHA256SUMS`:

```text
measurements/
  <source-prefix>-arm.md
  <source-prefix>-xxl.md
  <source-prefix>-comparison.md
  raw/<source-prefix>/
    SHA256SUMS
    topic28-<source-prefix>-arm-results.tar.gz
    topic28-<source-prefix>-xxl-results.tar.gz
```

Never overwrite a failed or superseded bundle. A corrected source gets a new
commit and source prefix. Host and comparison notes must link to the sealed raw
evidence instead of copying only summary values.

## Retained candidate

- [`64ec37b` required Arm result](64ec37b-arm.md)
- [`64ec37b` runtime-resolved `xxl` result](64ec37b-xxl.md)
- [`64ec37b` two-host boundary and comparison](64ec37b-comparison.md)
