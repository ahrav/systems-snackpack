# Topic 48 checked-host experiment

This harness compares demand-only access with one explicit low-locality read
prefetch. It uses fresh processes and complete order-balanced blocks. It retains
raw process output and separates initialization, warmup, and steady-state time.

## Freeze the source

From the repository root, commit the source-only artifact before collecting
final evidence. Then create an archive whose embedded source is the candidate:

```bash
source_commit=$(git rev-parse HEAD)
git archive --format=tar.gz --prefix="systems-snackpack-${source_commit}/" \
  --output="/tmp/topic48-${source_commit}.tar.gz" "$source_commit" -- \
  topics/048-hardware-software-prefetching
sha256sum "/tmp/topic48-${source_commit}.tar.gz"
```

The path-limited archive contains the complete Topic 48 artifact without
copying older topics and their raw receipts. Git still embeds `source_commit`
in the archive header, which the validator checks.

Transfer that same archive to each required host. Run the literal Arm target
and the runtime-resolved `xxl` target separately. Resolve and record `xxl`
before transfer; do not substitute a remembered hostname.

```bash
archive="/tmp/topic48-${source_commit}.tar.gz"
archive_root="systems-snackpack-${source_commit}"
tar -xOf "$archive" \
  "$archive_root/topics/048-hardware-software-prefetching/experiment/run_host.sh" |
  bash -s -- "$archive" "$source_commit" \
    "/tmp/topic48-${source_commit}-receipt"
```

This extracts the host runner from the sealed archive itself. It does not
depend on a separate repository checkout on the target.

The script records host identity and native target flags, builds the exact C
source, checks small demand and prefetch runs, inspects both linked kernels, and
runs these campaigns:

- randomized gather: five distances, four primary blocks each, and two A/A
  blocks, for 88 fresh processes;
- sequential control: distance 16, two primary blocks and two A/A blocks, for
  16 fresh processes.

It then validates the checksums, process schedule, fixed inputs, fault and
migration controls, page-advice result, binary identity, generated hint, receipt
manifest, and independently recomputed summaries.

## Inspect a receipt

```bash
python3 topics/048-hardware-software-prefetching/experiment/validate_receipts.py \
  /tmp/topic48-SOURCE-receipt --expected-source-commit SOURCE \
  --expected-hostname HOST --expected-uname-machine ARCH \
  --objdump objdump
jq '.summary' /tmp/topic48-SOURCE-receipt/random-analysis.json
rg -n 'prefetch|prfm' /tmp/topic48-SOURCE-receipt/codegen/kernel_prefetch.asm
```

The hostname and machine values come from the target you claim the receipt
represents; the validator compares them with the recorded host evidence.
`--objdump` regenerates the kernel disassembly from the retained binary and
checks the hint evidence against those bytes; omit it when no disassembler for
the receipt's architecture is available, which limits the codegen check to the
recorded text and reports `codegen_binding: recorded-text-only`.

The ratio is B/A: values below one favor the explicit hint. The Student-t
interval covers complete-block variation in this exact run window. It is not an
instruction-set, processor-family, or fleet interval.

## Controls and limitations

- Keep one source archive and one binary per host throughout collection.
- Keep every failed process. Do not replace an invalid block silently.
- Keep the production hardware-prefetch configuration unchanged.
- Do not treat loop accesses or the two passes as independent samples.
- `MADV_NOHUGEPAGE` is Linux's request not to use automatically managed
  transparent huge pages. Success records an accepted request, not the eventual
  page size. First-touch placement is inferred unless a page-location query
  records it separately.
- CPU pinning does not isolate frequency, interrupts, co-runners, or thermal
  effects.
- Timing and disassembly do not reveal the serving cache or prefetch mechanism.
