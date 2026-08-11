#!/usr/bin/env python3
"""Reconstruct Topic 32 process results without trusting the summary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


RUNS = 8


def sha256(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest for ``data``."""

    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    """Raise a validation failure with one direct message."""

    raise ValueError(message)


def main() -> int:
    """Validate raw receipts and one independent execution."""

    if len(sys.argv) != 3:
        print("usage: validate_receipts.py OUTPUT BINARY", file=sys.stderr)
        return 2

    output = Path(sys.argv[1]).resolve(strict=True)
    binary = Path(sys.argv[2]).resolve(strict=True)
    expected = (Path(__file__).resolve().parent / "expected.txt").read_bytes()
    expected_digest = sha256(expected)
    binary_digest = sha256(binary.read_bytes())

    recorded_binary = (output / "binary.sha256").read_text(encoding="utf-8").split()
    recorded_expected = (output / "expected.sha256").read_text(encoding="utf-8").split()
    if not recorded_binary or recorded_binary[0] != binary_digest:
        fail("recorded binary digest does not match the supplied binary")
    if not recorded_expected or recorded_expected[0] != expected_digest:
        fail("recorded expected-output digest does not match expected.txt")
    if sha256((output / "binary").read_bytes()) != binary_digest:
        fail("runner's private binary differs from the supplied binary")

    receipt_lines = (output / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
    if len(receipt_lines) != RUNS:
        fail(f"expected {RUNS} JSON receipts, found {len(receipt_lines)}")

    seen_runs: set[int] = set()
    for line in receipt_lines:
        receipt = json.loads(line)
        run_number = receipt.get("run")
        if not isinstance(run_number, int) or not 1 <= run_number <= RUNS:
            fail(f"invalid run number: {run_number!r}")
        if run_number in seen_runs:
            fail(f"duplicate run number: {run_number}")
        seen_runs.add(run_number)
        run_name = f"run-{run_number:02d}"
        stdout = (output / f"{run_name}.stdout").read_bytes()
        stderr = (output / f"{run_name}.stderr").read_bytes()
        exit_text = (output / f"{run_name}.exit").read_text(encoding="utf-8")
        try:
            exit_code = int(exit_text.strip())
        except ValueError as error:
            fail(f"{run_name} has an invalid exit receipt: {error}")

        assertions = {
            "exit_code": exit_code == 0 and receipt.get("exit_code") == 0,
            "passed": receipt.get("passed") is True,
            "timed_out": receipt.get("timed_out") is False,
            "stdout": stdout == expected,
            "stderr": stderr == b"",
            "stdout_bytes": receipt.get("stdout_bytes") == len(stdout),
            "stderr_bytes": receipt.get("stderr_bytes") == len(stderr),
            "stdout_sha256": receipt.get("stdout_sha256") == sha256(stdout),
            "stderr_sha256": receipt.get("stderr_sha256") == sha256(stderr),
        }
        failed = [name for name, passed in assertions.items() if not passed]
        if failed:
            fail(f"{run_name} failed reconstructed checks: {','.join(failed)}")

    if seen_runs != set(range(1, RUNS + 1)):
        fail("receipt set is incomplete")

    independent = subprocess.run(
        [str(binary), "--self-check"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    if (
        independent.returncode != 0
        or independent.stdout != expected
        or independent.stderr != b""
    ):
        fail("independent execution does not match the expected receipt")

    print(
        "VALIDATION=PASS "
        f"runs={RUNS} expected_sha256={expected_digest} binary_sha256={binary_digest}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
