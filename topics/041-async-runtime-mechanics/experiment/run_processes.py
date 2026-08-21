#!/usr/bin/env python3
"""Retain eight deterministic process receipts without timing the probe."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


OUTPUT_PATTERN = re.compile(
    rb"experiment=topic41-async-state-and-cancellation\n"
    rb"buffer_bytes=(?P<buffer>[0-9]+)\n"
    rb"future_large_bytes=(?P<large>[0-9]+)\n"
    rb"future_small_bytes=(?P<small>[0-9]+)\n"
    rb"future_size_delta_bytes=(?P<delta>[0-9]+)\n"
    rb"checksum=(?P<checksum>[0-9]+)\n"
    rb"large_polls=(?P<large_polls>[0-9]+) small_polls=(?P<small_polls>[0-9]+)\n"
    rb"unsafe_race=winner:11 left_remaining:0 right_remaining:0\n"
    rb"safe_race=winner:11 left_remaining:0 right_remaining:1\n"
    rb"wake_by_ref_calls=(?P<wakes>[0-9]+)\n"
    rb"outcome=PASS\n"
)


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_output(output: bytes) -> dict[str, int]:
    """Validate the deterministic state-layout and cancellation invariants."""

    match = OUTPUT_PATTERN.fullmatch(output)
    if match is None:
        raise ValueError("probe output does not match the receipt schema")
    values = {key: int(value) for key, value in match.groupdict().items()}
    if any(
        (
            values["buffer"] != 4096,
            values["large"] < values["buffer"],
            values["small"] >= values["buffer"],
            values["delta"] != values["large"] - values["small"],
            values["checksum"] != 522_240,
            values["large_polls"] != 2,
            values["small_polls"] != 2,
            values["wakes"] != 6,
        )
    ):
        raise ValueError("probe output violates a deterministic invariant")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=8)
    arguments = parser.parse_args()

    binary = arguments.binary.resolve()
    output = arguments.output.resolve()
    if arguments.runs != 8:
        parser.error("this receipt contract requires exactly eight fresh processes")
    if output.exists():
        parser.error(f"output already exists: {output}")
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"binary is not executable: {binary}")

    output.mkdir(parents=True)
    raw = output / "raw"
    raw.mkdir()
    retained_binary = output / "probe"
    shutil.copy2(binary, retained_binary)
    retained_binary.chmod(0o500)
    binary_digest = digest_path(retained_binary)

    rows: list[dict[str, str]] = []
    canonical: bytes | None = None
    canonical_values: dict[str, int] | None = None
    for sequence in range(1, arguments.runs + 1):
        launch_digest = digest_path(retained_binary)
        if launch_digest != binary_digest:
            raise RuntimeError(f"probe changed before process {sequence}")
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
        values = validate_output(completed.stdout)
        if canonical is None:
            canonical = completed.stdout
            canonical_values = values
        matches_canonical = completed.stdout == canonical
        rows.append(
            {
                "sequence": str(sequence),
                "binary_sha256_at_launch": launch_digest,
                "return_code": str(completed.returncode),
                "invariants_passed": "yes",
                "stdout_matches_canonical": "yes" if matches_canonical else "no",
                "stdout_sha256": digest_path(stdout_path),
                "stderr_sha256": digest_path(stderr_path),
                "stderr_bytes": str(stderr_path.stat().st_size),
            }
        )
        if completed.returncode != 0 or not matches_canonical or completed.stderr:
            raise RuntimeError(f"process {sequence} failed deterministic checks")

    assert canonical is not None
    assert canonical_values is not None
    canonical_path = output / "canonical.stdout"
    canonical_path.write_bytes(canonical)
    canonical_path.chmod(0o400)
    configuration = {
        "binary": retained_binary.name,
        "binary_sha256": binary_digest,
        "canonical_output": canonical_path.name,
        "canonical_output_sha256": digest_path(canonical_path),
        "fresh_process_runs": arguments.runs,
        "future_large_bytes": canonical_values["large"],
        "future_small_bytes": canonical_values["small"],
        "measurement_kind": "deterministic correctness and code generation only",
        "retry_policy": "none",
        "timing_reported": False,
    }
    (output / "config.json").write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output / "runs.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
