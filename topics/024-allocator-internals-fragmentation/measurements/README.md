# Measurement contract

Each receipt applies only to its recorded source identity, probe hash, binary
hash, host, glibc, kernel, compiler flags, CPU affinity, page size, workload,
and run window.

The treatment uses 12 complete four-period blocks. Every letter launches a
fresh process. A block contrast is the mean log scattered RSS minus the mean
log compact RSS. The point estimate exponentiates the mean of 12 contrasts.
The 95% interval uses the Student-t critical value with 11 degrees of freedom.

The interval covers block-to-block variation in one run window. It excludes
build, host, future-window, allocator-version, and workload variation. Four
A/A blocks exercise both labels but do not establish a calibrated noise floor.

Final publication requires exact-source receipts from the following hosts,
accepted only after `validate_receipts.py` succeeds:

- AArch64: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`.
- x86-64: the runtime-resolved backing host for SSH alias `xxl`.

Store retained evidence under `measurements/raw/<source>/<host>/`. Record the
host-specific result and a cross-host comparison only after
`validate_receipts.py` succeeds.

Exact-source records for commit `c7187b178fd75cea08462e4e77cdad225c1e7522`:

- [x86-64 host](xxl-2026-08-03.md)
- [AArch64 host](arm-2026-08-03.md)
- [cross-host comparison](comparison-2026-08-03.md)
- [raw receipts](raw/c7187b1/)

Provenance notes for the `c7187b1` receipts:

- Raw receipts are immutable snapshots bound to their evidence commit.
  Review commits changed the harness and probe after measurement; those
  changes apply to future runs only and the retained bundles are not
  regenerated. The strengthened validator re-passes both retained sets;
  its probe-environment blocklist parameter check is waived only for
  receipts recorded before that parameter existed.
- In the retained runs, the probe's pointer table lived inside the measured
  arena as an equal additive term in both arms, diluting the RSS ratio
  toward one; the retained scattered/compact contrast is therefore
  conservative. The probe now places the table in a separate mapping.
- The retained `free_ns` diagnostic included per-iteration pattern string
  comparisons (one per compact free, two per scattered free); the probe now
  resolves the pattern before timing. The primary RSS estimand is
  unaffected.
- The retained payload checksum covered each survivor's first and last
  bytes; the probe now sums every byte against a formula-derived
  expectation.
