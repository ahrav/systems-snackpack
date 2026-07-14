# Topic 3: Advanced Linux perf workflow

This crate supplies a deterministic two-phase workload for testing PMU skid,
precise sampling, and multiplex scaling. It does not wrap `perf` or interpret a
host automatically.

## Measurement model

For event rate `x(t)`, true event count is `C = integral(x(t) dt)`. When the
event owns a counter only during schedule mask `s(t)`, the raw count is
`c = integral(s(t) x(t) dt)`. Linux scales that raw count as:

```text
C_hat = c * time_enabled / time_running
```

Equivalently, `C_hat` extends the mean rate in scheduled windows across the
whole enabled interval. Its exact bias is:

```text
C_hat - C = time_enabled * (mean_rate_scheduled - mean_rate_full)
```

The running percentage measures counter residency. It does not bound scaling
error. A counter can run for 90% of an execution and miss the only phase that
produces its event.

A strong group, `{cycles,instructions}`, schedules all members together or not
at all. It preserves simultaneous ratio inputs. It does not make the scheduled
windows representative. A weak `:W` group can fall back to independent
scheduling, which removes the simultaneity guarantee. Separate passes avoid
multiplex scaling but require a deterministic workload and stable host.

## Sampling model

Sampling has five separate stages:

1. an event occurs;
2. a counter crosses its sampling threshold;
3. hardware captures state;
4. the kernel records the sample;
5. user space drains the ring buffer.

Ordinary interrupt sampling can capture an instruction after the event. That
distance is skid. `precise_ip` requests tighter attribution, but the event and
PMU determine support. A record marked `PERF_RECORD_MISC_EXACT_IP` reports exact
IP attribution for that sample.

Intel PEBS, AMD IBS, and Arm SPE are not interchangeable precision levels.
They select different operations, use different record formats, and expose
different collision or shadowing behavior. On AMD, requesting a precise alias
can switch from a core-PMU event to IBS. Record the resolved event with
`perf evlist -v`; do not describe the change as skid reduction alone.

For period `P`, expected records are approximately `event_count / P`. For
frequency `F`, expected records are approximately `F * CPU-active seconds`, but
the kernel adjusts the period and can throttle collection. Approximate CPU cost
is:

```text
sample_rate * (overflow + capture + unwind + copy cost)
```

More samples reduce random error. They do not remove skid, phase aliasing,
sample shadowing, collisions, throttling, loss, or symbolization errors.

## Failure gates

Reject or qualify a run when any of these conditions holds:

- a required event is unsupported, not counted, or has zero running time;
- a strong ratio group cannot schedule;
- CPU migration crosses PMU types on a hybrid processor;
- sampling reports throttling, lost records, or more than 5% wall-time overhead;
- the profile and annotated binary have different build IDs;
- the requested precise mechanism is unavailable or resolves to another event;
- a non-multiplexed reference has a coefficient of variation above 2%.

The 5% overhead and 2% variation limits are experiment policy, not kernel
guarantees. Normal ring-buffer mode can report lost records. Overwrite mode
discards old data by design, so an absent loss record does not prove a complete
profile.

## Focused experiment: phase-coupled multiplexing

Run this experiment on Linux. First record the environment and PMU constraints:

```bash
perf version
uname -a
lscpu
cat /proc/sys/kernel/perf_event_paranoid
cat /proc/sys/kernel/nmi_watchdog
cat /sys/devices/cpu/perf_event_mux_interval_ms 2>/dev/null || true
perf list --details branches branch-misses cycles instructions \
  cache-references cache-misses ref-cycles bus-cycles
```

Build with debug information and frame pointers. Inspect the generated code.
The branch phase must contain a data-dependent conditional branch. The
arithmetic phase can contain a loop branch but no data-dependent branch.

```bash
RUSTFLAGS='-C debuginfo=2 -C force-frame-pointers=yes' \
  cargo build --release -p systems-snackpack-topic-003 --example perf_workload
objdump -drwC --no-show-raw-insn \
  target/release/examples/perf_workload > /tmp/perf-workload.asm
```

Pin one homogeneous CPU. Store each repetition separately so the decision rule
can inspect nine independent event counts and checksums. Run this block and
every block after it in one shell session: `set -euo pipefail` makes a missing
tool or a failed `perf stat` abort the sequence instead of leaving empty output
files that read as valid data.

```bash
set -euo pipefail

CPU=2
BIN=target/release/examples/perf_workload
OUT=/tmp/perf-mux-topic-003
mkdir -p "$OUT"

measure_reference() {
  name=$1
  rounds=$2
  iterations=$3
  run=$4
  taskset -c "$CPU" perf stat -x ';' \
    -o "$OUT/$name-reference-$run.csv" \
    -e '{branches:u,branch-misses:u}' \
    -- "$BIN" "$rounds" "$iterations" \
    >"$OUT/$name-reference-$run.out"
  awk -F';' '/^#/ || NF < 5 { next }
    $1 ~ /^</ || $5 + 0 < 100 {
      printf "reject %s: %s ran %s%% of enabled time\n", FILENAME, $3, $5
      exit 1
    }' "$OUT/$name-reference-$run.csv"
}
```

The reference is a baseline only while its counters never multiplex. The `awk`
gate reads the run-time and residency fields that `perf stat -x` emits with
each event row and fails the sequence when any row reports `<not counted>` or
less than 100% running; a multiplexed reference biases every later comparison.

Request distinct supported events until the PMU must multiplex. The two strong
groups keep IPC and branch-miss ratio inputs simultaneous. The other events
consume counter capacity. Remove unsupported events or add supported events for
the host before collecting the nine-run series.

```bash
measure_multiplexed() {
  name=$1
  rounds=$2
  iterations=$3
  mode=$4
  run=$5
  extra=()
  if [ "$mode" = raw ]; then
    extra=(--no-scale)
  fi

  taskset -c "$CPU" perf stat "${extra[@]}" -x ';' \
    -o "$OUT/$name-$mode-$run.csv" \
    -e '{cycles:u,instructions:u}' \
    -e '{branches:u,branch-misses:u}' \
    -e cache-references:u -e cache-misses:u \
    -e ref-cycles:u -e bus-cycles:u \
    -- "$BIN" "$rounds" "$iterations" \
    >"$OUT/$name-$mode-$run.out"
}
```

Add events if every row remains at or above 90% running. If a strong group is
not counted, record the counter constraint; do not weaken it and claim a
simultaneous ratio. The `raw` cases retain only events observed while each
counter ran.

Sweep phase duration while holding total inner-loop iterations constant:

```bash
# Each case completes 400 million inner-loop iterations.
measure_phase() {
  name=$1
  rounds=$2
  iterations=$3
  run=$4
  measure_reference "$name" "$rounds" "$iterations" "$run"
  measure_multiplexed "$name" "$rounds" "$iterations" scaled "$run"
  measure_multiplexed "$name" "$rounds" "$iterations" raw "$run"
}

for run in $(seq 1 9); do
  if ((run % 2 == 1)); then
    measure_phase short 10000 20000 "$run"
    measure_phase long 100 2000000 "$run"
  else
    measure_phase long 100 2000000 "$run"
    measure_phase short 10000 20000 "$run"
  fi
done
```

Expected observations:

- raw counts fall as running percentage falls;
- scaled counts approach the reference when scheduled windows represent both
  phases;
- long phases can produce larger deviations from their matching reference when
  PMU rotation aligns with one phase;
- strong-group miss ratios stay co-temporal but can remain phase-biased.

The loop rotates short- and long-phase case order. Keep the CPU, binary, event
scope, watchdog state, input seed, and background load fixed. Require matching
checksums. Claim phase-coupled bias only when a scaled
branch-group estimate differs from its phase-matched reference median by more
than `max(5%, 3 * reference CV)` in at least six of nine stored runs. A result
below that threshold applies only to this host and phase pattern.

Compare approximate and maximum-supported precision with a fixed prime period:

```bash
taskset -c "$CPU" perf record -o cycles.data \
  -e cycles:u -c 100003 --call-graph fp -- "$BIN" 400 250000
taskset -c "$CPU" perf record -o cycles-precise.data \
  -e cycles:uP -c 100003 --call-graph fp -- "$BIN" 400 250000
perf evlist -v -i cycles-precise.data
for capture in cycles cycles-precise; do
  perf report -i "$capture.data" --stats > "$OUT/$capture-stats.txt"
  perf script -i "$capture.data" --show-lost-events \
    | awk '/LOST/' > "$OUT/$capture-lost-events.txt"
done
```

Both captures keep an auditable statistics and loss report. An empty loss file
records that no loss event appeared; the failure gates above explain why that
still does not prove a complete profile in overwrite mode.

This comparison measures the profiles produced by two resolved event
configurations. A changed histogram can support a skid hypothesis, but it does
not prove that skid caused the change. Unsupported precision, event remapping,
throttling, or loss blocks that conclusion.

Run the portable example and local elapsed-time benchmark:

```bash
cargo run -p systems-snackpack-topic-003 --example perf_workload -- 400 250000
cargo bench -p systems-snackpack-topic-003 --bench phase_workload
```

See [references](references.md) for the kernel ABI, tool manuals, architecture
documentation, and empirical multiplexing studies.
