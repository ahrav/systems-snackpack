#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    printf 'usage: %s BINARY OUTPUT_DIR\n' "$0" >&2
    exit 2
fi

binary=$(realpath -- "$1")
output_dir=$2
if [[ ! -x $binary || -e $output_dir ]]; then
    printf 'binary must exist and output directory must not exist\n' >&2
    exit 2
fi
mkdir -p -- "$output_dir"

objdump_tool=$(command -v objdump)
nm_tool=$(command -v nm)
"$nm_tool" -n -- "$binary" >"$output_dir/symbols.txt"

for symbol in topic43_plain_lookup topic43_mask_lookup topic43_barrier_lookup topic43_speculation_barrier; do
    "$objdump_tool" -d --no-show-raw-insn --disassemble="$symbol" -- "$binary" \
        >"$output_dir/${symbol}.asm"
done

architecture=$(uname -m)
script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)

# The instruction checks live in codegen_checks.py so offline receipt
# validation re-runs exactly the same gate over the retained assembly.
barrier_order=$(python3 "$script_dir/codegen_checks.py" \
    --codegen-dir "$output_dir" --architecture "$architecture")

printf 'status=pass\narchitecture=%s\nobjdump=%s\nnm=%s\nbarrier_order=%s\n' \
    "$architecture" "$objdump_tool" "$nm_tool" "$barrier_order" \
    >"$output_dir/codegen-check.txt"
