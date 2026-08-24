#!/usr/bin/env python3
"""Require byte-identical fresh processes and retain output and digest receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    """Return one file's SHA-256 digest."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    """Run the eight-process correctness contract without retry."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--expected", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=int)
    arguments = parser.parse_args()

    if arguments.runs != 8:
        raise SystemExit("this round requires exactly eight fresh processes")
    arguments.output.mkdir(parents=True, exist_ok=False)
    expected = arguments.expected.read_bytes()
    executable_digest = digest(arguments.binary)
    # The child environment below drops PATH, so a bare relative name would be
    # unresolvable; the absolute path keeps execution independent of lookup.
    probe = str(arguments.binary.resolve())

    records = []
    for run in range(1, arguments.runs + 1):
        if digest(arguments.binary) != executable_digest:
            raise SystemExit("executable changed between processes")
        completed = subprocess.run(
            [probe],
            check=False,
            capture_output=True,
            env={"LANG": "C", "LC_ALL": "C"},
        )
        stdout_path = arguments.output / f"run-{run:02d}.stdout"
        stderr_path = arguments.output / f"run-{run:02d}.stderr"
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        passed = completed.returncode == 0 and completed.stdout == expected and not completed.stderr
        records.append(
            {
                "run": run,
                "exit_status": completed.returncode,
                "passed": passed,
                "executable_sha256": executable_digest,
                "stdout_sha256": digest(stdout_path),
                "stderr_sha256": digest(stderr_path),
            }
        )
        if not passed:
            raise SystemExit(f"process {run} did not match expected output")

    with (arguments.output / "processes.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"fresh_processes={len(records)}")
    print(f"executable_sha256={executable_digest}")
    print("status=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
