#!/usr/bin/env python3
"""Run the deterministic Topic 29 self-check in eight fresh processes."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

RUNS = 8
EXPECTED = Path(__file__).with_name("expected.txt").read_text(encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase SHA-256 digest for `data`."""

    return hashlib.sha256(data).hexdigest()


def main() -> int:
    """Run the fixed process schedule and retain every receipt."""

    if len(sys.argv) != 3:
        print("usage: run_processes.py BINARY OUTPUT_DIRECTORY", file=sys.stderr)
        return 2

    binary = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    if not binary.is_file():
        print(f"binary does not exist: {binary}", file=sys.stderr)
        return 2
    if output.exists():
        print(f"output already exists: {output}", file=sys.stderr)
        return 2

    output.mkdir(parents=True)
    expected_bytes = EXPECTED.encode()
    (output / "expected.txt").write_bytes(expected_bytes)
    # A private copy prevents a concurrent Cargo rebuild from swapping the
    # binary between hashing and spawning. commentlint: allow(JUDGE)
    executed = output / "binary-under-test"
    shutil.copy2(binary, executed)
    binary_digest = sha256_bytes(executed.read_bytes())
    (output / "binary.sha256").write_text(
        f"{binary_digest}  {binary.name}\n", encoding="utf-8"
    )

    rows: list[dict[str, object]] = []
    failures = 0
    with (output / "processes.jsonl").open("w", encoding="utf-8") as ledger:
        for run in range(1, RUNS + 1):
            try:
                result = subprocess.run(
                    [str(executed), "--self-check"],
                    capture_output=True,
                    check=False,
                    timeout=10,
                )
                exit_code = result.returncode
                stdout = result.stdout
                stderr = result.stderr
                timed_out = False
            except subprocess.TimeoutExpired as error:
                exit_code = None
                stdout = error.stdout or b""
                stderr = error.stderr or b""
                timed_out = True

            stdout_path = output / f"run-{run:02d}.stdout"
            stderr_path = output / f"run-{run:02d}.stderr"
            stdout_path.write_bytes(stdout)
            stderr_path.write_bytes(stderr)
            passed = (
                not timed_out
                and exit_code == 0
                and stdout == expected_bytes
                and stderr == b""
            )
            failures += int(not passed)
            row = {
                "run": run,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "passed": passed,
                "stdout_sha256": sha256_bytes(stdout),
                "stderr_sha256": sha256_bytes(stderr),
            }
            rows.append(row)
            ledger.write(json.dumps(row, sort_keys=True) + "\n")
            ledger.flush()

    summary = {
        "binary_sha256": binary_digest,
        "expected_sha256": sha256_bytes(expected_bytes),
        "failures": failures,
        "runs_completed": len(rows),
        "runs_planned": RUNS,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    executed.unlink()
    print(json.dumps(summary, sort_keys=True))
    return int(failures != 0)


if __name__ == "__main__":
    raise SystemExit(main())
