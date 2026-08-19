#!/usr/bin/env python3
"""Retain independent process-level correctness receipts without timing them."""

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--flavor", choices=("generic", "native"), required=True)
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
    retained_binary = output / "probe"
    shutil.copy2(binary, retained_binary)
    # Owner read and execute only. The per-launch digest below is what
    # actually binds each replicate to these bytes; dropping the write bit
    # just removes the accidental path. A same-user process that rewrites
    # this file, cargo, or python itself is outside the runner's trust
    # boundary and no in-process check can exclude it.
    retained_binary.chmod(0o500)
    binary_digest = digest_path(retained_binary)
    # Retain the expected output the receipt names. The runner deletes its
    # private source copy, so without this a retrieved bundle could not rerun
    # the exact-output validation or read the contract bytes it claims.
    retained_expected = output / expected.name
    shutil.copy2(expected, retained_expected)
    retained_expected.chmod(0o400)
    expected_digest = hashlib.sha256(expected_bytes).hexdigest()
    if digest_path(retained_expected) != expected_digest:
        raise RuntimeError("retained expected output does not match its source")
    configuration = {
        "binary": retained_binary.name,
        "binary_sha256": binary_digest,
        "expected": expected.name,
        "expected_sha256": expected_digest,
        "flavor": arguments.flavor,
        "fresh_process_runs": arguments.runs,
        "measurement_kind": "deterministic correctness only",
        "real_dma_exercised": False,
        "retry_policy": "none",
        "timing_reported": False,
    }
    (output / "config.json").write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows = []
    for sequence in range(1, arguments.runs + 1):
        # Attest the bytes this replicate is about to execute. Hashing only
        # before the loop and once after would accept a substituted probe
        # that was restored before validation.
        launch_digest = digest_path(retained_binary)
        if launch_digest != binary_digest:
            raise RuntimeError(
                f"{arguments.flavor} probe changed before process {sequence}"
            )
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
                "flavor": arguments.flavor,
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
                f"{arguments.flavor} process {sequence} failed deterministic output checks"
            )

    with (output / "runs.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
