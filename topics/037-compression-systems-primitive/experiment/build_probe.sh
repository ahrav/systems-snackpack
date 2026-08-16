#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 OUTPUT_DIR" >&2
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    echo "Topic 37 C measurements require Linux" >&2
    exit 2
fi

output_dir=$(realpath -m -- "$1")
if [[ -e $output_dir ]]; then
    echo "output already exists: $output_dir" >&2
    exit 2
fi
script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
source_file="$script_dir/compression_probe.c"
lz4_library=$(ldconfig -p | awk '$1 ~ /^liblz4\.so\.1$/ { print $NF; exit }')
zstd_library=$(ldconfig -p | awk '$1 ~ /^libzstd\.so\.1$/ { print $NF; exit }')
if [[ -z $lz4_library || -z $zstd_library ]]; then
    echo "versioned LZ4 or zstd runtime library was not found" >&2
    exit 2
fi
lz4_library=$(realpath "$lz4_library")
zstd_library=$(realpath "$zstd_library")

mkdir -p "$output_dir"
binary="$output_dir/compression-probe"
flags=(-O3 -fno-omit-frame-pointer -std=gnu11 -Wall -Wextra -Wpedantic -Werror \
    -march=native -g)
{
    printf 'COMMAND=cc'
    printf ' %q' "${flags[@]}" "$source_file" -o "$binary" "$zstd_library" "$lz4_library"
    printf '\n'
    cc "${flags[@]}" "$source_file" -o "$binary" "$zstd_library" "$lz4_library"
} >"$output_dir/build.log" 2>&1
"$binary" verify >"$output_dir/verify.log" 2>&1
cc --version >"$output_dir/compiler.txt" 2>&1
ldd "$binary" >"$output_dir/dynamic-libraries.txt" 2>&1
sha256sum "$source_file" "$binary" "$lz4_library" "$zstd_library" \
    >"$output_dir/inputs-and-binary.sha256"
{
    echo "CHECK=PASS"
    echo "source=$source_file"
    echo "binary=$binary"
    echo "flags=${flags[*]}"
    echo "lz4_library=$lz4_library"
    echo "zstd_library=$zstd_library"
} >"$output_dir/build.status"
(
    cd "$output_dir"
    find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 |
        LC_ALL=C sort -z | xargs -0 sha256sum
) >"$output_dir/SHA256SUMS"
echo "CHECK=PASS binary=$binary"
