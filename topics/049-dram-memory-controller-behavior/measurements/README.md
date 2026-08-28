# Topic 49 measurement records

Final records are added only after the exact checked-source candidate passes on
the literal Arm target and the runtime-resolved `xxl` x86-64 target.

Each host note must record source and archive identity, host and alias identity,
toolchain and flags, topology and placement, process count, block contrasts,
interval scope, useful-byte bounds, code generation, validation outcome, and
measured-versus-inferred claims. The comparison note must keep host results
separate and must not turn them into an instruction-set or vendor comparison.

Worker rates use the full run epoch, including release, acknowledgement, small
control, large probe, stop publication, and worker drain through termination.
The end timestamp follows all worker joins. Record the lower and inclusive
upper useful-source-byte rates, require every loaded worker to contribute, and
keep idle bounds at exact zero. Record process-wide large-walk resource
counters separately from probe-thread timing.

Sealed raw receipts and an outer SHA-256 manifest belong under [`raw/`](raw/).
