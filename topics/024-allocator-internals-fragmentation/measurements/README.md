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

Final publication requires validated exact-source receipts from:

- AArch64: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`.
- x86-64: the runtime-resolved backing host for SSH alias `xxl`.

Store retained evidence under `measurements/raw/<source>/<host>/`. Record the
host-specific result and a cross-host comparison only after
`validate_receipts.py` succeeds.
