# Topic 47 focused experiment

This experiment asks what changes when eight pinned workers stop meeting at one
shared atomic location. It compares a shared addition, a compare-and-swap (CAS)
retry loop, one atomic stripe per worker, and batches of 256 logical updates.
It measures process time and software CAS retries. It does not count cache-line
transfers or prove an internal processor mechanism.

## Build and inspect one process

The publication binary uses native target features, one code-generation unit,
fat link-time optimization, and debug information for linked disassembly:

```bash
CARGO_INCREMENTAL=0 \
CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1 \
CARGO_PROFILE_RELEASE_LTO=fat \
CARGO_PROFILE_RELEASE_DEBUG=2 \
RUSTFLAGS='-C target-cpu=native' \
cargo build --locked --offline --release \
  --package atomics-under-contention --example atomic_contention
```

On a Linux host where central processing unit (CPU) identifiers 0 through 8 are
allowed, run one smoke case:

```bash
BENCH_LABEL=manual:shared \
target/release/examples/atomic_contention \
  shared 8 10000 1000 256 8 0,1,2,3,4,5,6,7
```

Success is exactly one JavaScript Object Notation (JSON) object. `startup_ns`
covers allocation, thread creation, pinning, and readiness. `warmup_ns` covers
warmup plus state reset. `steady_ns` covers the synchronized measured kernel.
`teardown_ns` covers joins, placement checks, arithmetic checks, and final-count
validation. `total_ns` is the exact sum of those four fields. Every worker must
report its requested processor before and after steady work.

## Run the fixed process schedule

```bash
RUN_ROOT=$(mktemp -d)
mkdir "$RUN_ROOT/binary"
install -m 0500 target/release/examples/atomic_contention \
  "$RUN_ROOT/binary/atomic_contention"
python3 -I -B \
  topics/047-atomics-under-contention/experiment/run_processes.py \
  --binary "$RUN_ROOT/binary/atomic_contention" \
  --out "$RUN_ROOT/experiment" \
  --threads 8 --iterations 2000000 --warmup-iterations 100000 \
  --batch-size 256 --coordinator-cpu 8 \
  --worker-cpus 0,1,2,3,4,5,6,7 \
  --blocks 12 --aa-blocks 4 --seed 20260826 \
  --timeout-seconds 120
```

The runner launches 64 fresh processes. Forty-eight processes form 12 primary
blocks: three complete repetitions of the four-sequence Williams design. That
design places every treatment equally often in every position and balances
every directed first-order transition. Sixteen additional processes form four
A/A control blocks, which send byte-identical shared runs through labels A and
B. They are split equally between ABBA and BAAB order.

One complete four-process block is an analysis unit. Threads and loop iterations
inside a process are subsamples. The primary outputs are paired geometric-mean
ratios for CAS/shared, striped/shared, and batched/shared `steady_ns` per logical
operation. The summary retains block-level log dispersion and a descriptive
bootstrap interval over complete blocks from that one host and run window.

The runner never retries or replaces an attempt. It appends stdout, stderr,
timeout state, placement, phase times, operation counts, CAS retries, and binary
hashes to `attempts.jsonl` before continuing. A zero `steady_ns` is valid JSON
and valid phase accounting, but it cannot enter a logarithmic ratio; it remains
in the raw record and makes its block unpublishable.

## Inspect the linked kernels

```bash
objdump -d -C --no-show-raw-insn \
  target/release/examples/atomic_contention |
  rg -n -A 60 '<topic47_(shared_fetch_add|cas_increment|striped_fetch_add|batched_fetch_add)>:'
```

The x86-64 binary should retain locked read-modify-write instructions, including
`cmpxchg` in the CAS kernel. AArch64 can contain Large System Extensions (LSE)
instructions, an exclusive-load/store loop, or linked helper calls, depending
on the exact target features. Both shared and striped stable symbol names must
remain in the symbol table. The optimizer may bind them to one address because
their machine-code bodies are identical; `symbol-addresses.json` records that
alias explicitly. Record the linked image. Do not infer timing, fairness, or
cache-line handoffs from an instruction name.

## Create a source-bound host receipt

Resolve the `xxl` Secure Shell (SSH) alias immediately before the x86 run:

```bash
ssh -G xxl | rg '^hostname ' | tee /tmp/topic47-xxl-resolution.txt
```

Retain that local resolution receipt. Create the archive with one top-level
directory, then record its digest:

```bash
SOURCE_COMMIT=$(git rev-parse HEAD)
git archive --format=tar.gz \
  --prefix="systems-snackpack-${SOURCE_COMMIT}/" \
  --output=/tmp/topic47-source.tar.gz "$SOURCE_COMMIT"
SOURCE_ARCHIVE_SHA256=$(shasum -a 256 /tmp/topic47-source.tar.gz | awk '{print $1}')
```

Record the resolved hostname as `SSH_RESOLVED_HOSTNAME`. On each required Linux
host, run the copy of `run_host.sh` taken from that sealed Git archive:

```bash
SOURCE_COMMIT=<40-hex-commit> \
SOURCE_ARCHIVE_SHA256=<64-hex-digest> \
SOURCE_ARCHIVE_PATH=/tmp/topic47-source.tar.gz \
SSH_TARGET_LABEL=xxl \
SSH_RESOLVED_HOSTNAME=<resolved-hostname> \
./run_host.sh /tmp/topic47-x86 8 0,1,2,3,4,5,6,7 \
  2000000 100000 256 12 4 20260826
```

For Arm, set both host variables to
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`. The host runner rejects any
other label. It also rejects a reused output directory, source drift, archive
or binary drift, missing processors, simultaneous threads of one core,
cross-socket or cross-NUMA-node placement, incompatible coherence-line size,
failed source gates, incomplete code generation, failed processes, and
statistics that cannot be recomputed from raw attempts.

The validator writes `receipt-validation.json` only after every gate passes.
Partial and failed output remains in the requested directory for diagnosis; it
is never silently replaced.

## Interpretation controls

- Compare only `steady_ns` per logical update for the primary ratios. Report
  startup, warmup, and teardown separately.
- Every kernel pays one fixed `black_box(index)` cost per logical increment,
  and that cost is inside `steady_ns`. The shared overhead pulls the
  striped/shared and batched/shared ratios toward 1, with a proportionally
  larger effect on the cheaper striped and batched modes, so those ratios
  understate the isolated-counter advantage.
- Keep all 12 complete primary blocks. Do not stop after a favorable result.
- Treat the A/A result as a mechanical path check, not a universal noise floor.
- Report CAS retries as software failed attempts per successful logical update,
  not as coherence events.
- Report batched `rmw_attempts` with its weaker visibility contract: a worker can
  hold up to 255 unflushed updates.
- Limit conclusions to the retained source, binary, processors, host, and run
  window. A host pair does not represent an instruction-set family.
