# Focused frontend-layout experiment

The generator emits 512 externally visible leaf functions with identical source
and control flow. The Linux runner compiles that source twice. Every compiler
input is equal except `FUNC_ALIGN`: `dense16` requests 16-byte function
alignment and `sparse4096` requests 4096-byte alignment. The analysis assigns
arm labels outside the generated program.

The treatment is intentionally composite. It changes final executable layout,
instruction footprint, translation footprint, and branch-target spacing. A
timing difference establishes a layout cost for this workload. It cannot isolate
L1I, instruction-TLB, decoded-operation-cache, prediction, or prefetch effects.

Run from an exact clean checkout:

```sh
topic=topics/019-cpu-frontend-bottlenecks
"$topic/experiment/run_remote.sh" "$PWD" /tmp/topic19-evidence
```

For an extracted Git archive, declare the source identity:

```sh
SOURCE_COMMIT=<40-hex-commit> \
SOURCE_ARCHIVE_SHA256=<64-hex-archive-digest> \
RUNTIME_HOST_ALIAS=<ssh-alias> \
topics/019-cpu-frontend-bottlenecks/experiment/run_remote.sh \
    "$PWD" /tmp/topic19-evidence
```

The runner chooses the first allowed CPU unless a numeric CPU is the third
argument. It generates and builds under an ephemeral directory, writes evidence
outside the source tree, and verifies that the source manifest is unchanged.

The primary comparison uses 12 complete process blocks, alternating `ABBA` and
`BAAB`. Every letter launches a fresh pinned process. The internal
`CLOCK_MONOTONIC_RAW` timer starts after 512 untimed warm-up rounds; compilation
and process startup are excluded. The analysis reports the geometric
`sparse4096/dense16` ratio, 12 block analysis units, log-contrast dispersion, and
a 95% Student-t confidence interval for that geometric-mean ratio, computed from
between-block dispersion. It is not a prediction interval for an individual
block, which would be wider.

An identical-artifact A/A control uses two hard links to the dense ELF and the
same schedule. It checks launch-label and analysis symmetry, not independent
build variation or a false-positive rate.

The runner also retains:

- checksum smoke tests, with command, status, and output, and all process
  attempts;
- ELF hashes, sections, program headers, symbols, and disassembly;
- a machine-checked 512-leaf layout invariant;
- order-balanced `perf stat` passes with counter running fractions;
- host, kernel, CPU, compiler, native target flags, and build commands;
- workspace validation logs and before/after source manifests.

Expected observations are a larger `.text` footprint and wider leaf-address
spacing for `sparse4096`. Timing and counters are empirical outcomes, not
assumptions. A virtualized or unsupported PMU event may fail or report literal
zero; retain that result and do not interpret it as absence of activity.
