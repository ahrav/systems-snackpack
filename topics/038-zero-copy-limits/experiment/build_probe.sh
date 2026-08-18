#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 OUTPUT_DIR" >&2
    exit 2
fi

output_dir=$1
if [[ -e $output_dir ]]; then
    echo "output already exists: $output_dir" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
compiler=${CC:-cc}
common_flags=(-O3 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer)

mkdir -p "$output_dir"
"$compiler" "${common_flags[@]}" \
    "$script_dir/transfer_bench.c" -o "$output_dir/transfer-probe"
"$compiler" "${common_flags[@]}" -march=native \
    "$script_dir/transfer_bench.c" -o "$output_dir/transfer-probe-native"
"$compiler" "${common_flags[@]}" -pthread \
    "$script_dir/msgzc_control.c" -o "$output_dir/msgzc-control"
"$compiler" "${common_flags[@]}" -march=native -pthread \
    "$script_dir/msgzc_control.c" -o "$output_dir/msgzc-control-native"

{
    printf 'compiler=%s\n' "$compiler"
    printf 'generic_flags=%s\n' "${common_flags[*]}"
    printf 'native_flags=%s -march=native\n' "${common_flags[*]}"
    sha256sum \
        "$script_dir/transfer_bench.c" \
        "$script_dir/msgzc_control.c" \
        "$output_dir/transfer-probe" \
        "$output_dir/transfer-probe-native" \
        "$output_dir/msgzc-control" \
        "$output_dir/msgzc-control-native"
} >"$output_dir/build-receipt.txt"
