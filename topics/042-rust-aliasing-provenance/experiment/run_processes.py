#!/usr/bin/env python3
"""Run exactly eight fresh correctness processes and retain their outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    """Run and retain the fixed eight-process correctness contract."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=8)
    arguments = parser.parse_args()

    binary = arguments.binary.resolve()
    expected = arguments.expected.resolve()
    output = arguments.output.resolve()
    if arguments.runs != 8:
        parser.error("this receipt contract requires exactly eight fresh processes")
    if output.exists():
        parser.error(f"output already exists: {output}")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"binary is not executable: {binary}")
    if not expected.is_file():
        parser.error(f"expected output does not exist: {expected}")

    expected_bytes = expected.read_bytes()
    output.mkdir(parents=True)
    raw = output / "raw"
    raw.mkdir()
    retained_binary = output / "provenance-demo"
    retained_expected = output / "expected.txt"
    shutil.copy2(binary, retained_binary)
    shutil.copy2(expected, retained_expected)
    retained_binary.chmod(0o500)
    retained_expected.chmod(0o400)
    binary_digest = digest_path(retained_binary)
    expected_digest = hashlib.sha256(expected_bytes).hexdigest()
    if digest_path(retained_expected) != expected_digest:
        raise RuntimeError("retained expected output differs from its source")

    configuration = {
        "binary": retained_binary.name,
        "binary_sha256": binary_digest,
        "expected": retained_expected.name,
        "expected_sha256": expected_digest,
        "fresh_process_runs": arguments.runs,
        "measurement_kind": "deterministic correctness and codegen only",
        "retry_policy": "none",
        "timing_reported": False,
    }
    (output / "config.json").write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows: list[dict[str, str]] = []
    for sequence in range(1, arguments.runs + 1):
        launch_digest = digest_path(retained_binary)
        if launch_digest != binary_digest:
            raise RuntimeError(f"binary changed before process {sequence}")
        completed = subprocess.run(
            [str(retained_binary)],
            check=False,
            capture_output=True,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
            timeout=120,
        )
        stdout_path = raw / f"run-{sequence:02d}.stdout"
        stderr_path = raw / f"run-{sequence:02d}.stderr"
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        matches = completed.stdout == expected_bytes
        rows.append(
            {
                "sequence": str(sequence),
                "binary_sha256_at_launch": launch_digest,
                "return_code": str(completed.returncode),
                "stdout_matches_expected": "yes" if matches else "no",
                "stdout_sha256": digest_path(stdout_path),
                "stderr_sha256": digest_path(stderr_path),
                "stderr_bytes": str(stderr_path.stat().st_size),
            }
        )
        if completed.returncode != 0 or not matches or completed.stderr:
            raise RuntimeError(
                f"process {sequence} failed the deterministic output contract"
            )

    with (output / "runs.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
