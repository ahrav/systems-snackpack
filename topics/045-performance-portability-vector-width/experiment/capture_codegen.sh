#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf 'usage: %s BINARY OUTPUT_DIR\n' "$0" >&2
    exit 2
fi

binary=$(realpath -- "$1")
output_dir=$(realpath -m -- "$2")
if [[ ! -x $binary || -e $output_dir ]]; then
    printf 'binary must exist and output directory must not exist\n' >&2
    exit 2
fi
mkdir -p -- "$output_dir"

objdump_tool=$(command -v objdump)
nm_tool=$(command -v nm)
"$nm_tool" -an -- "$binary" >"$output_dir/symbols.txt"
"$objdump_tool" -drwC --no-show-raw-insn -- "$binary" >"$output_dir/all.asm"

architecture=$(uname -m)
symbols=(kernel_scalar kernel_v128)
if [[ $architecture == x86_64 ]]; then
    symbols+=(kernel_v256 kernel_v512)
fi
for symbol in "${symbols[@]}"; do
    "$objdump_tool" -d --no-show-raw-insn --disassemble="$symbol" -- "$binary" \
        >"$output_dir/${symbol}.asm"
done

script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
python3 -I -B "$script_dir/codegen_checks.py" \
    --codegen-dir "$output_dir" --architecture "$architecture" \
    >"$output_dir/codegen-check.json"

(
    cd -- "$output_dir"
    sha256sum -- all.asm kernel_*.asm symbols.txt
) >"$output_dir/sha256sums.txt"
