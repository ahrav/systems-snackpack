#!/usr/bin/env bash
set -euo pipefail

if (( $# != 2 )); then
  echo "usage: probe_remote.sh HOST_ALIAS CPU" >&2
  exit 2
fi

host_alias=$1
cpu=$2
if [[ -z $host_alias || $host_alias =~ [[:cntrl:]] ]]; then
  echo "HOST_ALIAS must be nonempty and contain no control characters" >&2
  exit 2
fi
if [[ ! $cpu =~ ^[0-9]+$ ]]; then
  echo "CPU must be a nonnegative integer" >&2
  exit 2
fi
for tool in cargo date getconf hostname lscpu python3 rg rustc sed taskset uname; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "required probe tool is unavailable: $tool" >&2
    exit 2
  fi
done
if [[ ! -r /proc/cpuinfo ]]; then
  echo "/proc/cpuinfo is unreadable" >&2
  exit 2
fi
if ! taskset --cpu-list "$cpu" true; then
  echo "CPU $cpu is unavailable to the current affinity mask" >&2
  exit 2
fi

printf 'host_alias=%s\n' "$host_alias"
printf 'resolved_hostname=%s\n' "$(hostname -f)"
printf 'utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
printf 'uname='
uname -a
printf 'architecture='
uname -m
printf 'online_cpus='
getconf _NPROCESSORS_ONLN
printf 'configured_cpus='
getconf _NPROCESSORS_CONF
printf 'affinity='
taskset --cpu-list --pid "$$"
printf '\nlscpu\n'
lscpu
printf '\ncpu_model_and_feature_fields\n'
rg -m 128 \
  '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
  /proc/cpuinfo
printf '\nrustc_verbose\n'
rustc -vV
printf '\ncargo_version\n'
cargo -V
printf '\npython_version\n'
python3 --version
printf '\nc_and_cxx_compilers\n'
for compiler in cc gcc clang; do
  if command -v "$compiler" >/dev/null 2>&1; then
    printf '%s_path=%s\n' "$compiler" "$(command -v "$compiler")"
    "$compiler" --version | sed -n '1,4p'
    if "$compiler" -dumpmachine >/dev/null 2>&1; then
      printf '%s_target=%s\n' "$compiler" "$("$compiler" -dumpmachine)"
    fi
  else
    printf '%s=unavailable\n' "$compiler"
  fi
done
printf '\nbinutils\n'
for tool in as ld nm objdump readelf; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '%s_path=%s\n' "$tool" "$(command -v "$tool")"
    "$tool" --version | sed -n '1,2p'
  else
    printf '%s=unavailable\n' "$tool"
  fi
done
