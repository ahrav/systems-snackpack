#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 SOURCE-ARCHIVE SOURCE-COMMIT OUTPUT-DIRECTORY" >&2
    exit 2
fi

source_archive=$(realpath "$1")
source_commit=$2
output_directory=$(realpath -m "$3")
scratch_directory=$(mktemp -d)
trap 'rm -rf -- "$scratch_directory"' EXIT

if [[ -e "$output_directory" ]]; then
    echo "output already exists; choose a new directory to retain prior attempts: $output_directory" >&2
    exit 2
fi
mkdir -p "$output_directory"
cp "$source_archive" "$output_directory/source-archive.tar.gz"
printf '%s\n' "$source_commit" > "$output_directory/source-commit.txt"
(
    cd "$output_directory"
    sha256sum source-archive.tar.gz > source-archive.sha256
)

mkdir -p "$scratch_directory/source"
tar -xzf "$source_archive" --strip-components=1 -C "$scratch_directory/source"
topic_directory="$scratch_directory/source/topics/048-hardware-software-prefetching"
experiment_directory="$topic_directory/experiment"
binary="$output_directory/prefetch_bench"

{
    printf 'recorded_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'hostname=%s\n' "$(hostname -f 2>/dev/null || hostname)"
    printf 'uname_machine=%s\n' "$(uname -m)"
    printf 'available_cpus=%s\n' "$(nproc)"
    printf 'line_size=%s\n' "$(getconf LEVEL1_DCACHE_LINESIZE 2>/dev/null || true)"
    uname -a
    lscpu
    gcc --version
    rustc -vV
    gcc -Q -O3 -march=native --help=target
} > "$output_directory/host.txt" 2>&1

build_flags=(
    -O3 -g -std=c11 -Wall -Wextra -Werror -march=native
    -fno-tree-vectorize -fno-tree-slp-vectorize
)
{
    printf 'gcc'
    printf ' %q' "${build_flags[@]}"
    printf ' %q -o %q\n' "$experiment_directory/prefetch_bench.c" "$binary"
    gcc "${build_flags[@]}" "$experiment_directory/prefetch_bench.c" -o "$binary"
} > "$output_directory/build.txt" 2>&1

(
    cd "$output_directory"
    sha256sum prefetch_bench > binary.sha256
)
(
    cd "$experiment_directory"
    sha256sum \
        prefetch_bench.c run_campaign.py analyze.py validate_receipts.py \
        > "$output_directory/experiment-sources.sha256"
)

mkdir -p "$output_directory/smoke" "$output_directory/codegen"
taskset -c 0 "$binary" --mode demand --pattern random --distance 0 \
    --mib 8 --passes 1 --warmup-passes 1 --seed 48000048 \
    > "$output_directory/smoke/demand.json" \
    2> "$output_directory/smoke/demand.stderr"
taskset -c 0 "$binary" --mode prefetch --pattern random --distance 16 \
    --mib 8 --passes 1 --warmup-passes 1 --seed 48000048 \
    > "$output_directory/smoke/prefetch.json" \
    2> "$output_directory/smoke/prefetch.stderr"

nm -n "$binary" > "$output_directory/codegen/symbols.txt"
objdump -drwC --disassemble=kernel_demand "$binary" \
    > "$output_directory/codegen/kernel_demand.asm"
objdump -drwC --disassemble=kernel_prefetch "$binary" \
    > "$output_directory/codegen/kernel_prefetch.asm"

python3 "$experiment_directory/run_campaign.py" \
    --binary "$binary" --output "$output_directory/random.tsv" \
    --pattern random --distances 4,8,16,32,64 --blocks 4 --aa-blocks 2 \
    --mib 256 --passes 2 --warmup-passes 1 --cpu 0 \
    --campaign-seed 480048 --workload-seed 48000048 \
    > "$output_directory/random-run.log" 2>&1
python3 "$experiment_directory/analyze.py" "$output_directory/random.tsv" \
    > "$output_directory/random-analysis.json"

python3 "$experiment_directory/run_campaign.py" \
    --binary "$binary" --output "$output_directory/sequential.tsv" \
    --pattern sequential --distances 16 --blocks 2 --aa-blocks 2 \
    --mib 256 --passes 2 --warmup-passes 1 --cpu 0 \
    --campaign-seed 480049 --workload-seed 48000048 \
    > "$output_directory/sequential-run.log" 2>&1
python3 "$experiment_directory/analyze.py" "$output_directory/sequential.tsv" \
    > "$output_directory/sequential-analysis.json"

(
    cd "$output_directory"
    sha256sum \
        source-archive.tar.gz source-commit.txt source-archive.sha256 host.txt \
        build.txt prefetch_bench binary.sha256 experiment-sources.sha256 \
        smoke/demand.json smoke/demand.stderr smoke/prefetch.json \
        smoke/prefetch.stderr codegen/symbols.txt codegen/kernel_demand.asm \
        codegen/kernel_prefetch.asm random.tsv random-run.log \
        random-analysis.json sequential.tsv sequential-run.log \
        sequential-analysis.json > SHA256SUMS
)

python3 "$experiment_directory/validate_receipts.py" "$output_directory" \
    --expected-source-commit "$source_commit" \
    > "$output_directory/validation.json"
