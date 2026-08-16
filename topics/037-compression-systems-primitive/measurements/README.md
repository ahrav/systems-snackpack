# Topic 37 measurement contract

Retained exact-source results:

- [`2026-08-16-arm.md`](2026-08-16-arm.md)
- [`2026-08-16-xxl.md`](2026-08-16-xxl.md)
- [`2026-08-16-comparison.md`](2026-08-16-comparison.md)
- [`raw/2026-08-16-febce369/`](raw/2026-08-16-febce369/)

This experiment asks two narrow questions: how much byte reduction survives
real per-unit metadata and raw fallback, and how much encode or decode time the
same units cost on one pinned Linux processor. It does not simulate storage or
network input/output (I/O). The Rust model turns measured byte and codec-rate
inputs into a separate no-overlap break-even estimate.

## Implementations and stored format

The C probe compares three methods over the same bytes:

- `identity` copies bytes with `memcpy`. It is a copy control, not a zero-copy
  raw-read path.
- `lz4` uses `LZ4_compress_default` and `LZ4_decompress_safe`. Those functions
  produce and consume an LZ4 raw block, not an LZ4 frame.
- `zstd` uses one-shot frames at level 1 with one reusable compression and
  decompression context per process.

Every independently decoded unit is serialized as:

```text
4 bytes  magic "C37U"
1 byte   selected representation: raw, LZ4 raw block, or zstd frame
4 bytes  encoded payload length, little endian
4 bytes  decoded length, little endian
N bytes  selected payload
```

The 13 metadata bytes are present in the timed buffer and in `stored_bytes`.
For LZ4 or zstd, the probe stores the compressed payload only when it is
smaller than that unit's raw payload. Otherwise it overwrites the candidate
with the original bytes and writes the raw tag. The common header means the
fallback comparison includes the same container metadata on both sides.

The decoder validates the magic, tag, lengths, complete unit count, aggregate
container length, and decoded length. For zstd it also requires
`ZSTD_findFrameCompressedSize` to equal the recorded payload length, rejecting
trailing data within the unit. The correctness gate compares every decoded byte
with the input after warmup and after timing.

## Corpus and unit shapes

Each process constructs 1,024 records of 256 bytes, for 262,144 logical input
bytes. The `structured` corpus repeats one service-log pattern and replaces the
first 16 bytes of each record with its lowercase hexadecimal ordinal. The
`random` control uses SplitMix64, a deterministic pseudorandom number
generator, from the fixed seed `0x4d595df4d0f33173`. It stores words explicitly
in little-endian order.

The same corpus is represented in two ways:

- `independent`: 1,024 separately encoded 256-byte units;
- `batch`: one 262,144-byte unit.

This exposes the combined effects of call count, repeated framing, history
resets, and per-unit fallback in the probe. A history reset prevents a new unit
from referring to bytes in an earlier unit. The experiment does not attribute
the result to one mechanism or establish a production chunk size. A real
choice must also account for point-read amplification, indexes, corruption
recovery, scheduling, and memory.

## Timing and replication

Corpus construction, allocation, context creation, calibration, one verified
warmup, and JavaScript Object Notation (JSON) formatting are outside the encode
and decode intervals.
Encode and decode receive separate frozen repetition counts because their rates
can differ. Repetitions only lengthen one process interval; they are not
independent observations.

One process is one treatment application. A paired complete-block contrast is
the replication and analysis unit used for statistical dispersion. The frozen
seed `370037` creates:

- 12 complete main blocks;
- all six codec orders exactly twice;
- each codec in each order position four times;
- independent-first and batch-first in six blocks each;
- both corpus orders in six blocks each;
- 144 main fresh processes, one per codec, corpus, shape, and block;
- four two-period identity A/A blocks, meaning the same method runs under both
  labels, per corpus and shape, or 32 additional
  fresh processes; and
- 12 startup controls before and 12 after the timed schedule.

The design, schedule, and phase-specific calibration are written before timed
execution. There is no data-dependent stopping or retry. A failed or malformed
attempt remains in its exclusive attempt directory and fails the run.

Codec-time summaries use paired log ratios within each of the 12 complete
blocks. `lz4/identity`, `zstd/identity`, and `zstd/lz4` below one mean the
numerator used less in-process time per input byte. Unit-shape summaries use
`batch/independent`; below one means the batched representation used less time
per input byte. The report includes raw block contrasts and their sample
standard deviation. It also gives a working-model, two-sided 95 percent
Student-t interval for the mean log ratio, transformed back to a ratio. That
calculation assumes independent, approximately normal complete-block log
contrasts. Sequential blocks on one shared host do not establish those
assumptions. Treat the interval as descriptive for this run, not as a bound on
future outcomes or a simultaneous interval across codecs, corpora, shapes, and
phases. No multiplicity correction is applied.

The four-block identity A/A results, where both labels run the same method,
verify label, scheduling, and receipt
plumbing. They are not a noise floor, equivalence test, or correction applied
to codec estimates. Startup controls include Python fork, process execution,
the dynamic loader, the probe, standard streams, and exit. They are summarized
separately and never subtracted from the in-process intervals.

## Exact-source and host boundary

`run_host.sh` requires a full hexadecimal commit object identifier, a source
archive, and its Secure Hash Algorithm 256-bit (SHA-256) digest. In a Git
worktree, it requires clean files, resolves and records the full commit,
rehashes files against that commit, and compares the verified archive with that
tree. In an archive-extracted tree without Git metadata, it retains the full
supplied commit identifier and compares the digest-verified archive's extracted
file manifest with the runner tree. Both modes build a read-only source snapshot
outside the repository. The result records:

- the requested Secure Shell (SSH) alias and runtime-resolved hostname;
- architecture, kernel, central processing unit (CPU) model and counts,
  affinity, `/proc` status, and
  available control group (cgroup) CPU, processor-set, and pressure files;
- Rust, Cargo, Python, C compiler, linker, binary utilities, and resolved tool
  hashes;
- generic and `-march=native` C builds plus generic and native Rust builds;
- probe source, Python runner, validator, timing binary, and runtime-library
  hashes before and after timing;
- copies of the exact probe source, Python runner, validator, and timing binary
  inside the hashed benchmark receipt tree;
- the exact child argument vector, working directory, pinned central processing
  unit (CPU), and minimal recorded effective environment for every attempt;
- child-observed CPU and affinity before and after timed work;
- linked wrapper disassembly and dynamic imports; and
- an outer SHA-256 manifest before the result tree is made read-only.

The native build changes only this probe. The linked zstd and LZ4 shared
libraries are distribution binaries whose compile flags are not inferred from
probe disassembly. Executable and Linkable Format (ELF) generated code shows
calls and harness control flow, not the codec libraries' internal kernels or
the cause of a timing difference.

The runner is Linux/GNU-specific and requires Python 3.9 or newer, `taskset`,
`ldconfig`, ELF `ldd`, GNU-compatible `nm` and `objdump`, a zstd development
header, and versioned zstd and LZ4 shared libraries. When `lz4.h` is absent, the
probe uses a small documented LZ4 1.x application binary interface (ABI)
declaration shim. The receipt records which declaration path compiled and
hashes the actual runtime library.

## Run and validate

From a clean committed source tree, create an archive whose extracted tree is
the same source candidate. Resolve `xxl` immediately before its run and pass
the observed backing hostname. The host runner verifies that `xxl` is x86-64
and that the literal Arm target is Arm.

```bash
SSH_TARGET_LABEL=xxl \
SSH_RESOLVED_HOSTNAME="$RESOLVED_XXL_HOST" \
topics/037-compression-systems-primitive/experiment/run_host.sh \
  /tmp/topic37-x86-results "$SOURCE_COMMIT" "$SOURCE_ARCHIVE_SHA256" "$SOURCE_ARCHIVE"

SSH_TARGET_LABEL=dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
SSH_RESOLVED_HOSTNAME=dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
topics/037-compression-systems-primitive/experiment/run_host.sh \
  /tmp/topic37-arm-results "$SOURCE_COMMIT" "$SOURCE_ARCHIVE_SHA256" "$SOURCE_ARCHIVE"
```

To revalidate a retrieved benchmark directory with the exact validator source:

```bash
python3 -I /tmp/topic37-results/benchmark/artifacts/validate_receipts.py \
  /tmp/topic37-results/benchmark
```

Pass `--binary PATH` to compare an additional retrieved executable with the
retained timing-binary digest.

The validator independently reconstructs the schedule, both corpora and their
Fowler-Noll-Vo version 1a (FNV-1a) checksums, calibration cells, row arithmetic,
byte accounting, affinity observations, attempt digests, paired contrasts,
intervals, startup summaries, and pre/post/retained artifact hashes.

## Interpretation limits

These observations apply to the recorded hosts, shared-library versions,
262,144-byte hot corpus, one pinned processor, reusable contexts and buffers,
and isolated fresh processes. They do not measure I/O, cold allocation,
concurrency, queueing, high-percentile latency at the slow end of the request
distribution, energy, dictionaries, other zstd levels,
checksums, content negotiation, secrecy, mixed-version rollout, or hostile
decoder resource exhaustion. Do not generalize one host to an instruction-set
architecture or vendor family.
