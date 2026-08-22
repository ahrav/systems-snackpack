# Spectre-era performance tradeoffs

Transient execution occurs when a processor executes a predicted path before
it knows whether that path is architecturally valid. A mitigation must match
the predictor and the trust boundary: the point where less-trusted input can
influence protected data or control flow. A barrier can remove useful overlap
from every guarded lookup. A data dependency can preserve more overlap, but it
constrains only the value it sanitizes. This crate measures those two lookup
shapes beside an ordinary bounds check. It neither demonstrates an exploit nor
proves that a program is secure.

## Three lookup shapes

- `plain` performs Rust's ordinary checked lookup. It provides the correctness
  baseline and no experiment-specific speculation control.
- `mask` turns the unsigned bounds result into a data dependency on the load
  address. Linux x86-64 uses `cmp` and `sbb`. Linux AArch64 uses `cmp`, `sbc`,
  and the Consumption of Speculative Data Barrier (`CSDB`). Other targets use
  an arithmetic fallback for correctness testing only.
- `barrier` rejects an invalid index, then places a speculation barrier before
  the load. Linux x86-64 uses `lfence`. Linux AArch64 uses `dsb nsh` plus `isb`:
  a Data Synchronization Barrier for the non-shareable domain followed by an
  Instruction Synchronization Barrier. This shape can constrain more in-flight
  work than a dependency, so its cost depends on the surrounding workload.

All modes return zero for an invalid index. Exact symbols make the generated
code reviewable: `topic43_plain_lookup`, `topic43_mask_lookup`,
`topic43_barrier_lookup`, and `topic43_speculation_barrier`.

## Cost boundary

The experiment asks how much elapsed time each lookup shape adds to this fixed
synthetic stream. If `N` lookups execute, a screening model is
`T = T_work + N * C_shape`. `T_work` is shared loop and data work. `C_shape` is
the host-specific incremental cost of the selected shape. The terms can
interact through code layout, prediction, caches, and outstanding work, so the
harness compares complete fresh processes instead of subtracting instruction
latencies.

The reported 95% Student-t confidence interval for each geometric mean ratio is
computed from 24 within-block log ratios on one host. It does not cover other
CPUs, kernels, compilers, inputs, placements, attack strategies, or security
outcomes.

## Run the probe

```bash
cargo test --package spectre-era-performance-tradeoffs
cargo run --release --package spectre-era-performance-tradeoffs \
  --bin spectre-tradeoff-probe -- --mode mask --iterations 2000000
```

For a publication receipt, run the locked, native-CPU protocol from the
repository root. `OUTPUT_DIR` must not exist and must be outside the repository.

```bash
SOURCE_COMMIT=<40-hex-commit> \
SOURCE_ARCHIVE_SHA256=<64-hex-archive-digest> \
SOURCE_ARCHIVE_PATH=/tmp/source-archive.tar.gz \
SSH_TARGET_LABEL=<authorized-target-label> \
SSH_RESOLVED_HOSTNAME=<hostname-f-output> \
topics/043-spectre-era-performance-tradeoffs/experiment/run_host.sh \
  /tmp/topic43-receipts [CPU] [ITERATIONS]
```

The host protocol requires Linux, `taskset`, and either the x86-64 `xxl` target
or the AArch64 `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` target. It also
requires a caller-supplied Git archive. It verifies the archive digest and
embedded commit, then compares every executing source file with the archive.
It defaults to the first CPU in the caller's affinity set and 20,000,000 timed
iterations. The scripts record host state, run correctness and code-generation
gates, perform a balanced A/A screen, and execute the fixed 24-block comparison.
They retain every scheduled process record, including nonzero exits and invalid
output, before analysis fails.

## Selection guide

Masking is a candidate when one bounds-sensitive value and its safe fallback
are auditable. A barrier is a candidate when the relevant data flow cannot be
sanitized locally. Broader compiler or operating-system controls require a map
of the attacker, victim, predictor boundary, and uncovered code. In every case,
inspect the deployed generated code and measure the deployed workload.

See [primary references](references.md) and [round 1](rounds/01.md).
