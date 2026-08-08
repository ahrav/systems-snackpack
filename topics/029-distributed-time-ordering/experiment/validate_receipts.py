#!/usr/bin/env python3
"""Validate Topic 29 fresh-process receipts without trusting the summary."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_processes import EXPECTED, RUNS


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for `data`."""

    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    """Abort validation with one stable diagnostic."""

    raise ValueError(message)


def main() -> int:
    """Recompute process counts, outputs, and hashes from raw files."""

    if len(sys.argv) != 2:
        print("usage: validate_receipts.py OUTPUT_DIRECTORY", file=sys.stderr)
        return 2

    output = Path(sys.argv[1]).resolve()
    expected = EXPECTED.encode()
    if (output / "expected.txt").read_bytes() != expected:
        fail("retained expected output differs from the source contract")
    rows = [
        json.loads(line)
        for line in (output / "processes.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(rows) != RUNS:
        fail(f"expected {RUNS} process rows, found {len(rows)}")

    for expected_run, row in enumerate(rows, start=1):
        if row.get("run") != expected_run:
            fail(f"unexpected run identity at row {expected_run}")
        stdout = (output / f"run-{expected_run:02d}.stdout").read_bytes()
        stderr = (output / f"run-{expected_run:02d}.stderr").read_bytes()
        if row.get("exit_code") != 0 or row.get("timed_out") is not False:
            fail(f"run {expected_run} did not exit normally")
        if row.get("passed") is not True:
            fail(f"run {expected_run} was not marked passed")
        if stdout != expected or stderr != b"":
            fail(f"run {expected_run} output differs from the contract")
        if row.get("stdout_sha256") != sha256_bytes(stdout):
            fail(f"run {expected_run} stdout digest differs")
        if row.get("stderr_sha256") != sha256_bytes(stderr):
            fail(f"run {expected_run} stderr digest differs")

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if summary.get("runs_planned") != RUNS or summary.get("runs_completed") != RUNS:
        fail("summary process count differs")
    if summary.get("failures") != 0:
        fail("summary reports a failure")
    if summary.get("expected_sha256") != sha256_bytes(expected):
        fail("expected-output digest differs")

    binary_line = (output / "binary.sha256").read_text(encoding="utf-8").strip()
    fields = binary_line.split()
    if len(fields) != 2 or fields[0] != summary.get("binary_sha256"):
        fail("binary identity differs from summary")

    print("receipt validation: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"receipt validation: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
