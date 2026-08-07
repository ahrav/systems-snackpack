#!/usr/bin/env bash
set -Eeuo pipefail

# BASH_ENV/ENV startup hooks run before line 1 and can mutate arguments or
# shadow commands; re-exec cannot undo them, so refuse instead.
if [[ -n ${BASH_ENV-} || -n ${ENV-} ]]; then
  printf 'refusing to run: BASH_ENV or ENV startup hooks are unrecorded\n' >&2
  exit 2
fi
if [[ -n $(declare -F) ]]; then
  printf 'refusing to run: inherited shell functions are unrecorded\n' >&2
  exit 2
fi

if [[ $# -ne 4 ]]; then
  printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY HOST_LABEL SOURCE_COMMIT\n' "$0" >&2
  exit 2
fi
if [[ $(uname -s) != Linux ]]; then
  printf 'this experiment requires Linux taskset and procfs\n' >&2
  exit 2
fi

repository_root=$(cd "$1" && pwd -P)
output_directory=$(realpath -m -- "$2")
host_label=$3
source_commit=$4
topic=topics/027-queueing-service-design
run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
cargo_scratch_directory=
failure_reason=
failure_line=
failure_command=
failure_exit_code=

fail() {
  failure_reason=$1
  printf '%s\n' "$failure_reason" >&2
  exit "${2:-2}"
}

append_failure_reason() {
  if [[ -n $failure_reason ]]; then
    failure_reason="$failure_reason; $1"
  else
    failure_reason=$1
  fi
}

capture_error() {
  failure_exit_code=$1
  failure_line=$2
  failure_command=$3
  return "$failure_exit_code"
}

write_tracked_source_manifest() {
  local manifest=$1
  (
  cd "$repository_root"
  "${git_path:-git}" ls-files | LC_ALL=C sort | while IFS= read -r source_file; do
      sha256sum -- "$source_file" || exit 1
    done
  ) > "$manifest"
}

cleanup_scratch() {
  if [[ -z ${cargo_scratch_directory:-} || ! -e $cargo_scratch_directory ]]; then
    return 0
  fi
  if [[ ! -f $cargo_scratch_directory/.topic27-cargo-scratch ]]; then
    printf 'refusing to remove unverified scratch path: %s\n' "$cargo_scratch_directory" >&2
    return 1
  fi
  rm -rf -- "$cargo_scratch_directory"
}

write_run_status() {
  local final_status=$1
  local source_manifest_match=$2
  local head_match=$3
  local clean_worktree=$4
  local seal_state=$5
  local outcome=failed
  if (( final_status == 0 )); then
    outcome=success
  fi
  {
    printf 'status=%s\n' "$outcome"
    printf 'exit_code=%s\n' "$final_status"
    printf 'run_started_utc=%s\n' "$run_started_utc"
    printf 'run_finished_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
    printf 'alias_label=%q\n' "$host_label"
    printf 'source_commit_expected=%q\n' "$source_commit"
    printf 'tracked_source_manifest_match=%s\n' "$source_manifest_match"
    printf 'final_head_match=%s\n' "$head_match"
    printf 'final_clean_worktree=%s\n' "$clean_worktree"
    printf 'evidence_seal=%s\n' "$seal_state"
    printf 'failure_reason=%q\n' "$failure_reason"
    printf 'failure_exit_code=%q\n' "$failure_exit_code"
    printf 'failure_line=%q\n' "$failure_line"
    printf 'failure_command=%q\n' "$failure_command"
  } > "$output_directory/run.status"
}

seal_evidence() {
  (
    cd "$output_directory"
    find . -type f ! -path './evidence.sha256' -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum > evidence.sha256
    sha256sum --check --quiet evidence.sha256
  )
}

finalize_run() {
  local final_status=$1
  local source_manifest_match=not-recorded
  local head_match=not-checked
  local clean_worktree=not-checked
  local current_head=
  trap - EXIT ERR INT TERM
  set +e

  if write_tracked_source_manifest "$output_directory/source-files.after.sha256"; then
    if [[ -f $output_directory/source-files.before.sha256 ]] \
      && cmp -s "$output_directory/source-files.before.sha256" \
        "$output_directory/source-files.after.sha256"; then
      source_manifest_match=passed
    else
      source_manifest_match=failed
      final_status=1
      append_failure_reason 'tracked source manifest changed during the run'
    fi
  else
    source_manifest_match=failed
    final_status=1
    append_failure_reason 'could not record the final tracked source manifest'
  fi

  if current_head=$("${git_path:-git}" -C "$repository_root" rev-parse HEAD 2>/dev/null); then
    printf '%s\n' "$current_head" > "$output_directory/source-head.after.txt"
    if [[ $current_head == "$source_commit" ]]; then
      head_match=passed
    else
      head_match=failed
      final_status=1
      append_failure_reason 'HEAD changed during the run'
    fi
  else
    head_match=failed
    final_status=1
    append_failure_reason 'could not resolve final HEAD'
  fi

  if "${git_path:-git}" -C "$repository_root" status --porcelain=v1 --untracked-files=all \
    > "$output_directory/source-status.after.txt"; then
    if [[ -s $output_directory/source-status.after.txt ]]; then
      clean_worktree=failed
      final_status=1
      append_failure_reason 'source worktree changed during the run'
    else
      clean_worktree=passed
    fi
  else
    clean_worktree=failed
    final_status=1
    append_failure_reason 'could not inspect the final source worktree'
  fi

  if ! cleanup_scratch; then
    final_status=1
    append_failure_reason 'could not remove the verified Cargo scratch directory'
  fi

  if (( final_status != 0 )) && [[ -z $failure_reason ]]; then
    failure_reason='run failed'
  fi
  write_run_status "$final_status" "$source_manifest_match" "$head_match" \
    "$clean_worktree" validated
  if ! seal_evidence; then
    final_status=1
    append_failure_reason 'evidence SHA-256 manifest generation or validation failed'
    write_run_status "$final_status" "$source_manifest_match" "$head_match" \
      "$clean_worktree" validation-failed
    if ! seal_evidence; then
      printf 'failed to seal evidence directory: %s\n' "$output_directory" >&2
    fi
  fi
  exit "$final_status"
}

if [[ -z $host_label || $host_label == *$'\n'* ]]; then
  fail 'host label must be nonempty and single-line'
fi
if [[ -z $source_commit || $source_commit == *$'\n'* ]]; then
  fail 'source commit must be nonempty and single-line'
fi
if [[ -e $output_directory ]]; then
  fail "output directory already exists: $output_directory"
fi
if [[ $output_directory == "$repository_root" || $output_directory == "$repository_root"/* ]]; then
  fail 'output directory must be outside the repository'
fi
mkdir -p "$output_directory"/{artifacts,codegen,gates}

trap 'capture_error "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap 'failure_reason="received SIGINT"; exit 130' INT
trap 'failure_reason="received SIGTERM"; exit 143' TERM
trap 'finalize_run "$?"' EXIT

environment_candidates=(
  AR ARFLAGS AS CC CFLAGS CPP CPPFLAGS CXX CXXFLAGS LD LDFLAGS LIBRARY_PATH
  CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH DYLD_LIBRARY_PATH GLIBC_TUNABLES
  LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
  MALLOC_ARENA_MAX MALLOC_ARENA_TEST MALLOC_CHECK_ MALLOC_MMAP_MAX_
  MALLOC_MMAP_THRESHOLD_ MALLOC_PERTURB_ MALLOC_TOP_PAD_ MALLOC_TRIM_THRESHOLD_
  LANG LANGUAGE LC_ALL LC_CTYPE MACOSX_DEPLOYMENT_TARGET MAKEFLAGS NM NUM_JOBS OBJCOPY OBJDUMP PKG_CONFIG
  PKG_CONFIG_PATH RANLIB SDKROOT SOURCE_DATE_EPOCH STRIP TZ ZERO_AR_DATE
  CARGO CARGO_BUILD_JOBS CARGO_BUILD_RUSTFLAGS CARGO_BUILD_TARGET CARGO_ENCODED_RUSTFLAGS
  CARGO_HOME CARGO_INCREMENTAL CARGO_MAKEFLAGS CARGO_NET_OFFLINE CARGO_TARGET_DIR
  RUSTC RUSTC_BOOTSTRAP RUSTC_LOG RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER
  RUSTDOC RUSTDOCFLAGS RUSTFLAGS RUSTUP_TOOLCHAIN
  CONDA_PREFIX PYTHONBREAKPOINT PYTHONCOERCECLOCALE PYTHONDONTWRITEBYTECODE
  PYTHONHASHSEED PYTHONHOME PYTHONINSPECT PYTHONINTMAXSTRDIGITS PYTHONIOENCODING
  PYTHONMALLOC PYTHONOPTIMIZE PYTHONPATH PYTHONPYCACHEPREFIX PYTHONSAFEPATH
  PYTHONSTARTUP PYTHONUTF8 PYTHONWARNINGS VIRTUAL_ENV
)
while IFS= read -r environment_name; do
  case "$environment_name" in
    CARGO_BUILD_*|CARGO_PROFILE_*|CARGO_TARGET_*)
      environment_candidates+=("$environment_name")
      ;;
  esac
done < <(compgen -e)
mapfile -t swept_environment_names < <(
  printf '%s\n' "${environment_candidates[@]}" | LC_ALL=C sort -u
)
{
  for environment_name in "${swept_environment_names[@]}"; do
    if [[ -v $environment_name ]]; then
      printf '%s=%q\n' "$environment_name" "${!environment_name}"
    else
      printf '%s=<unset>\n' "$environment_name"
    fi
  done
} > "$output_directory/environment.swept.txt"
for environment_name in "${swept_environment_names[@]}"; do
  unset "$environment_name"
done

# glibc preloads /etc/ld.so.preload entries even with LD_PRELOAD unset.
if [[ -s /etc/ld.so.preload ]]; then
  fail 'non-empty /etc/ld.so.preload would interpose unrecorded libraries'
fi

# GIT_* variables can repoint the identity checks below at a different tree,
# and a PATH wrapper can misreport source identity. Record Git's PATH
# resolution, then clear GIT_* variables before the source-identity checks.
git_path=$(command -v git)
git_path=$(readlink -f "$git_path")
{
  printf 'git_path=%s\n' "$(command -v git)"
  printf 'git_resolved_path=%s\n' "$git_path"
  "$git_path" --version
  while IFS= read -r environment_name; do
    case "$environment_name" in
      GIT_*)
        printf '%s=%q\n' "$environment_name" "${!environment_name}"
        unset "$environment_name"
        ;;
    esac
  done < <(compgen -e)
} > "$output_directory/git-provenance.txt"

cd "$repository_root"
"$git_path" rev-parse HEAD > "$output_directory/source-head.before.txt"
if [[ $(<"$output_directory/source-head.before.txt") != "$source_commit" ]]; then
  fail 'source commit does not match HEAD'
fi
"$git_path" status --porcelain=v1 --untracked-files=all \
  > "$output_directory/source-status.before.txt"
if [[ -s $output_directory/source-status.before.txt ]]; then
  fail 'exact-source run requires a clean worktree'
fi
write_tracked_source_manifest "$output_directory/source-files.before.sha256"

"$git_path" archive --format=tar "$source_commit" \
  | gzip -n -9 > "$output_directory/source.tar.gz"
(
  cd "$output_directory"
  sha256sum source.tar.gz > source-archive.sha256
  sha256sum --check --quiet source-archive.sha256
)

scratch_parent=${TMPDIR:-/tmp}
cargo_scratch_directory=$(mktemp -d "$scratch_parent/topic27-queueing-build.XXXXXXXX")
cargo_scratch_directory=$(cd "$cargo_scratch_directory" && pwd -P)
if [[ $cargo_scratch_directory == "$repository_root" \
  || $cargo_scratch_directory == "$repository_root"/* \
  || $cargo_scratch_directory == "$output_directory" \
  || $cargo_scratch_directory == "$output_directory"/* ]]; then
  fail 'Cargo scratch directory must be outside the repository and evidence directory'
fi
touch "$cargo_scratch_directory/.topic27-cargo-scratch"
mkdir -p "$cargo_scratch_directory"/{cargo-home,python-cache,target}

export CARGO_HOME="$cargo_scratch_directory/cargo-home"
export CARGO_INCREMENTAL=0
export CARGO_NET_OFFLINE=true
export CARGO_TARGET_DIR="$cargo_scratch_directory/target"
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$cargo_scratch_directory/python-cache"
export TZ=UTC
{
  printf 'CARGO_HOME=%q\n' "$CARGO_HOME"
  printf 'CARGO_INCREMENTAL=%q\n' "$CARGO_INCREMENTAL"
  printf 'CARGO_NET_OFFLINE=%q\n' "$CARGO_NET_OFFLINE"
  printf 'CARGO_TARGET_DIR=%q\n' "$CARGO_TARGET_DIR"
  printf 'HOME=%q\n' "$HOME"
  printf 'LC_ALL=%q\n' "$LC_ALL"
  printf 'PATH=%q\n' "$PATH"
  printf 'PYTHONDONTWRITEBYTECODE=%q\n' "$PYTHONDONTWRITEBYTECODE"
  printf 'PYTHONPYCACHEPREFIX=%q\n' "$PYTHONPYCACHEPREFIX"
  printf 'RUSTFLAGS=<unset-for-gates>\n'
  printf 'RUSTUP_HOME=%q\n' "${RUSTUP_HOME-<unset>}"
  printf 'TZ=%q\n' "$TZ"
} > "$output_directory/environment.effective.txt"

allowed_list=$(awk '/^Cpus_allowed_list:/ {print $2}' /proc/self/status)
if [[ -z $allowed_list ]]; then
  fail 'could not resolve the process CPU affinity list'
fi
selected_cpus=()
IFS=',' read -r -a cpu_parts <<< "$allowed_list"
for part in "${cpu_parts[@]}"; do
  if [[ $part =~ ^([0-9]+)-([0-9]+)$ ]]; then
    first=${BASH_REMATCH[1]}
    last=${BASH_REMATCH[2]}
    if (( last < first )); then
      fail "invalid CPU range in affinity list: $part"
    fi
    for ((cpu=first; cpu<=last; cpu++)); do
      selected_cpus+=("$cpu")
      if (( ${#selected_cpus[@]} == 2 )); then
        break 2
      fi
    done
  elif [[ $part =~ ^[0-9]+$ ]]; then
    selected_cpus+=("$part")
    if (( ${#selected_cpus[@]} == 2 )); then
      break
    fi
  else
    fail "invalid CPU entry in affinity list: $part"
  fi
done
if (( ${#selected_cpus[@]} != 2 )); then
  fail 'the open generator and worker require two allowed CPUs'
fi
cpu_list=$(IFS=,; printf '%s' "${selected_cpus[*]}")

resolved_hostname=$(hostname -f)
if [[ -z $resolved_hostname ]]; then
  fail 'could not resolve the host FQDN'
fi
clocksource_file=/sys/devices/system/clocksource/clocksource0/current_clocksource
if [[ ! -r $clocksource_file ]]; then
  fail "current clocksource is not readable: $clocksource_file"
fi
current_clocksource=$(<"$clocksource_file")
taskset_path=$(command -v taskset)
taskset_path=$(readlink -f "$taskset_path")
{
  printf 'alias_label=%s\n' "$host_label"
  printf 'resolved_hostname=%s\n' "$resolved_hostname"
  printf 'kernel_hostname=%s\n' "$(hostname)"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'run_started_utc=%s\n' "$run_started_utc"
  printf 'uname=%s\n' "$(uname -a)"
  printf 'architecture=%s\n' "$(uname -m)"
  printf 'kernel_release=%s\n' "$(uname -r)"
  printf 'kernel_version=%s\n' "$(uname -v)"
  printf 'configured_cpus_nproc=%s\n' "$(nproc --all)"
  printf 'available_cpus_nproc=%s\n' "$(nproc)"
  printf 'configured_cpus_getconf=%s\n' "$(getconf _NPROCESSORS_CONF)"
  printf 'online_cpus_getconf=%s\n' "$(getconf _NPROCESSORS_ONLN)"
  printf 'allowed_cpu_list=%s\n' "$allowed_list"
  printf 'selected_cpu_list=%s\n' "$cpu_list"
  printf 'selected_cpu_count=%s\n' "${#selected_cpus[@]}"
  printf 'current_clocksource=%s\n' "$current_clocksource"
  if [[ -r /sys/devices/system/clocksource/clocksource0/available_clocksource ]]; then
    printf 'available_clocksources=%s\n' \
      "$(</sys/devices/system/clocksource/clocksource0/available_clocksource)"
  fi
  for cpu_state in possible present online offline; do
    if [[ -r /sys/devices/system/cpu/$cpu_state ]]; then
      printf 'cpu_%s=%s\n' "$cpu_state" "$(</sys/devices/system/cpu/$cpu_state)"
    fi
  done
  "$taskset_path" -pc "$$"
  awk '/^Cpus_allowed(_list)?:/ {print}' /proc/self/status
  printf 'proc_version=%s\n' "$(</proc/version)"
  lscpu
  awk -F: '/^(vendor_id|model name|cpu family|model|stepping|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision)/ { if (!seen[$1]++) print }' /proc/cpuinfo
  if [[ -r /sys/devices/system/cpu/cpu0/regs/identification/midr_el1 ]]; then
    printf 'MIDR_EL1=%s\n' "$(</sys/devices/system/cpu/cpu0/regs/identification/midr_el1)"
  fi
} > "$output_directory/host.txt"

cc_path=$(command -v cc)
rustc_path=$(command -v rustc)
cargo_path=$(command -v cargo)
python_path=$(command -v python3)
{
  printf 'cc_path=%s\n' "$cc_path"
  printf 'cc_resolved_path=%s\n' "$(readlink -f "$cc_path")"
  cc --version 2>&1
  if cc -dumpmachine > /dev/null 2>&1; then
    printf 'cc_target=%s\n' "$(cc -dumpmachine)"
  fi
  printf 'rustc_path=%s\n' "$rustc_path"
  printf 'rustc_resolved_path=%s\n' "$(readlink -f "$rustc_path")"
  rustc -vV
  printf 'cargo_path=%s\n' "$cargo_path"
  printf 'cargo_resolved_path=%s\n' "$(readlink -f "$cargo_path")"
  cargo -Vv
  printf 'taskset_path=%s\n' "$(command -v taskset)"
  printf 'taskset_resolved_path=%s\n' "$taskset_path"
  "$taskset_path" --version
  printf 'python_path=%s\n' "$python_path"
  printf 'python_resolved_path=%s\n' "$(readlink -f "$python_path")"
  python3 -I -S -VV 2>&1
  python3 -I -S -c 'import platform, sys; print(f"python_executable={sys.executable}"); print(f"python_prefix={sys.prefix}"); print(f"python_platform={platform.platform()}")'
} > "$output_directory/toolchain.txt"
"$taskset_path" --cpu-list "$cpu_list" rustc -C target-cpu=native --print cfg \
  | LC_ALL=C sort > "$output_directory/rustc-native-cfg.txt"
"$taskset_path" --cpu-list "$cpu_list" rustc -C target-cpu=native --print target-features \
  > "$output_directory/rustc-native-target-features.txt"

if ! command -v rg > /dev/null 2>&1; then
  fail 'rg is required to record symbol references'
fi
# Cargo merges ancestor .cargo configs that the source archive cannot record.
config_scan_directory=$repository_root
while :; do
  for cargo_config in "$config_scan_directory/.cargo/config.toml" "$config_scan_directory/.cargo/config"; do
    if [[ -e $cargo_config ]]; then
      fail "unrecorded Cargo config would alter builds: $cargo_config"
    fi
  done
  if [[ $config_scan_directory == / ]]; then
    break
  fi
  config_scan_directory=$(dirname "$config_scan_directory")
done

"$git_path" diff --check > "$output_directory/gates/git-diff-check.log" 2>&1
cargo fmt --package queueing-service-design -- --check \
  > "$output_directory/gates/cargo-fmt.log" 2>&1
cargo test --locked --package queueing-service-design --lib --bins \
  > "$output_directory/gates/cargo-test-lib-bins.log" 2>&1
cargo test --locked --package queueing-service-design --doc \
  > "$output_directory/gates/cargo-test-doc.log" 2>&1
cargo clippy --locked --package queueing-service-design --all-targets -- -D warnings \
  > "$output_directory/gates/cargo-clippy.log" 2>&1
RUSTDOCFLAGS='-D warnings' cargo doc --locked --package queueing-service-design --no-deps \
  > "$output_directory/gates/cargo-doc.log" 2>&1
python3 -I -S -X "pycache_prefix=$cargo_scratch_directory/python-cache" -m py_compile \
  "$topic/experiment/run_processes.py" \
  "$topic/experiment/analyze.py" \
  "$topic/experiment/validate_receipts.py" \
  > "$output_directory/gates/python-py-compile.log" 2>&1
bash -n "$topic/experiment/run_host.sh" \
  > "$output_directory/gates/bash-syntax.log" 2>&1

export RUSTFLAGS='-C target-cpu=native -C codegen-units=1 -C embed-bitcode=yes -C lto=fat -C panic=abort'
{
  printf 'RUSTFLAGS=%q\n' "$RUSTFLAGS"
  printf 'CARGO_TARGET_DIR=%q\n' "$CARGO_TARGET_DIR"
  printf 'CARGO_HOME=%q\n' "$CARGO_HOME"
} > "$output_directory/build-environment.txt"
"$taskset_path" --cpu-list "$cpu_list" \
  cargo build --locked --release --package queueing-service-design --bin queue-probe \
  > "$output_directory/build.log" 2>&1
built_binary="$CARGO_TARGET_DIR/release/queue-probe"
retained_binary="$output_directory/artifacts/queue-probe"
cp --preserve=mode,timestamps -- "$built_binary" "$retained_binary"
cmp --silent "$built_binary" "$retained_binary"
(
  cd "$output_directory"
  sha256sum artifacts/queue-probe > binary.sha256
  sha256sum --check --quiet binary.sha256
)
{
  file "$retained_binary"
  readelf -h -d -Ws "$retained_binary"
  nm -C "$retained_binary"
} > "$output_directory/codegen/elf-symbols.txt"
objdump -drwC "$retained_binary" > "$output_directory/codegen/final-binary.txt"
objdump -d --disassemble=topic27_do_work "$retained_binary" \
  > "$output_directory/codegen/do-work.txt"
rg -n 'topic27_do_work' "$output_directory/codegen/final-binary.txt" \
  > "$output_directory/codegen/do-work-calls.txt"
gzip -n -9 "$output_directory/codegen/final-binary.txt"

python3 -I -S -X "pycache_prefix=$cargo_scratch_directory/python-cache" \
  "$topic/experiment/run_processes.py" \
  "$retained_binary" "$output_directory/processes" "$cpu_list" \
  > "$output_directory/process-driver.log"
python3 -I -S -X "pycache_prefix=$cargo_scratch_directory/python-cache" \
  "$topic/experiment/analyze.py" "$output_directory/processes" \
  > "$output_directory/processes/analysis.json"
python3 -I -S -X "pycache_prefix=$cargo_scratch_directory/python-cache" \
  "$topic/experiment/validate_receipts.py" "$output_directory/processes" \
  > "$output_directory/receipt-validation.txt"

{
  printf 'The generator follows absolute intended times and never waits for completion.\n'
  printf 'The bounded channel has four waiting slots plus one job in service.\n'
  printf 'Queue wait is admission attempt to service start, conditional on completion.\n'
  printf 'The main analysis unit is one complete four-process block contrast.\n'
  printf 'The result applies only to this source, binary, host, CPU set, workload, and run window.\n'
} > "$output_directory/measurement-boundary.txt"
