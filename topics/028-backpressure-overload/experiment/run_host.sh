#!/usr/bin/env bash
set -Eeuo pipefail

# BASH_ENV/ENV startup hooks and exported shell functions run before line 1
# and can mutate arguments or shadow commands; re-exec cannot undo them, so
# refuse instead.
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

repository_root=$(cd "$1" && pwd -P)
output_directory=$(realpath -m -- "$2")
host_label=$3
source_commit=$4
topic=topics/028-backpressure-overload
run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
scratch_directory=
failure_reason=
failure_line=
failure_command=
failure_exit_code=

fail() {
  failure_reason=$1
  printf '%s\n' "$failure_reason" >&2
  exit "${2:-2}"
}

capture_error() {
  failure_exit_code=$1
  failure_line=$2
  failure_command=$3
  failure_reason="command failed at line $failure_line"
  return "$failure_exit_code"
}

write_source_manifest() {
  local destination=$1
  (
    cd "$repository_root"
    "${git_path:-git}" ls-files -z | LC_ALL=C sort -z | xargs -0 "${sha256sum_path:-sha256sum}" --
  ) > "$destination"
}

cleanup_scratch() {
  if [[ -z ${scratch_directory:-} || ! -e $scratch_directory ]]; then
    return 0
  fi
  if [[ ! -f $scratch_directory/.topic28-scratch ]]; then
    printf 'refusing to remove unverified scratch directory: %s\n' "$scratch_directory" >&2
    return 1
  fi
  rm -rf -- "$scratch_directory"
}

seal_evidence() {
  (
    cd "$output_directory"
    find . -type f ! -path './evidence.sha256' -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 "${sha256sum_path:-sha256sum}" > evidence.sha256
    "${sha256sum_path:-sha256sum}" --check --quiet evidence.sha256
  )
}

finalize() {
  local status=$?
  local head_match=failed
  local clean_tree=failed
  local source_match=failed
  trap - EXIT ERR INT TERM
  set +e

  if [[ -d $output_directory ]]; then
    "${git_path:-git}" -C "$repository_root" rev-parse HEAD > "$output_directory/source-head.after.txt" 2>&1
    if [[ $(<"$output_directory/source-head.after.txt") == "$source_commit" ]]; then
      head_match=passed
    else
      status=1
    fi
    "${git_path:-git}" -C "$repository_root" status --porcelain=v1 --untracked-files=all \
      > "$output_directory/source-status.after.txt" 2>&1
    if [[ ! -s $output_directory/source-status.after.txt ]]; then
      clean_tree=passed
    else
      status=1
    fi
    if write_source_manifest "$output_directory/source-files.after.sha256" \
      && cmp -s "$output_directory/source-files.before.sha256" \
        "$output_directory/source-files.after.sha256"; then
      source_match=passed
    else
      status=1
    fi
  fi
  if ! cleanup_scratch; then
    status=1
  fi
  if (( status != 0 )) && [[ -z $failure_reason ]]; then
    failure_reason='run failed or exact-source finalization failed'
  fi
  if [[ -d $output_directory ]]; then
    {
      if (( status == 0 )); then printf 'status=success\n'; else printf 'status=failed\n'; fi
      printf 'exit_code=%s\n' "$status"
      printf 'run_started_utc=%s\n' "$run_started_utc"
      printf 'run_finished_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
      printf 'host_label=%q\n' "$host_label"
      printf 'source_commit=%q\n' "$source_commit"
      printf 'head_match=%s\n' "$head_match"
      printf 'clean_tree=%s\n' "$clean_tree"
      printf 'source_manifest_match=%s\n' "$source_match"
      printf 'failure_reason=%q\n' "$failure_reason"
      printf 'failure_exit_code=%q\n' "$failure_exit_code"
      printf 'failure_line=%q\n' "$failure_line"
      printf 'failure_command=%q\n' "$failure_command"
    } > "$output_directory/run.status"
    if ! seal_evidence; then
      status=1
      printf 'status=failed\nexit_code=1\nfailure_reason=evidence_seal_failed\n' \
        > "$output_directory/run.status"
      seal_evidence || true
    fi
  fi
  exit "$status"
}

if [[ $(uname -s) != Linux ]]; then
  fail 'the retained host protocol requires Linux'
fi
if [[ -z $host_label || $host_label == *$'\n'* ]]; then
  fail 'host label must be nonempty and single-line'
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
  fail 'source commit must be a full lowercase 40-hex Git object ID'
fi
if [[ -e $output_directory ]]; then
  fail "output directory already exists: $output_directory"
fi
if [[ $output_directory == "$repository_root" || $output_directory == "$repository_root"/* ]]; then
  fail 'output directory must be outside the repository'
fi
mkdir -p "$output_directory"/{artifacts,codegen,gates}

# Loader interposition and toolchain overrides are recorded and cleared
# before the first source receipt; a shim active during archive or checksum
# generation can forge the receipts the bundle vouches for.
environment_candidates=(
  AR ARFLAGS AS CC CFLAGS CPP CPPFLAGS CXX CXXFLAGS LD LDFLAGS LIBRARY_PATH
  CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH DYLD_LIBRARY_PATH GLIBC_TUNABLES
  LD_AUDIT LD_LIBRARY_PATH LD_PRELOAD
  MALLOC_ARENA_MAX MALLOC_ARENA_TEST MALLOC_CHECK_ MALLOC_MMAP_MAX_
  MALLOC_MMAP_THRESHOLD_ MALLOC_PERTURB_ MALLOC_TOP_PAD_ MALLOC_TRIM_THRESHOLD_
  LANG LANGUAGE LC_ALL LC_CTYPE MAKEFLAGS NM NUM_JOBS OBJCOPY OBJDUMP
  PKG_CONFIG PKG_CONFIG_PATH RANLIB SOURCE_DATE_EPOCH STRIP TZ ZERO_AR_DATE
  CARGO CARGO_BUILD_JOBS CARGO_BUILD_RUSTFLAGS CARGO_BUILD_TARGET
  CARGO_ENCODED_RUSTFLAGS CARGO_HOME CARGO_INCREMENTAL CARGO_MAKEFLAGS
  CARGO_NET_OFFLINE CARGO_TARGET_DIR RUSTC RUSTC_BOOTSTRAP RUSTC_LOG
  RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER RUSTDOC RUSTDOCFLAGS RUSTFLAGS
  RUSTUP_HOME RUSTUP_TOOLCHAIN PYTHONHASHSEED PYTHONHOME PYTHONINSPECT
  PYTHONIOENCODING PYTHONMALLOC PYTHONOPTIMIZE PYTHONPATH PYTHONPYCACHEPREFIX
  PYTHONSAFEPATH PYTHONSTARTUP PYTHONUTF8 PYTHONWARNINGS VIRTUAL_ENV
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

# GIT_* variables (GIT_DIR, GIT_WORK_TREE, object/index/graft/replace
# redirection) can repoint every identity check below at a different tree, and
# a PATH wrapper can misreport source identity. This block records Git's PATH
# resolution, clears GIT_* variables, and disables replace refs before the
# repository identity checks.
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
export GIT_NO_REPLACE_OBJECTS=1

# A PATH wrapper can hash bytes different from the retained files.
sha256sum_path=$(command -v sha256sum)
sha256sum_path=$(readlink -f "$sha256sum_path")
printf 'sha256sum_path=%s\nsha256sum_resolved_path=%s\n' \
  "$(command -v sha256sum)" "$sha256sum_path" \
  > "$output_directory/checksum-provenance.txt"
"$sha256sum_path" --version | sed -n 1p >> "$output_directory/checksum-provenance.txt"

# A repository subdirectory would scope git ls-files and the output-directory
# guard to a prefix, leaving the exact-source evidence incomplete.
repository_toplevel=$("$git_path" -C "$repository_root" rev-parse --show-toplevel)
repository_toplevel=$(cd "$repository_toplevel" && pwd -P)
if [[ $repository_toplevel != "$repository_root" ]]; then
  fail 'repository root must be the top-level checkout'
fi

trap 'capture_error "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap 'failure_reason="received SIGINT"; exit 130' INT
trap 'failure_reason="received SIGTERM"; exit 143' TERM
trap finalize EXIT

cd "$repository_root"
"$git_path" rev-parse HEAD > "$output_directory/source-head.before.txt"
if [[ $(<"$output_directory/source-head.before.txt") != "$source_commit" ]]; then
  fail 'HEAD does not equal the requested source commit'
fi
"$git_path" status --porcelain=v1 --untracked-files=all > "$output_directory/source-status.before.txt"
if [[ -s $output_directory/source-status.before.txt ]]; then
  fail 'exact-source measurement requires a clean worktree'
fi
# git status misses files flagged assume-unchanged or skip-worktree, which
# would let hidden local edits pass the clean-tree gate.
if "$git_path" ls-files -v | grep -Eq '^(S|[a-z]) '; then
  fail 'exact-source measurement refuses assume-unchanged or skip-worktree files'
fi
# git status reports a clean tree even when gitignored files exist, but the
# build can consume such a file during compilation.
"$git_path" ls-files --others --ignored --exclude-standard -- "$topic" \
  > "$output_directory/source-ignored.before.txt"
if [[ -s $output_directory/source-ignored.before.txt ]]; then
  fail 'exact-source measurement refuses gitignored files under the topic directory'
fi
write_source_manifest "$output_directory/source-files.before.sha256"
"$git_path" ls-tree -r --full-tree "$source_commit" > "$output_directory/source-tree.txt"
(
  cd "$output_directory"
  "$sha256sum_path" source-tree.txt > source-tree.sha256
)
"$git_path" archive --format=tar "$source_commit" | gzip -n -9 > "$output_directory/source.tar.gz"
(
  cd "$output_directory"
  "$sha256sum_path" source.tar.gz > source-archive.sha256
  "$sha256sum_path" --check --quiet source-tree.sha256 source-archive.sha256
)

scratch_parent=${TMPDIR:-/tmp}
scratch_directory=$(mktemp -d "$scratch_parent/topic28-overload.XXXXXXXX")
scratch_directory=$(cd "$scratch_directory" && pwd -P)
if [[ $scratch_directory == "$repository_root" || $scratch_directory == "$repository_root"/* \
  || $scratch_directory == "$output_directory" || $scratch_directory == "$output_directory"/* ]]; then
  fail 'scratch directory overlaps source or evidence'
fi
touch "$scratch_directory/.topic28-scratch"
mkdir -p "$scratch_directory"/{cargo-home,target,python-cache}

export CARGO_HOME="$scratch_directory/cargo-home"
export CARGO_INCREMENTAL=0
export CARGO_NET_OFFLINE=true
export CARGO_TARGET_DIR="$scratch_directory/target"
export LC_ALL=C
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$scratch_directory/python-cache"
export TZ=UTC
unset RUSTFLAGS RUSTDOCFLAGS CARGO_BUILD_RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
{
  printf 'CARGO_HOME=%q\n' "$CARGO_HOME"
  printf 'CARGO_INCREMENTAL=%q\n' "$CARGO_INCREMENTAL"
  printf 'CARGO_NET_OFFLINE=%q\n' "$CARGO_NET_OFFLINE"
  printf 'CARGO_TARGET_DIR=%q\n' "$CARGO_TARGET_DIR"
  printf 'LC_ALL=%q\n' "$LC_ALL"
  printf 'PYTHONPYCACHEPREFIX=%q\n' "$PYTHONPYCACHEPREFIX"
  printf 'TZ=%q\n' "$TZ"
} > "$output_directory/environment.effective.txt"

allowed_list=$(awk '/^Cpus_allowed_list:/ {print $2}' /proc/self/status)
if [[ -z $allowed_list ]]; then
  fail 'could not read Cpus_allowed_list from procfs'
fi
# The retained-host protocol records a pinned four-CPU boundary; an unpinned
# run would seal evidence that misstates the calibration and treatment CPUs.
if ! command -v taskset > /dev/null 2>&1; then
  fail 'the retained host protocol requires taskset to pin the CPU set'
fi
taskset_path=$(command -v taskset)
taskset_path=$(readlink -f "$taskset_path")
selected_cpus=()
IFS=',' read -r -a cpu_parts <<< "$allowed_list"
for part in "${cpu_parts[@]}"; do
  if [[ $part =~ ^([0-9]+)-([0-9]+)$ ]]; then
    first=${BASH_REMATCH[1]}
    last=${BASH_REMATCH[2]}
    for ((cpu=first; cpu<=last; cpu++)); do
      selected_cpus+=("$cpu")
      if (( ${#selected_cpus[@]} == 4 )); then break 2; fi
    done
  elif [[ $part =~ ^[0-9]+$ ]]; then
    selected_cpus+=("$part")
    if (( ${#selected_cpus[@]} == 4 )); then break; fi
  else
    fail "invalid CPU affinity component: $part"
  fi
done
if (( ${#selected_cpus[@]} != 4 )); then
  fail 'fewer than four allowed CPUs were found for the pinned run'
fi
cpu_list=$(IFS=,; printf '%s' "${selected_cpus[*]}")
affinity_mode=taskset-four-cpus
clocksource_file=/sys/devices/system/clocksource/clocksource0/current_clocksource
if [[ ! -r $clocksource_file ]]; then
  fail "current clocksource is not readable: $clocksource_file"
fi
current_clocksource=$(<"$clocksource_file")

{
  printf 'host_label=%s\n' "$host_label"
  printf 'resolved_hostname=%s\n' "$(hostname -f)"
  printf 'run_started_utc=%s\n' "$run_started_utc"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'uname=%s\n' "$(uname -a)"
  printf 'architecture=%s\n' "$(uname -m)"
  printf 'kernel_release=%s\n' "$(uname -r)"
  printf 'kernel_version=%s\n' "$(uname -v)"
  printf 'configured_cpu_count=%s\n' "$(nproc --all)"
  printf 'available_cpu_count=%s\n' "$(nproc)"
  printf 'allowed_cpu_list=%s\n' "$allowed_list"
  printf 'selected_cpu_list=%s\n' "$cpu_list"
  printf 'affinity_mode=%s\n' "$affinity_mode"
  printf 'current_clocksource=%s\n' "$current_clocksource"
  if [[ -r /sys/devices/system/clocksource/clocksource0/available_clocksource ]]; then
    printf 'available_clocksources=%s\n' \
      "$(</sys/devices/system/clocksource/clocksource0/available_clocksource)"
  fi
  awk '/^Cpus_allowed(_list)?:/ {print}' /proc/self/status
  if command -v taskset > /dev/null 2>&1; then "$taskset_path" -pc "$$"; fi
  lscpu
  awk -F: '/^(vendor_id|model name|cpu family|model|stepping|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision)/ { if (!seen[$1]++) print }' /proc/cpuinfo
} > "$output_directory/host.txt"
# A PATH wrapper around the build or analysis tools could substitute a
# different binary while the source receipts stay internally consistent, so
# pin the absolute PATH resolutions and record their symlink targets. The
# rustup proxies dispatch on argv[0], so cargo/rustc keep their proxy names
# rather than being collapsed through readlink.
rustc_path=$(command -v rustc)
cargo_path=$(command -v cargo)
python3_path=$(command -v python3)
{
  printf 'rustc_path=%s\n' "$rustc_path"
  printf 'rustc_resolved_path=%s\n' "$(readlink -f "$rustc_path")"
  "$rustc_path" -vV
  printf 'cargo_path=%s\n' "$cargo_path"
  printf 'cargo_resolved_path=%s\n' "$(readlink -f "$cargo_path")"
  "$cargo_path" -Vv
  printf 'python_path=%s\n' "$python3_path"
  printf 'python_resolved_path=%s\n' "$(readlink -f "$python3_path")"
  printf 'taskset_path=%s\n' "$(command -v taskset)"
  printf 'taskset_resolved_path=%s\n' "$taskset_path"
  "$taskset_path" --version
  "$python3_path" -I -S -VV 2>&1
  if command -v cc > /dev/null 2>&1; then cc --version 2>&1; fi
  if command -v ld > /dev/null 2>&1; then ld --version 2>&1 | sed -n '1,4p'; fi
  if command -v nm > /dev/null 2>&1; then nm --version 2>&1 | sed -n '1,4p'; fi
  if command -v objdump > /dev/null 2>&1; then objdump --version 2>&1 | sed -n '1,4p'; fi
} > "$output_directory/toolchain.txt"
"$rustc_path" -C target-cpu=native --print cfg | LC_ALL=C sort \
  > "$output_directory/rustc-native-cfg.txt"
"$rustc_path" -C target-cpu=native --print target-features \
  > "$output_directory/rustc-native-target-features.txt"

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
"$cargo_path" fmt --all -- --check \
  > "$output_directory/gates/cargo-fmt.log" 2>&1
"$cargo_path" test --locked --workspace --lib --examples \
  > "$output_directory/gates/cargo-test-workspace-lib-examples.log" 2>&1
"$cargo_path" test --locked --package backpressure-overload --bin overload-probe \
  > "$output_directory/gates/cargo-test-probe.log" 2>&1
"$cargo_path" test --locked --workspace --doc \
  > "$output_directory/gates/cargo-test-workspace-doc.log" 2>&1
"$cargo_path" clippy --locked --workspace --all-targets -- -D warnings \
  > "$output_directory/gates/cargo-clippy.log" 2>&1
RUSTDOCFLAGS='-D warnings' "$cargo_path" doc --locked --workspace --no-deps \
  > "$output_directory/gates/cargo-doc.log" 2>&1
"$cargo_path" bench --locked --workspace --no-run \
  > "$output_directory/gates/cargo-bench-no-run.log" 2>&1
"$python3_path" -I -S -X "pycache_prefix=$scratch_directory/python-cache" -m py_compile \
  "$topic/experiment/run_processes.py" \
  "$topic/experiment/analyze.py" \
  "$topic/experiment/validate_receipts.py" \
  > "$output_directory/gates/python-py-compile.log" 2>&1
bash -n "$topic/experiment/run_host.sh" \
  > "$output_directory/gates/bash-syntax.log" 2>&1

export RUSTFLAGS='-C target-cpu=native -C codegen-units=1 -C embed-bitcode=yes -C lto=fat -C panic=abort'
printf 'RUSTFLAGS=%q\n' "$RUSTFLAGS" > "$output_directory/build-environment.txt"
"$cargo_path" build --locked --release --package backpressure-overload --bin overload-probe \
  > "$output_directory/build.log" 2>&1
built_binary="$CARGO_TARGET_DIR/release/overload-probe"
retained_binary="$output_directory/artifacts/overload-probe"
cp --preserve=mode,timestamps -- "$built_binary" "$retained_binary"
cmp --silent "$built_binary" "$retained_binary"
(
  cd "$output_directory"
  "$sha256sum_path" artifacts/overload-probe > binary.sha256
  "$sha256sum_path" --check --quiet binary.sha256
)
{
  file "$retained_binary"
  if command -v readelf > /dev/null 2>&1; then readelf -h -d -Ws "$retained_binary"; fi
  nm -C "$retained_binary"
} > "$output_directory/codegen/final-symbols.txt"
objdump -drwC "$retained_binary" > "$output_directory/codegen/final-binary.txt"
objdump -d --disassemble=topic28_origin_work "$retained_binary" \
  > "$output_directory/codegen/origin-work-loop.txt"
grep -n 'topic28_origin_work' "$output_directory/codegen/final-symbols.txt" \
  > "$output_directory/codegen/origin-work-symbol.txt"
grep -nE '(call|bl).*topic28_origin_work' "$output_directory/codegen/final-binary.txt" \
  > "$output_directory/codegen/origin-work-callsites.txt"
test -s "$output_directory/codegen/origin-work-loop.txt"
test -s "$output_directory/codegen/origin-work-symbol.txt"
test -s "$output_directory/codegen/origin-work-callsites.txt"
gzip -n -9 "$output_directory/codegen/final-binary.txt"

"$taskset_path" --cpu-list "$cpu_list" "$retained_binary" --self-check \
  > "$output_directory/gates/self-check.log" 2>&1
"$python3_path" -I -S -X "pycache_prefix=$scratch_directory/python-cache" \
  "$topic/experiment/run_processes.py" \
  --taskset "$taskset_path" \
  "$retained_binary" "$output_directory/processes" "$cpu_list" \
  > "$output_directory/process-driver.log" 2>&1
"$python3_path" -I -S -X "pycache_prefix=$scratch_directory/python-cache" \
  "$topic/experiment/analyze.py" "$output_directory/processes" \
  > "$output_directory/processes/analysis.json"
"$python3_path" -I -S -X "pycache_prefix=$scratch_directory/python-cache" \
  "$topic/experiment/validate_receipts.py" "$output_directory/processes" \
  > "$output_directory/receipt-validation.txt"
(
  cd "$output_directory/processes"
  "$sha256sum_path" --check --quiet settings.sha256
)
{
  printf 'Measured: release-through-all-settled-rendezvous burst_ns, including end-barrier release overhead, for this retained host, source, binary, settings, CPU set, and run window.\n'
  printf 'Observed: exact logical and physical counts, capacity maxima, final-image symbol, loop, and call sites.\n'
  printf 'Inferred: count reduction follows one-key coalescing plus one aggregate retry budget.\n'
  printf 'Not established: production DNS, network, resolver, TTL, backoff, recovery, or multi-key behavior.\n'
  printf 'Requests and attempts are dependent receipts; complete four-process blocks are analysis units.\n'
} > "$output_directory/measurement-boundary.txt"
