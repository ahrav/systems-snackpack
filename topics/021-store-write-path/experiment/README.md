# Exact-source experiment runner

`run_remote.sh` binds one clean Git checkout to one native benchmark binary,
one selected Linux CPU, and one sealed evidence directory. It requires the
checkout to be clean at entry and digest-identical at exit. `run_processes.py`
executes the fixed process schedule and computes block-level comparisons.

## Invocation

From a clean Git checkout:

```bash
topics/021-store-write-path/experiment/run_remote.sh \
  /absolute/path/to/systems-snackpack \
  /absolute/path/to/empty-evidence-directory \
  0
```

Omitting the CPU selects the first CPU allowed to the runner. `SOURCE_COMMIT`
can require an exact checked-out commit. `HOST_ALIAS` records the caller's
alias because the remote host cannot reconstruct it; the runner records
`unspecified` when the caller omits the variable.

Calling `run_processes.py` directly exercises the schedule but bypasses the
source, build, disassembly, and evidence-integrity gates.

## Source and build boundary

The runner rejects dirty state and any scanned source path absent from
`git ls-files`. It records per-file SHA-256 manifests before and after the
experiment and rejects a checkout that is dirty or digest-different at exit.
These entry/exit checks do not detect a transient edit that is restored before
the final snapshot.

On normal invocation, the runner re-executes itself with an allowlisted
environment. Its inner path independently rejects any exported variable
outside that allowlist. It also rejects Cargo configuration found between the
repository and file-system root and uses a fresh offline `CARGO_HOME`. The
allowlist retains `PATH`, `HOME`, user identity, fixed locale and time zone, the
host label, and the optional expected commit; Cargo, Rust, linker, profile, and
loader overrides are not inherited. Workspace formatting, tests, Clippy,
benchmark compilation, and rustdoc gates precede the focused build. That build
uses:

```text
-C target-cpu=native -C codegen-units=1 -C lto=off
```

The copied benchmark binary receives its own SHA-256, file metadata, symbol
table, complete disassembly, and complete focused-function disassembly. Presence
gates require `VMOVAPS`, `VMOVNTDQ`, and `SFENCE` on x86-64 or `STP`, `STNP`,
`STLR`, and `LDUR` on AArch64. The retained focused disassembly still requires
manual confirmation that the fences and publication occur in order and that
the STLF loads use exact and `+4` addresses in their respective functions.

## Fixed schedule

Each comparison runs four A/A control blocks before twelve primary blocks. Odd
blocks use `ABBA`; even blocks use `BAAB`. A block launches four fresh processes
on the selected CPU and contributes one log-time contrast. The two comparisons
therefore run 128 processes in total:

- temporal labels versus temporal labels, then temporal versus non-temporal;
- exact-overlap labels versus exact-overlap labels, then exact versus partial.

The primary schedule contains six `ABBA` and six `BAAB` blocks. The driver does
not retry samples, discard outliers, or stop from an observed effect.

## Fail-closed records

Each successful child must emit exactly one JSON object on standard output,
emit no standard error, and exit successfully. The driver rejects a wrong
schema, architecture, arm implementation, input size, iteration count,
publication value, full-pattern check, or STLF oracle result. It also rejects:

- any major fault in setup, scrub, timed, or verification phases;
- any minor fault in the timed phase;
- an external process interval shorter than the sum of internal phase timers;
- a partial schedule or an architecture change within the run.

`attempts.jsonl` flushes a parseable child record before exit-status and content
validation. `raw.jsonl` contains validated records only. `process.log` retains
child output and timeout diagnostics. `session.json` binds the schedule to the
source and binary, while `summary.json` contains the completed block analysis.
The outer runner also retains host, toolchain, gate, binary, and source evidence,
then seals every retained file in `evidence.sha256`.
