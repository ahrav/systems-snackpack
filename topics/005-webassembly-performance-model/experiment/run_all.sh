#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="${WASM_TOPIC5_ROOT:-/tmp/systems-snackpack-topic-005}"
evidence_dir="${WASM_TOPIC5_EVIDENCE_DIR:-${root}/evidence}"
version=46.0.1

# The default root sits in shared /tmp; refuse symlinked or foreign-owned
# workspaces and keep the tree private so another account cannot swap
# contents between verification and use.
if [ -L "$root" ]; then
    echo "refusing symlinked workspace root: $root" >&2
    exit 1
fi
mkdir -p "$root"
chmod 0700 "$root"
if [ ! -O "$root" ]; then
    echo "workspace root is not owned by the current user: $root" >&2
    exit 1
fi
mkdir -p "$evidence_dir"
if [ ! -O "$evidence_dir" ]; then
    echo "evidence directory is not owned by the current user: $evidence_dir" >&2
    exit 1
fi
# Resolve overrides to absolute paths so relative values (for example
# WASM_TOPIC5_ROOT=work) survive the cd below.
root="$(cd -- "$root" && pwd)"
evidence_dir="$(cd -- "$evidence_dir" && pwd)"

case "$(uname -m)" in
    aarch64) archive_arch=aarch64 ;;
    x86_64) archive_arch=x86_64 ;;
    *) echo "unsupported host architecture: $(uname -m)" >&2; exit 1 ;;
esac

# CPU 0 is not guaranteed to be usable under cpusets or container
# affinity limits; default to the first CPU in this shell's affinity set
# and let WASM_TOPIC5_CPU override it.
affinity_list="$(taskset -pc $$ | sed 's/.*: //')"
default_cpu="${affinity_list%%[-,]*}"
cpu="${WASM_TOPIC5_CPU:-$default_cpu}"
case "$cpu" in
    ''|*[!0-9]*) echo "invalid benchmark CPU: '$cpu'" >&2; exit 1 ;;
esac

cli_url="https://github.com/bytecodealliance/wasmtime/releases/download/v${version}/wasmtime-v${version}-${archive_arch}-linux.tar.xz"
c_api_url="https://github.com/bytecodealliance/wasmtime/releases/download/v${version}/wasmtime-v${version}-${archive_arch}-linux-c-api.tar.xz"
build_command="gcc -O2 -std=c11 -Wall -Wextra -Werror -Iwasmtime-c-api/include wasm_boundary_bench.c -Lwasmtime-c-api/lib -Wl,-rpath,'\$ORIGIN/wasmtime-c-api/lib' -lwasmtime -ldl -lm -lpthread -o wasm_boundary_bench"
runner_command="./run_processes.py --bench ./wasm_boundary_bench --wat ./boundary.wat --iterations 10000000 --runs 12 --cpu ${cpu} --warmup-processes 2"

cd "$root"
cp "$source_dir/boundary.wat" "$root/boundary.wat"
cp "$source_dir/wasm_boundary_bench.c" "$root/wasm_boundary_bench.c"
cp "$source_dir/run_processes.py" "$root/run_processes.py"
python3 -m py_compile run_processes.py
eval "$build_command"

mkdir -p artifacts
./wasm_boundary_bench boundary.wat 1000 GH artifacts/boundary > artifacts/correctness.jsonl
./wasmtime/wasmtime objdump --addresses --bytes --traps \
    artifacts/boundary.cwasm > artifacts/disassembly.txt
eval "$runner_command" > raw-processes.jsonl

{
    printf 'manifest_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'hostname='; hostname -f 2>/dev/null || hostname
    printf 'uname_all='; uname -a
    printf 'uname_machine='; uname -m
    printf 'kernel_release='; uname -r
    printf 'nproc='; nproc
    printf 'affinity='; taskset -pc $$
    printf 'os_release='; . /etc/os-release; printf '%s %s\n' "$NAME" "$VERSION_ID"
    printf 'cpu_model='; LC_ALL=C lscpu | sed -n -e 's/^Model name:[[:space:]]*//p' -e 's/^Vendor ID:[[:space:]]*//p' | tr '\n' '|'; printf '\n'
    printf 'cpu_flags='; LC_ALL=C lscpu | sed -n -e 's/^Flags:[[:space:]]*//p'
    printf 'gcc_version='; gcc --version | sed -n '1p'
    printf 'python_version='; python3 --version
    printf 'rustc_begin\n'; rustc -vV 2>&1 || true; printf 'rustc_end\n'
    printf 'cargo_version='; cargo --version 2>&1 || true
    printf 'wasmtime_cli_version='; ./wasmtime/wasmtime --version
    printf 'wasmtime_cli_release_url=%s\n' "$cli_url"
    printf 'wasmtime_c_api_release_url=%s\n' "$c_api_url"
    printf 'wasmtime_c_api_embedded_version='; strings wasmtime-c-api/lib/libwasmtime.so | sed -n 's/^version: /version: /p' | head -n 1
    printf 'explicit_wasmtime_config=Cranelift; opt-level=speed; parallel-compilation=false; no target override; Config infers native host target/features\n'
    printf 'build_command=%s\n' "$build_command"
    printf 'runner_command=%s\n' "$runner_command"
    printf 'governor='; sed -n '1p' /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || printf 'unavailable\n'
    printf 'intel_no_turbo='; sed -n '1p' /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || printf 'unavailable\n'
    printf 'amd_boost='; sed -n '1p' /sys/devices/system/cpu/cpufreq/boost 2>/dev/null || printf 'unavailable\n'
    printf 'perf_version='; perf --version 2>&1 || true
    sha256sum wasmtime.tar.xz wasmtime-c-api.tar.xz \
        wasmtime-c-api/lib/libwasmtime.so wasmtime-c-api/include/wasmtime/conf.h \
        boundary.wat wasm_boundary_bench.c run_processes.py wasm_boundary_bench
    printf 'ldd_begin\n'; ldd ./wasm_boundary_bench; printf 'ldd_end\n'
    printf 'c_api_features_begin\n'; sed -n '/WASMTIME_FEATURE_LIST/,/marked/p' wasmtime-c-api/include/wasmtime/conf.h; printf 'c_api_features_end\n'
} > manifest.txt

{
    printf 'probe_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'hostname='; hostname -f 2>/dev/null || hostname
    printf 'dmi_product='; sed -n '1p' /sys/class/dmi/id/product_name 2>/dev/null || true
    printf 'dmi_vendor='; sed -n '1p' /sys/class/dmi/id/sys_vendor 2>/dev/null || true
    printf 'midr_el1='; sed -n '1p' /sys/devices/system/cpu/cpu0/regs/identification/midr_el1 2>/dev/null || true; printf '\n'
    printf 'lscpu_identity_begin\n'
    LC_ALL=C lscpu | sed -n -e '/^Architecture:/p' -e '/^Vendor ID:/p' -e '/^Model name:/p' \
        -e '/^CPU family:/p' -e '/^Model:/p' -e '/^Stepping:/p' \
        -e '/^Hypervisor vendor:/p' -e '/^Virtualization type:/p'
    printf 'lscpu_identity_end\n'
} > model-probe.txt

sha256sum manifest.txt model-probe.txt artifacts/correctness.jsonl \
    artifacts/boundary.wasm artifacts/boundary.cwasm \
    artifacts/disassembly.txt raw-processes.jsonl > evidence.sha256

cp manifest.txt model-probe.txt raw-processes.jsonl evidence.sha256 "$evidence_dir/"
rm -rf "$evidence_dir/artifacts"
cp -R artifacts "$evidence_dir/artifacts"
(cd "$evidence_dir" && sha256sum -c evidence.sha256)
