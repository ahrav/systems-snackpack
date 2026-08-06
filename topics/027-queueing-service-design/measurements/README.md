# Measurements

No exact-candidate host result is retained yet. This directory intentionally
contains only the measurement contract until one committed candidate completes
the fixed schedule on both exact hosts.

## Required host record

Each record must bind its claims to:

- full source commit, source archive and SHA-256, sorted tree-manifest digest,
  clean extracted source, compiler identity, complete build command, final
  binary and SHA-256, and final-image workload/call-path evidence;
- requested endpoint, runtime alias resolution, resolved hostname, host label,
  architecture, CPU model, kernel, online and allowed CPUs, selected two-CPU
  affinity set, timer source, and run window;
- base-iteration calibration, observed calibration duration, derived arrival
  interval, nominal load, queue capacity, request horizon, workload seed, and
  exact main and A/A schedules;
- every intended arrival, actual generator attempt, service start, completion
  or rejection, service factor, checksum contribution, process exit, and
  stdout/stderr;
- per-period offered/admitted/completed/rejected counts, generator lateness,
  completed-request mean/p50/p99 queue wait, the nominal-arrival and final-
  completion endpoints, and goodput over their later endpoint;
- complete-block primary contrasts, the predeclared paired-t interval,
  secondary contrasts, A/A diagnostics, invalid-attempt decisions, and final
  validator status.

## Promotion rule

1. Commit the candidate before running it.
2. Produce one immutable bundle for runtime alias `xxl`, recording the backing
   hostname resolved at run time.
3. Produce one immutable bundle for literal Arm endpoint
   `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` from the same candidate.
4. Verify source identity before and after each run, the complete fixed
   schedule, raw timestamp ordering, counts, checksums, analysis, final-image
   evidence, and the bundle manifest.
5. Only then add host and cross-host notes. A host result is not promoted merely
   because its process exited zero or the other host passed.

Queueing outcomes remain scoped to the recorded model, candidate, binary,
host, CPU boundary, workload, and run window. Cross-host differences are not
ISA or vendor effects without a design that supports that claim.

## Retained records

None. Pending the exact post-commit two-host rerun.

Raw evidence belongs under `raw/<source-prefix>/<host-label>/` and follows the
[raw bundle contract](raw/README.md).
