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


Instruction = tuple[int, str, str]


def instruction_stream(asm: Path, symbol: str) -> list[Instruction]:
    """Parse GNU objdump instruction addresses, mnemonics, and operands."""

    text = asm.read_text(encoding="utf-8")
    if f"<{symbol}>" not in text:
        raise CodegenError(f"{asm.name} does not disassemble {symbol}")
    code = []
    for line in text.splitlines():
        match = re.match(r"^\s*([0-9a-f]+):\s+([a-z][a-z0-9.]*)\s*(.*?)\s*$", line)
        if match:
            code.append((int(match.group(1), 16), match.group(2), match.group(3)))
    if not code:
        raise CodegenError(f"{asm.name} contains no instructions")
    return code


def operand_match(
    code: list[Instruction], index: int, mnemonics: tuple[str, ...], pattern: str, file: str
) -> re.Match[str]:
    """Match one exact instruction position and return its operand captures."""

    if index >= len(code) or code[index][1] not in mnemonics:
        expected = "/".join(mnemonics)
        raise CodegenError(f"expected adjacent {expected} instruction in {file}")
    match = re.fullmatch(pattern, code[index][2])
    if not match:
        raise CodegenError(f"unexpected {code[index][1]} operands in {file}: {code[index][2]}")
    return match


def first_mnemonic(code: list[Instruction], mnemonics: tuple[str, ...], file: str) -> int:
    for index, (_, mnemonic, _) in enumerate(code):
        if mnemonic in mnemonics:
            return index
    raise CodegenError(f"missing {'/'.join(mnemonics)} instruction in {file}")


def require_branch_target(
    code: list[Instruction], branch: int, target_index: int, file: str
) -> None:
    """Require a branch to target one exact instruction in its symbol."""

    match = re.match(r"([0-9a-f]+)\b", code[branch][2])
    if not match:
        raise CodegenError(f"cannot parse branch target in {file}: {code[branch][2]}")
    target = int(match.group(1), 16)
    if target != code[target_index][0]:
        raise CodegenError(f"unexpected out-of-bounds branch target in {file}")


def check_x86(mask: list[Instruction], barrier: list[Instruction]) -> str:
    mask_file = "topic43_mask_lookup.asm"
    compare = first_mnemonic(mask, ("cmp", "cmpq", "cmpl", "cmpw"), mask_file)
    compare_match = operand_match(
        mask, compare, (mask[compare][1],), r"%[a-z0-9]+,\s*(%[a-z0-9]+)", mask_file
    )
    index = re.escape(compare_match.group(1))
    mask_match = operand_match(
        mask,
        compare + 1,
        ("sbb", "sbbq", "sbbl", "sbbw"),
        r"(%[a-z0-9]+),\s*\1",
        mask_file,
    )
    mask_register = re.escape(mask_match.group(1))
    operand_match(
        mask,
        compare + 2,
        ("and", "andq", "andl", "andw"),
        rf"{mask_register},\s*{index}",
        mask_file,
    )
    load = compare + 3
    while load < len(mask) and not re.fullmatch(
        rf"\([^,]+,\s*{index},[^)]*\),\s*{mask_register}", mask[load][2]
    ):
        load += 1
    operand_match(
        mask,
        load,
        ("and", "andq", "andl", "andw"),
        rf"\([^,]+,\s*{index},[^)]*\),\s*{mask_register}",
        mask_file,
    )

    barrier_file = "topic43_barrier_lookup.asm"
    compare = first_mnemonic(barrier, ("cmp", "cmpq", "cmpl", "cmpw"), barrier_file)
    if compare != 0 or len(barrier) != 7:
        raise CodegenError(f"unexpected instruction graph in {barrier_file}")
    compare_match = operand_match(
        barrier,
        compare,
        (barrier[compare][1],),
        r"%[a-z0-9]+,\s*(%[a-z0-9]+)",
        barrier_file,
    )
    index = re.escape(compare_match.group(1))
    operand_match(barrier, compare + 1, ("jae", "jnb", "jnc"), r"[0-9a-f]+.*", barrier_file)
    operand_match(barrier, compare + 2, ("lfence",), r"", barrier_file)
    operand_match(
        barrier,
        compare + 3,
        ("mov", "movq", "movl", "movw"),
        rf"\([^,]+,\s*{index},[^)]*\),\s*%[a-z0-9]+",
        barrier_file,
    )
    operand_match(barrier, compare + 4, ("ret", "retq"), r"", barrier_file)
    operand_match(
        barrier,
        compare + 5,
        ("xor", "xorl", "xorq"),
        r"(%[a-z0-9]+),\s*\1",
        barrier_file,
    )
    operand_match(barrier, compare + 6, ("ret", "retq"), r"", barrier_file)
    require_branch_target(barrier, compare + 1, compare + 5, barrier_file)
    return "cmp<conditional-branch<lfence<load"


def check_arm(mask: list[Instruction], barrier: list[Instruction]) -> str:
    mask_file = "topic43_mask_lookup.asm"
    compare = first_mnemonic(mask, ("cmp",), mask_file)
    compare_match = operand_match(mask, compare, ("cmp",), r"(x[0-9]+),\s*x[0-9]+", mask_file)
    index = re.escape(compare_match.group(1))
    if compare + 1 >= len(mask) or mask[compare + 1][1] not in ("ngc", "sbc"):
        raise CodegenError(f"expected adjacent ngc/sbc instruction in {mask_file}")
    if mask[compare + 1][1] == "ngc":
        mask_match = operand_match(mask, compare + 1, ("ngc",), r"(x[0-9]+),\s*xzr", mask_file)
    else:
        mask_match = operand_match(
            mask, compare + 1, ("sbc",), r"(x[0-9]+),\s*xzr,\s*xzr", mask_file
        )
    mask_register = re.escape(mask_match.group(1))
    barrier_mnemonic = mask[compare + 2][1] if compare + 2 < len(mask) else ""
    barrier_operands = r"" if barrier_mnemonic == "csdb" else r"#0x14"
    operand_match(
        mask, compare + 2, ("csdb", "hint"), barrier_operands, mask_file
    )
    safe_match = operand_match(
        mask,
        compare + 3,
        ("and",),
        rf"(x[0-9]+),\s*(?:{mask_register},\s*{index}|{index},\s*{mask_register})",
        mask_file,
    )
    safe_index = re.escape(safe_match.group(1))
    load = first_mnemonic(mask[compare + 4 :], ("ldr",), mask_file) + compare + 4
    load_match = operand_match(
        mask,
        load,
        ("ldr",),
        rf"(x[0-9]+),\s*\[[^],]+,\s*{safe_index}(?:,[^]]*)?\]",
        mask_file,
    )
    loaded_word = re.escape(load_match.group(1))
    operand_match(
        mask,
        load + 1,
        ("and",),
        rf"x[0-9]+,\s*(?:{loaded_word},\s*{mask_register}|{mask_register},\s*{loaded_word})",
        mask_file,
    )

    barrier_file = "topic43_barrier_lookup.asm"
    compare = first_mnemonic(barrier, ("cmp",), barrier_file)
    if compare != 0 or len(barrier) != 8:
        raise CodegenError(f"unexpected instruction graph in {barrier_file}")
    compare_match = operand_match(
        barrier, compare, ("cmp",), r"(x[0-9]+),\s*x[0-9]+", barrier_file
    )
    index = re.escape(compare_match.group(1))
    operand_match(barrier, compare + 1, ("b.cs", "b.hs"), r"[0-9a-f]+.*", barrier_file)
    operand_match(barrier, compare + 2, ("dsb",), r"nsh", barrier_file)
    operand_match(barrier, compare + 3, ("isb",), r"", barrier_file)
    operand_match(
        barrier,
        compare + 4,
        ("ldr",),
        rf"x[0-9]+,\s*\[[^],]+,\s*{index}(?:,[^]]*)?\]",
        barrier_file,
    )
    operand_match(barrier, compare + 5, ("ret",), r"", barrier_file)
    operand_match(barrier, compare + 6, ("mov",), r"x0,\s*xzr", barrier_file)
    operand_match(barrier, compare + 7, ("ret",), r"", barrier_file)
    require_branch_target(barrier, compare + 1, compare + 6, barrier_file)
    return "cmp<conditional-branch<dsb-nsh<isb<load"


def check_codegen_dir(codegen_dir: Path, architecture: str) -> str:
    """Validate the retained assembly for ``architecture``; return the barrier order."""

    streams = {
        symbol: instruction_stream(codegen_dir / f"{symbol}.asm", symbol) for symbol in SYMBOLS
    }
    if architecture == "x86_64":
        return check_x86(streams["topic43_mask_lookup"], streams["topic43_barrier_lookup"])
    if architecture in ("aarch64", "arm64"):
        return check_arm(streams["topic43_mask_lookup"], streams["topic43_barrier_lookup"])
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
