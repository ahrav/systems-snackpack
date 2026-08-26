# Topic 46 focused experiment

This experiment tests whether separating two independently written atomic
counters changes fixed-work time. It does not directly observe invalidations,
cache-to-cache transfers, or the Neoverse V1 near-versus-far atomic path.

## Run a focused Linux check

Choose two allowed logical processors that occupy different physical cores.
Inspect the mapping first:

```bash
lscpu -e=CPU,NODE,SOCKET,CORE,CACHE,ONLINE
taskset --pid --cpu-list $$
```

Build and smoke-test the exact operation:

```bash
RUSTFLAGS='-C target-cpu=native' \
  cargo build --release --package cache-coherence-false-sharing \
  --example cache_coherence_probe

target/release/examples/cache_coherence_probe packed 100000 0 1
target/release/examples/cache_coherence_probe padded 100000 0 1
```

Expected output is one JSON object with `correct`, `affinity_ok`, and
`layout_ok` set to `true`. `packed` reports an eight-byte address delta;
`padded` reports 128 bytes.

Run the fixed process schedule:

```bash
python3 -I -B \
  topics/046-cache-coherence-false-sharing/experiment/run_processes.py \
  --binary target/release/examples/cache_coherence_probe \
  --out /tmp/topic46-run --iterations 10000000 --cpu0 0 --cpu1 1 \
  --blocks 8 --aa-blocks 4 --seed 20260825
```

The runner retains 48 fresh-process attempts. Expect the packed-to-padded ratio
to exceed one when false sharing dominates on that exact CPU pair. Expect the
padded A/A ratio near one, but treat it only as a mechanical path check.

## Inspect generated code

```bash
objdump -d -C --no-show-raw-insn \
  target/release/examples/cache_coherence_probe |
  rg -n -A 80 '<topic46_increment>:'
```

The x86-64 lowering should contain a locked add or increment. AArch64 can use an
LSE `ldadd`, an `ldxr`/`stxr` loop, or an outline helper depending on the exact
target features. Record what the binary contains; do not assume one lowering.

## Publication runner

[`run_host.sh`](run_host.sh) accepts an output directory, two processors,
iteration count, primary block count, A/A block count, and seed. It also
requires these source-binding environment variables:

```text
SOURCE_COMMIT
SOURCE_ARCHIVE_SHA256
SOURCE_ARCHIVE_PATH
SSH_TARGET_LABEL
SSH_RESOLVED_HOSTNAME
```

It extracts the archive outside the repository, verifies the authorized host
and topology, builds once, captures code generation, runs the fixed schedule,
and invokes [`validate_receipts.py`](validate_receipts.py). Publication uses
10,000,000 iterations per thread, eight primary blocks, four A/A blocks, and
seed `20260825` on both required hosts.
