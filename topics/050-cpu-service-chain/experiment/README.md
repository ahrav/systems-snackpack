# Lock-holder preemption experiment

This experiment asks a narrow question: can a normal-priority CPU hog make a
short mutex critical section take much longer in wall time by delaying a
low-priority lock owner? It compares the same three-thread native workload with
the hog either pinned to the holder's logical CPU or pinned to a third physical
core.

The package measures one Linux host and observation window at a time. It does
not estimate a production latency distribution, compare instruction-set
architectures, test priority inheritance, or prove which scheduler event caused
every delay.

## Workload

[`lock_holder_preemption.c`](lock_holder_preemption.c) starts three POSIX
threads:

- The holder is pinned to one logical CPU, changes its nice value to `+19`,
  acquires a mutex, and consumes 5 milliseconds of thread CPU time while
  holding it.
- The waiter is pinned to a different physical core and records how long it
  waits for that mutex.
- The CPU hog runs at the default nice value. Treatment A pins it to the
  holder's logical CPU. Treatment B pins it to a third physical core.

The campaign is accepted only when its controller, waiter, and hog run under
the ordinary Linux `SCHED_OTHER` policy at static priority 0 and nice 0. Each
native row records those thread-level readbacks; the holder alone must
successfully change to nice +19. A batch, idle, deadline, or real-time launch
is rejected rather than silently changing the scheduler comparison.

The holder's thread CPU time is the fixed work control. Every accepted process
must report 4.9 through 6.0 milliseconds of holder CPU time. If that control
passes while holder wall time and the waiter's lock wait increase,
the observation is consistent with the holder being descheduled. Context-switch
counts support that interpretation but do not uniquely identify the scheduler
mechanism.

The two authorized hosts use GCC. The source applies GCC's `noinline`,
`noclone`, and `noipa` attributes to `burn_thread_cpu`, preventing inlining and
interprocedural cloning so the linked receipt contains the exact separately
inspectable burn-loop symbol used by the holder. This is a GCC boundary, not an
ISO C guarantee; the host runner rejects a different compiler for publication.

## Experimental units and stopping rule

[`run_processes.py`](run_processes.py) freezes the successful scratch design:

- Eight primary four-process blocks: four `ABBA` and four `BAAB` templates.
- Eight identical-artifact A/A four-process blocks: four `XYYX` and four
  `YXXY` templates. X and Y both use treatment B; only the label differs.
- Each period launches a fresh process. The 64 process identifiers must be
  unique.
- One complete four-period block is the analysis unit. Inner spin-loop
  iterations and individual process rows are not independent samples.
- Collection is fixed-horizon. The runner journals an attempt before launch,
  retains its raw output and final status, and never replaces a failure. It
  stops with an unsealed partial receipt after the first invalid attempt.

[`analyze.py`](analyze.py) reports per-label median and range, then computes the
mean paired log contrast across the eight complete blocks. It exponentiates
that contrast to obtain a geometric ratio and constructs a two-sided 95%
Student-t interval with seven degrees of freedom. The interval covers
block-to-block dispersion on that host during that run. It does not cover
machine, kernel, build, or workload populations.

The A/A interval is a mechanical label-path diagnostic. One eight-block A/A
campaign is not null calibration and must not be called a noise floor.

## Create the exact source archive on the controller

Run these commands from the repository root after the lesson commit exists:

```bash
source_commit=$(git rev-parse HEAD)
source_archive="/tmp/topic50-${source_commit}.tar.gz"
git archive --format=tar.gz \
  --prefix="systems-snackpack-${source_commit}/" \
  --output="$source_archive" "$source_commit" \
  topics/050-cpu-service-chain
source_archive_sha256=$(sha256sum "$source_archive" | awk '{print $1}')
```

The host runner rejects an archive whose SHA-256, embedded Git commit, unique
prefix, path boundary, or required file set differs from the controller's
values. It also compares the launcher being executed with the archived
`run_host.sh` before compiling.

## Resolve and probe the two authorized targets

The Arm target is literal. Resolve `xxl` for every campaign and retain this
controller evidence outside the host receipt:

```bash
arm_host=dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com
xxl_host=$(ssh -G xxl | rg '^hostname ' | awk '{print $2}')
ssh "$arm_host" 'hostname -f; uname -m; uname -a'
ssh xxl 'hostname -f; uname -m; uname -a'
```

The literal Arm host must report `aarch64`. The runtime-resolved `xxl` host
must report `x86_64`. The host runner checks the controller-supplied hostname
against `hostname -f`; it does not accept a hostname copied from the receipt as
controller evidence.

## Run one host

Upload the archive, extract a private launcher tree, and let the archived
launcher verify and re-extract the exact archive into separate private scratch:

```bash
target=xxl
target_label=xxl
expected_hostname="$xxl_host"
expected_architecture=x86_64
remote_archive="/tmp/topic50-${source_commit}.tar.gz"
remote_receipt="/tmp/topic50-${source_commit}-${target_label}-receipt"

scp "$source_archive" "$target:$remote_archive"
ssh "$target" "launcher=\$(mktemp -d); \
  tar -xzf '$remote_archive' -C \"\$launcher\"; \
  SOURCE_COMMIT='$source_commit' \
  SOURCE_ARCHIVE_SHA256='$source_archive_sha256' \
  SOURCE_ARCHIVE_PATH='$remote_archive' \
  bash \"\$launcher/systems-snackpack-${source_commit}/topics/050-cpu-service-chain/experiment/run_host.sh\" \
    '$remote_receipt' '$target_label' '$expected_hostname' '$expected_architecture'"
```

For Arm, set `target`, `target_label`, and `expected_hostname` to the literal
Arm hostname and set `expected_architecture=aarch64`.

The host runner performs these gates:

1. validates the authorized target identity and architecture;
2. validates and retains the exact source archive;
3. hashes every experiment source before execution;
4. builds the native program with `-O2 -g -std=c11 -Wall -Wextra -Werror -pthread`;
5. records architecture, hostname, kernel, compiler, CPU model/features,
   configured and allowed CPU counts, topology, effective affinity, nice and
   scheduler state, simultaneous-multithreading exposure, CPU-frequency
   exposure, and CPU-idle exposure;
6. rejects missing or malformed package/core/sibling sysfs topology, then
   chooses holder, waiter, and control CPUs from three distinct kernel-reported
   physical-core groups;
7. runs the fixed 64-process campaign and independent block analysis;
8. retains every raw stdout, stderr, status, command, binary hash, and journal
   event;
   every native row verifies start/end CPU placement for holder, waiter, and
   hog in addition to exact affinity and nice-value readback;
9. runs same-CPU and separate-core smoke checks using the campaign binary;
10. records linked `objdump`, `nm`, `file`, `ldd`, and build-ID output;
11. rehashes the source tree and rejects any mutation;
12. runs the independent validator, creates `MANIFEST.sha256`, writes a seal,
    removes write permission recursively, and validates the sealed receipt
    again.

Missing cpufreq or cpuidle sysfs files are recorded as unavailable. Their
absence is not rewritten as a claim that scaling or idle states are disabled.
Values such as current frequency and idle counters are snapshots, not proof of
their state throughout every process.

## Controller-side receipt validation

Archive the read-only receipt on the host, copy it to the controller, extract
it into a new directory, and validate it with the validator from the retained
source archive:

```bash
receipt_archive="/tmp/topic50-${source_commit}-${target_label}-receipt.tar.gz"
ssh "$target" "tar -C /tmp -czf '$receipt_archive' 'topic50-${source_commit}-${target_label}-receipt'"
scp "$target:$receipt_archive" /tmp/

receipt_extract=$(mktemp -d)
tar -xzf "/tmp/$(basename "$receipt_archive")" -C "$receipt_extract"
receipt_dir="$receipt_extract/topic50-${source_commit}-${target_label}-receipt"
source_extract=$(mktemp -d)
tar -xzf "$receipt_dir/source-archive.tar.gz" -C "$source_extract"
python3 "$source_extract/systems-snackpack-${source_commit}/topics/050-cpu-service-chain/experiment/validate_receipts.py" \
  "$receipt_dir" \
  --expected-target-label "$target_label" \
  --expected-hostname "$expected_hostname" \
  --expected-architecture "$expected_architecture" \
  --expected-source-commit "$source_commit" \
  --expected-source-archive-sha256 "$source_archive_sha256"
```

Keep the original compressed receipt, its controller-computed SHA-256, the
controller validation JSON, the `xxl` resolution record, and the exact source
commit together. A failed or partial campaign remains evidence but is excluded
from the point estimate and interval.

## Read the result

Inspect the independent summary and linked code generation:

```bash
python3 -m json.tool "$receipt_dir/experiment/summary.json"
rg -n 'holder_main|waiter_main|hog_main|burn_thread_cpu' "$receipt_dir/codegen"/*.asm
```

The primary decision signal is the A/B geometric ratio for holder wall time
and waiter wait time, checked against the nearly fixed holder CPU time. Report
Arm and x86 hosts separately. A difference between these two machines is a
host-specific observation, not an Arm-versus-x86 conclusion.
