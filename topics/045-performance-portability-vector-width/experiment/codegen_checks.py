#!/usr/bin/env python3
"""Check retained Topic 45 loops for the intended independent vector work."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


# capture_codegen.sh always passes --no-show-raw-insn, so the mnemonic follows
# the address directly. A raw-byte skip group here would swallow mnemonics made
# entirely of hexadecimal characters (Arm "fadd" parses as bytes, leaving "d0"
# as the mnemonic).
INSTRUCTION = re.compile(
    r"^\s*([0-9a-f]+):\s+([.a-z0-9]+)\s*(.*?)\s*$",
    re.IGNORECASE,
)
VECTOR_REGISTER = re.compile(r"\b[xyz]mm([0-9]+)\b|\bv([0-9]+)(?:\.[0-9a-z]+)?\b", re.IGNORECASE)
SCALAR_DOUBLE_REGISTER = re.compile(r"\bd([0-9]+)\b", re.IGNORECASE)


def instructions(path: Path) -> list[tuple[int, str, str]]:
    """Parse address, mnemonic, and operands from one GNU objdump file."""

    parsed = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = INSTRUCTION.match(line)
        if match:
            parsed.append((int(match.group(1), 16), match.group(2).lower(), match.group(3).lower()))
    if not parsed:
        raise ValueError(f"no instructions parsed from {path}")
    return parsed


def register_numbers(operands: str) -> list[int]:
    """Return vector-register numbers in assembly operand order."""

    result = []
    for match in VECTOR_REGISTER.finditer(operands):
        result.append(int(match.group(1) or match.group(2)))
    return result


def x86_destinations(rows: list[tuple[int, str, str]], width: str, suffix: str) -> set[int]:
    """Return AT&T-syntax destination registers for matching x86 FMA operations."""

    destinations = set()
    for _, mnemonic, operands in rows:
        if mnemonic.startswith("vfmadd") and mnemonic.endswith(suffix):
            registers = re.findall(rf"%{width}([0-9]+)\b", operands)
            if registers:
                destinations.add(int(registers[-1]))
    return destinations


def x86_hot_loop(rows: list[tuple[int, str, str]], suffix: str) -> list[tuple[int, str, str]]:
    """Select the smallest backward-branch region with the most matching x86 FMA work."""

    candidates = []
    for branch_index, (address, mnemonic, operands) in enumerate(rows):
        if not mnemonic.startswith("j"):
            continue
        target_text = operands.split()[0].removeprefix("0x")
        try:
            target = int(target_text, 16)
        except ValueError:
            continue
        if target >= address:
            continue
        region = [row for row in rows[: branch_index + 1] if target <= row[0] <= address]
        fma_count = sum(
            instruction.startswith("vfmadd") and instruction.endswith(suffix)
            for _, instruction, _ in region
        )
        if fma_count:
            candidates.append((fma_count, -len(region), region))
    if not candidates:
        raise ValueError(f"no backward x86 branch contains vfmadd*{suffix}")
    return max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def arm_hot_loop(
    rows: list[tuple[int, str, str]], fma_mnemonic: str
) -> list[tuple[int, str, str]]:
    """Select the smallest backward-branch region with the most requested FMA work."""

    candidates = []
    for branch_index, (address, mnemonic, operands) in enumerate(rows):
        if not mnemonic.startswith("b."):
            continue
        target_text = operands.split()[0].removeprefix("0x")
        try:
            target = int(target_text, 16)
        except ValueError:
            continue
        if target >= address:
            continue
        region = [row for row in rows[: branch_index + 1] if target <= row[0] <= address]
        fma_count = sum(mnemonic == fma_mnemonic for _, mnemonic, _ in region)
        if fma_count:
            candidates.append((fma_count, -len(region), region))
    if not candidates:
        raise ValueError(f"no backward Arm branch contains {fma_mnemonic}")
    return max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def check_x86(codegen_dir: Path) -> dict[str, object]:
    """Require scalar, XMM, YMM, and ZMM loops with 12 independent destinations."""

    requirements = [
        ("kernel_scalar", "xmm", "sd"),
        ("kernel_v128", "xmm", "pd"),
        ("kernel_v256", "ymm", "pd"),
        ("kernel_v512", "zmm", "pd"),
    ]
    result = {}
    for symbol, width, suffix in requirements:
        rows = instructions(codegen_dir / f"{symbol}.asm")
        hot_loop = x86_hot_loop(rows, suffix)
        fma_count = sum(
            mnemonic.startswith("vfmadd") and mnemonic.endswith(suffix)
            for _, mnemonic, _ in hot_loop
        )
        destinations = x86_destinations(hot_loop, width, suffix)
        if fma_count != 12 or len(destinations) != 12:
            raise ValueError(
                f"{symbol} hot loop has {fma_count} FMA operations and "
                f"{len(destinations)} {width} destinations; expected exactly 12 of each"
            )
        if any("(" in operands or "[" in operands for _, _, operands in hot_loop):
            raise ValueError(f"{symbol} hot loop contains a memory operand")
        if any(mnemonic.startswith(("mov", "vmov")) for _, mnemonic, _ in hot_loop):
            raise ValueError(f"{symbol} hot loop contains a register copy")
        result[symbol] = {
            "fma_width": width,
            "independent_destinations": sorted(destinations),
            "hot_loop_start": hex(hot_loop[0][0]),
            "hot_loop_end": hex(hot_loop[-1][0]),
        }
    return result


def require_only(
    hot_loop: list[tuple[int, str, str]], allowed: set[str], symbol: str
) -> None:
    """Reject any instruction outside the FMA and integer loop-control allowlist."""

    unexpected = sorted({mnemonic for _, mnemonic, _ in hot_loop if mnemonic not in allowed})
    if unexpected:
        raise ValueError(f"{symbol} hot loop contains unexpected instructions: {unexpected}")


def check_arm(codegen_dir: Path) -> dict[str, object]:
    """Require 12-destination Arm FMA loops with only explicit loop-control work."""

    scalar_rows = instructions(codegen_dir / "kernel_scalar.asm")
    scalar_hot_loop = arm_hot_loop(scalar_rows, "fmadd")
    scalar_destinations = {
        int(registers[0])
        for _, mnemonic, operands in scalar_hot_loop
        if mnemonic == "fmadd" and (registers := SCALAR_DOUBLE_REGISTER.findall(operands))
    }
    scalar_fma_count = sum(mnemonic == "fmadd" for _, mnemonic, _ in scalar_hot_loop)
    if scalar_fma_count != 12 or len(scalar_destinations) != 12:
        raise ValueError(
            f"kernel_scalar hot loop has {scalar_fma_count} fmadd operations and "
            f"{len(scalar_destinations)} destinations; expected exactly 12 of each"
        )
    require_only(scalar_hot_loop, {"add", "fmadd", "cmp", "b.ne"}, "kernel_scalar")

    vector_rows = instructions(codegen_dir / "kernel_v128.asm")
    hot_loop = arm_hot_loop(vector_rows, "fmla")
    vector_destinations = {
        registers[0]
        for _, mnemonic, operands in hot_loop
        if mnemonic == "fmla" and (registers := register_numbers(operands))
    }
    fmla_count = sum(mnemonic == "fmla" for _, mnemonic, _ in hot_loop)
    if fmla_count != 12 or len(vector_destinations) != 12:
        raise ValueError(
            f"kernel_v128 hot loop has {fmla_count} fmla operations and "
            f"{len(vector_destinations)} destinations; expected exactly 12 of each"
        )
    require_only(hot_loop, {"add", "fmla", "cmp", "b.ne"}, "kernel_v128")

    return {
        "kernel_scalar": {
            "fma_width": "scalar-double",
            "independent_destinations": sorted(scalar_destinations),
            "hot_loop_start": hex(scalar_hot_loop[0][0]),
            "hot_loop_end": hex(scalar_hot_loop[-1][0]),
            "register_copies": 0,
        },
        "kernel_v128": {
            "fma_width": "v-register-2d",
            "independent_destinations": sorted(vector_destinations),
            "hot_loop_start": hex(hot_loop[0][0]),
            "hot_loop_end": hex(hot_loop[-1][0]),
            "vector_register_copies": 0,
        },
    }


def main() -> None:
    """Validate one retained code-generation directory and print JSON."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--codegen-dir", type=Path, required=True)
    parser.add_argument("--architecture", choices=["x86_64", "aarch64", "arm64"], required=True)
    args = parser.parse_args()

    result = check_x86(args.codegen_dir) if args.architecture == "x86_64" else check_arm(args.codegen_dir)
    print(json.dumps({"status": "pass", "architecture": args.architecture, "kernels": result},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
