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
    grep -q "<$symbol>" "$output_dir/${symbol}.asm"
done

architecture=$(uname -m)
barrier_asm="$output_dir/topic43_barrier_lookup.asm"

first_line() {
    local pattern=$1
    local file=$2
    local match
    match=$(grep -Enm1 -- "$pattern" "$file") || {
        printf 'missing ordered instruction pattern %s in %s\n' "$pattern" "$file" >&2
        exit 1
    }
    printf '%s\n' "${match%%:*}"
}

first_line_after() {
    local minimum=$1
    local pattern=$2
    local file=$3
    local line
    line=$(awk -v minimum="$minimum" -v pattern="$pattern" \
        'NR > minimum && $0 ~ pattern { print NR; exit }' "$file")
    if [[ -z $line ]]; then
        printf 'missing ordered instruction pattern %s after line %s in %s\n' \
            "$pattern" "$minimum" "$file" >&2
        exit 1
    fi
    printf '%s\n' "$line"
}

case $architecture in
    x86_64)
        grep -Eq '[[:space:]]cmp[qwl]?[[:space:]]' "$output_dir/topic43_mask_lookup.asm"
        grep -Eq '[[:space:]]sbb[qwl]?[[:space:]]' "$output_dir/topic43_mask_lookup.asm"
        compare_line=$(first_line '[[:space:]]cmp[qwl]?[[:space:]]' "$barrier_asm")
        branch_line=$(first_line_after "$compare_line" \
            '[[:space:]]j(a|ae|b|be|e|ne|z|nz)[[:space:]]' "$barrier_asm")
        barrier_line=$(first_line_after "$branch_line" '[[:space:]]lfence([[:space:]]|$)' "$barrier_asm")
        load_line=$(first_line_after "$barrier_line" \
            '[[:space:]]mov[qwl]?[[:space:]]+[^[:space:]]*\([^)]*\),' "$barrier_asm")
        barrier_order='cmp<conditional-branch<lfence<load'
        ;;
    aarch64 | arm64)
        grep -Eq '[[:space:]]cmp[[:space:]]' "$output_dir/topic43_mask_lookup.asm"
        grep -Eq '[[:space:]](sbc|ngc)[[:space:]]' "$output_dir/topic43_mask_lookup.asm"
        grep -Eq '[[:space:]](csdb|hint[[:space:]]+#0x14)([[:space:]]|$)' \
            "$output_dir/topic43_mask_lookup.asm"
        compare_line=$(first_line '[[:space:]]cmp[[:space:]]' "$barrier_asm")
        branch_line=$(first_line_after "$compare_line" '[[:space:]]b\.[a-z]+[[:space:]]' "$barrier_asm")
        dsb_line=$(first_line_after "$branch_line" '[[:space:]]dsb[[:space:]]+nsh' "$barrier_asm")
        barrier_line=$(first_line_after "$dsb_line" '[[:space:]]isb([[:space:]]|$)' "$barrier_asm")
        load_line=$(first_line_after "$barrier_line" '[[:space:]]ldr[[:space:]]' "$barrier_asm")
        barrier_order='cmp<conditional-branch<dsb-nsh<isb<load'
        ;;
    *)
        printf 'unsupported Linux architecture for Topic 43: %s\n' "$architecture" >&2
        exit 1
        ;;
esac

printf 'status=pass\narchitecture=%s\nobjdump=%s\nnm=%s\nbarrier_order=%s\n' \
    "$architecture" "$objdump_tool" "$nm_tool" "$barrier_order" \
    >"$output_dir/codegen-check.txt"
