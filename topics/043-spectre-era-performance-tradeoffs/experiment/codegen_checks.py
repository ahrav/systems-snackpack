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


def first_line(pattern: str, lines: list[str], minimum: int, file: str) -> int:
    """Return the 1-based number of the first match strictly after ``minimum``."""

    for number, line in enumerate(lines, 1):
        if number > minimum and re.search(pattern, line):
            return number
    raise CodegenError(
        f"missing ordered instruction pattern {pattern!r} after line {minimum} in {file}"
    )


def require(pattern: str, lines: list[str], file: str) -> None:
    if not any(re.search(pattern, line) for line in lines):
        raise CodegenError(f"missing instruction pattern {pattern!r} in {file}")


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
        require(r"[ \t]cmp[qwl]?[ \t]", mask_lines, mask_file)
        require(r"[ \t]sbb[qwl]?[ \t]", mask_lines, mask_file)
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
        require(r"[ \t]cmp[ \t]", mask_lines, mask_file)
        require(r"[ \t](sbc|ngc)[ \t]", mask_lines, mask_file)
        require(r"[ \t](csdb|hint[ \t]+#0x14)([ \t]|$)", mask_lines, mask_file)
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
