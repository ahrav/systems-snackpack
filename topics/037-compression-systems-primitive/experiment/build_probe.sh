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

# ldconfig lists every ABI variant of a soname, so on a multi-arch host the
# first record for liblz4.so.1 can be a 32-bit library that this build cannot
# link. The architecture tag in that listing is spelled differently per
# platform, so ask the compiler instead: linking the candidate into an empty
# shared object succeeds only when its ABI matches the one cc emits here.
find_runtime_library() {
    local soname=$1 candidate
    while read -r candidate; do
        [[ -e $candidate ]] || continue
        if cc -shared -o /dev/null -x c /dev/null -x none "$candidate" \
            >/dev/null 2>&1; then
            realpath -- "$candidate"
            return 0
        fi
    done < <(ldconfig -p | awk -v soname="$soname" '$1 == soname { print $NF }')
    return 1
}

lz4_library=$(find_runtime_library liblz4.so.1) || {
    echo "no liblz4.so.1 that cc can link for this target" >&2
    exit 2
}
zstd_library=$(find_runtime_library libzstd.so.1) || {
    echo "no libzstd.so.1 that cc can link for this target" >&2
    exit 2
}

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
