#!/usr/bin/env python3
"""Ordered-instruction checks over the retained Topic 43 disassembly.

Single source of truth for the codegen gate: ``capture_codegen.sh`` runs it
right after disassembly and ``validate_receipts.py`` re-runs it over retained
receipts, so a ``status=pass`` marker can never certify assembly the checks
themselves would reject.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SYMBOLS = (
    "topic43_plain_lookup",
    "topic43_mask_lookup",
    "topic43_barrier_lookup",
    "topic43_speculation_barrier",
)


class CodegenError(ValueError):
    """A retained disassembly fails the fixed instruction checks."""


def first_match(
    pattern: str, lines: list[str], minimum: int, file: str
) -> tuple[int, re.Match[str]]:
    """Return the first matching line and match strictly after ``minimum``."""

    for number, line in enumerate(lines, 1):
        match = re.search(pattern, line)
        if number > minimum and match:
            return number, match
    raise CodegenError(
        f"missing ordered instruction pattern {pattern!r} after line {minimum} in {file}"
    )


def first_line(pattern: str, lines: list[str], minimum: int, file: str) -> int:
    """Return the 1-based number of the first match strictly after ``minimum``."""

    return first_match(pattern, lines, minimum, file)[0]


def check_codegen_dir(codegen_dir: Path, architecture: str) -> str:
    """Validate the retained assembly for ``architecture``; return the barrier order."""

    for symbol in SYMBOLS:
        asm = codegen_dir / f"{symbol}.asm"
        if f"<{symbol}>" not in asm.read_text(encoding="utf-8"):
            raise CodegenError(f"{asm.name} does not disassemble {symbol}")
    mask_file = "topic43_mask_lookup.asm"
    mask_lines = (codegen_dir / mask_file).read_text(encoding="utf-8").splitlines()
    barrier_file = "topic43_barrier_lookup.asm"
    barrier_lines = (codegen_dir / barrier_file).read_text(encoding="utf-8").splitlines()
    if architecture == "x86_64":
        compare, compare_match = first_match(
            r"[ \t]cmp[qwl]?[ \t]+%[a-z0-9]+,[ \t]*(%[a-z0-9]+)(?:[ \t]|$)",
            mask_lines,
            0,
            mask_file,
        )
        index = re.escape(compare_match.group(1))
        mask, mask_match = first_match(
            r"[ \t]sbb[qwl]?[ \t]+(%[a-z0-9]+),[ \t]*\1(?:[ \t]|$)",
            mask_lines,
            compare,
            mask_file,
        )
        mask_register = re.escape(mask_match.group(1))
        masked_index = first_line(
            rf"[ \t]and[qwl]?[ \t]+{mask_register},[ \t]*{index}(?:[ \t]|$)",
            mask_lines,
            mask,
            mask_file,
        )
        first_line(
            rf"[ \t]and[qwl]?[ \t]+\([^,]+,[ \t]*{index},[^)]*\),"
            rf"[ \t]*{mask_register}(?:[ \t]|$)",
            mask_lines,
            masked_index,
            mask_file,
        )
        compare = first_line(r"[ \t]cmp[qwl]?[ \t]", barrier_lines, 0, barrier_file)
        branch = first_line(
            r"[ \t]j(a|ae|b|be|e|ne|z|nz)[ \t]", barrier_lines, compare, barrier_file
        )
        barrier = first_line(r"[ \t]lfence([ \t]|$)", barrier_lines, branch, barrier_file)
        first_line(
            r"[ \t]mov[qwl]?[ \t]+[^ \t]*\([^)]*\),", barrier_lines, barrier, barrier_file
        )
        return "cmp<conditional-branch<lfence<load"
    if architecture in ("aarch64", "arm64"):
        compare, compare_match = first_match(
            r"[ \t]cmp[ \t]+(x[0-9]+),[ \t]*x[0-9]+(?:[ \t]|$)",
            mask_lines,
            0,
            mask_file,
        )
        index = re.escape(compare_match.group(1))
        mask, mask_match = first_match(
            r"[ \t](?:ngc[ \t]+(x[0-9]+),[ \t]*xzr|"
            r"sbc[ \t]+(x[0-9]+),[ \t]*xzr,[ \t]*xzr)(?:[ \t]|$)",
            mask_lines,
            compare,
            mask_file,
        )
        mask_register = re.escape(mask_match.group(1) or mask_match.group(2))
        csdb = first_line(
            r"[ \t](csdb|hint[ \t]+#0x14)([ \t]|$)", mask_lines, mask, mask_file
        )
        masked_index, masked_index_match = first_match(
            rf"[ \t]and[ \t]+(x[0-9]+),[ \t]*(?:{mask_register},[ \t]*{index}|"
            rf"{index},[ \t]*{mask_register})(?:[ \t]|$)",
            mask_lines,
            csdb,
            mask_file,
        )
        safe_index = re.escape(masked_index_match.group(1))
        load, load_match = first_match(
            rf"[ \t]ldr[ \t]+(x[0-9]+),[ \t]*\[[^],]+,[ \t]*{safe_index}"
            rf"(?:,[^]]*)?\]",
            mask_lines,
            masked_index,
            mask_file,
        )
        loaded_word = re.escape(load_match.group(1))
        first_line(
            rf"[ \t]and[ \t]+x[0-9]+,[ \t]*(?:{loaded_word},[ \t]*{mask_register}|"
            rf"{mask_register},[ \t]*{loaded_word})(?:[ \t]|$)",
            mask_lines,
            load,
            mask_file,
        )
        compare = first_line(r"[ \t]cmp[ \t]", barrier_lines, 0, barrier_file)
        branch = first_line(r"[ \t]b\.[a-z]+[ \t]", barrier_lines, compare, barrier_file)
        dsb = first_line(r"[ \t]dsb[ \t]+nsh", barrier_lines, branch, barrier_file)
        isb = first_line(r"[ \t]isb([ \t]|$)", barrier_lines, dsb, barrier_file)
        first_line(r"[ \t]ldr[ \t]", barrier_lines, isb, barrier_file)
        return "cmp<conditional-branch<dsb-nsh<isb<load"
    raise CodegenError(f"unsupported Linux architecture for Topic 43: {architecture}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codegen-dir", type=Path, required=True)
    parser.add_argument("--architecture", required=True)
    args = parser.parse_args()
    try:
        barrier_order = check_codegen_dir(args.codegen_dir, args.architecture)
    except CodegenError as error:
        raise SystemExit(str(error)) from error
    print(barrier_order)


if __name__ == "__main__":
    main()
