# Topic 49 checked-host experiment

This harness measures a dependent chain with idle workers and with the same
workers consuming private read-only buffers. It uses fresh processes, complete
order-balanced blocks, fixed stopping, and an independent A/A path check.

The result is a black-box loaded-treatment observation. It does not decode DRAM
rows, banks, channels, refresh, queue state, or controller scheduling.

## Freeze the source

Commit the source-only Topic 49 artifact before final collection. From the
repository root:

```bash
source_commit=$(git rev-parse HEAD)
archive="/tmp/topic49-${source_commit}.tar.gz"
archive_root="systems-snackpack-${source_commit}"

git archive --format=tar.gz --prefix="${archive_root}/" \
  --output="$archive" "$source_commit" -- \
  topics/049-dram-memory-controller-behavior

archive_sha256=$(shasum -a 256 "$archive" | cut -d' ' -f1)
printf '%s  %s\n' "$archive_sha256" "$archive"
```

The path-limited archive contains the complete Topic 49 crate and embeds the
source commit in Git archive metadata. The host runner checks both the
controller-supplied digest and embedded commit before compiling.

## Resolve and probe both targets

Resolve `xxl` for this run and record its backing host:

```bash
ssh -G xxl | rg '^hostname '
ssh xxl 'hostname -f; uname -m'
ssh dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
  'hostname -f; uname -m'
```

Reject the run unless `xxl` reports `x86_64` and the literal Arm target reports
`aarch64`. Keep the alias, configured hostname, runtime hostname, and
architecture in controller evidence outside the receipt.

## Run one host from the sealed archive

Transfer the same archive to both targets. On each target, verify the
controller-supplied digest before extraction. Extract only a launcher copy of
the archived runner, then execute it with the exact archive identity:

```bash
remote_archive="/tmp/topic49-${source_commit}.tar.gz"
receipt="/tmp/topic49-${source_commit}-HOST-receipt"
launcher="/tmp/topic49-${source_commit}-HOST-launcher"

printf '%s  %s\n' "$archive_sha256" "$remote_archive" |
  sha256sum --check --strict -
mkdir -p "$launcher"
tar -xzf "$remote_archive" -C "$launcher" \
  "${archive_root}/topics/049-dram-memory-controller-behavior/experiment/run_host.sh"

SOURCE_COMMIT="$source_commit" \
SOURCE_ARCHIVE_SHA256="$archive_sha256" \
SOURCE_ARCHIVE_PATH="$remote_archive" \
bash "$launcher/${archive_root}/topics/049-dram-memory-controller-behavior/experiment/run_host.sh" \
  "$receipt" TARGET_LABEL EXPECTED_HOSTNAME EXPECTED_ARCHITECTURE
```

Use target label `xxl` for the runtime-resolved x86-64 host. Use the full
literal Arm hostname as both target label and expected hostname. Supply the
controller-observed runtime hostname and architecture; do not derive them from
the receipt being validated.

The runner verifies that CPU 0 and CPUs 1 through 8 are online, allowed,
distinct physical cores on one NUMA node. Pass an explicit probe CPU and eight
comma-separated worker CPUs as two final arguments only when the default set
fails that topology gate. Record the reason and selected topology before the
run.

## What the runner retains

The runner:

1. verifies archive, commit, host, architecture, and CPU topology;
2. records kernel, CPU, cache, NUMA, page, cgroup, compiler, PMU, and load data;
3. requires GCC 11.5.0, records its resolved path and verbose version plus the
   Python version, then compiles one native binary and copies identical bytes to
   two paths;
4. runs idle and loaded smoke checks;
5. retains the binary, build identifier, runtime identity, and linked
   disassembly for the walker, stream, page preparation, and timed caller;
6. runs 12 main blocks and four A/A blocks, or 64 fresh processes;
7. retains every standard-output, standard-error, status, and parsed attempt;
8. journals each attempt before launch and records its final outcome;
9. validates the campaign with a standalone verifier that does not import the
   runner or analyzer, then seals the receipt manifest;
10. removes write permission and revalidates the sealed receipt.

Every process binds its allocation policy to the selected NUMA node with
`MPOL_BIND` before creating its mappings. Every fresh period then builds a 512
MiB large cycle, an 8 KiB small control, and
eight 128 MiB worker buffers. The runner uses a 750 ms treatment warmup and a
one-second quiet interval between periods. A process timeout, malformed result,
fault, migration, checksum failure, or identity change remains in the receipt
and fails the fixed acquisition.

## Inspect and package a receipt

Validate a copied receipt against the controller evidence:

```bash
python3 topics/049-dram-memory-controller-behavior/experiment/validate_receipts.py \
  /path/to/receipt \
  --expected-target-label TARGET_LABEL \
  --expected-hostname EXPECTED_HOSTNAME \
  --expected-architecture EXPECTED_ARCHITECTURE \
  --expected-source-commit "$source_commit" \
  --expected-source-archive-sha256 "$archive_sha256" \
  --output /tmp/topic49-validation.json

python3 -m json.tool /path/to/receipt/experiment/summary.json | sed -n '1,240p'
rg -n 'ldr|mov|vmov|zmm|ymm|xmm' /path/to/receipt/codegen/*.asm
```

Preserve the original receipt as a compressed archive. Compute its SHA-256 on
the controller, extract it into a new directory, and rerun the validator before
publishing the archive and digest under `measurements/raw/`.

## Controls and limitations

- Keep one source archive and one native binary per host.
- Leave hardware prefetch controls in their production state.
- Treat one complete four-process block as one replication.
- Do not replace a failed period or extend collection after inspecting data.
- `MADV_NOHUGEPAGE` records an accepted Linux request. Mapping-specific
  `/proc/self/smaps` fields provide the page-state evidence.
- `MPOL_BIND` restricts new anonymous allocations to the selected NUMA node.
  The successful system call is part of each result. The receipt does not query
  every page's final physical location.
- The receipt records `/proc/sys/kernel/numa_balancing` as the host's automatic
  NUMA-balancing setting. CPU pinning and first touch do not imply that the
  kernel will leave pages in their initial placement.
- Source-byte bounds do not equal cache, interconnect, or controller traffic.
- Worker source-byte rates cover the full run epoch: worker release, the
  all-worker first-chunk acknowledgement, the small control, the large probe,
  stop publication, and worker drain and termination. The end timestamp is
  recorded only after every worker joins, so every worker source read is inside
  the rate denominator. These are not rates for the large probe alone.
- Each loaded worker reports its own complete-chunk count. The lower bound is
  the sum of those counts. The inclusive upper bound adds at most one 256 KiB
  chunk per worker, so actual source bytes are less than or equal to that
  bound. Idle byte and rate bounds are exactly zero.
- Minor faults, major faults, and voluntary and involuntary context switches
  are reported twice around the large dependent walk: process-wide
  `getrusage(RUSAGE_SELF)` deltas and probe-thread-only
  `getrusage(RUSAGE_THREAD)` deltas. Any process-wide minor or major fault in
  that window fails the period. The full-process `total_major_faults` check
  still covers the entire invocation.
- A stable small control only weakens explanations that would affect both its
  short window and the later large-walk window uniformly. It does not exclude
  scheduler activity or other work specific to the large-walk window.
- CPU pinning does not isolate interrupts, co-runners, thermal state, or
  persistent host effects.
