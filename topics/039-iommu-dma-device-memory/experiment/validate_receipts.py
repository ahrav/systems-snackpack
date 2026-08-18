#!/usr/bin/env python3
"""Validate both eight-process Topic 39 correctness receipt sets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for one file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_flavor(root: Path, expected: bytes, flavor: str) -> None:
    """Require exact outputs and identities for one build flavor."""

    flavor_root = root / flavor
    config = json.loads((flavor_root / "config.json").read_text(encoding="utf-8"))
    expected_digest = hashlib.sha256(expected).hexdigest()
    required_keys = {
        "binary",
        "binary_sha256",
        "expected",
        "expected_sha256",
        "flavor",
        "fresh_process_runs",
        "measurement_kind",
        "real_dma_exercised",
        "retry_policy",
        "timing_reported",
    }
    if set(config) != required_keys or any(
        (
            config["binary"] != "probe",
            config["expected"] != "expected.txt",
            config["flavor"] != flavor,
            config["fresh_process_runs"] != 8,
            config["measurement_kind"] != "deterministic correctness only",
            config["real_dma_exercised"] is not False,
            config["retry_policy"] != "none",
            config["timing_reported"] is not False,
        )
    ):
        raise ValueError(f"{flavor}: configuration contract changed")
    if config["expected_sha256"] != expected_digest:
        raise ValueError(f"{flavor}: expected-output digest mismatch")
    binary = flavor_root / config["binary"]
    if digest_path(binary) != config["binary_sha256"]:
        raise ValueError(f"{flavor}: binary changed after the process run")
    # The bundle must carry the expected output its receipt names, so this
    # validation can be rerun from a retrieved archive alone.
    retained_expected = flavor_root / config["expected"]
    if not retained_expected.is_file():
        raise ValueError(f"{flavor}: bundle does not retain {config['expected']}")
    if digest_path(retained_expected) != expected_digest:
        raise ValueError(f"{flavor}: retained expected output digest mismatch")
    if retained_expected.read_bytes() != expected:
        raise ValueError(f"{flavor}: retained expected output differs from the supplied one")

    with (flavor_root / "runs.tsv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected_fields = [
            "sequence",
            "flavor",
            "binary_sha256_at_launch",
            "return_code",
            "stdout_matches_expected",
            "stdout_sha256",
            "stderr_sha256",
            "stderr_bytes",
        ]
        if reader.fieldnames != expected_fields:
            raise ValueError(f"{flavor}: process receipt schema changed")
        rows = list(reader)
    if len(rows) != 8:
        raise ValueError(f"{flavor}: expected eight process rows, found {len(rows)}")
    if [row["sequence"] for row in rows] != [str(value) for value in range(1, 9)]:
        raise ValueError(f"{flavor}: process sequence is not exactly 1..8")

    empty_digest = hashlib.sha256(b"").hexdigest()
    for row in rows:
        sequence = int(row["sequence"])
        stdout_path = flavor_root / "raw" / f"run-{sequence:02d}.stdout"
        stderr_path = flavor_root / "raw" / f"run-{sequence:02d}.stderr"
        if (
            row["flavor"] != flavor
            or row["binary_sha256_at_launch"] != config["binary_sha256"]
            or row["return_code"] != "0"
            or row["stdout_matches_expected"] != "yes"
            or row["stderr_bytes"] != "0"
            or stdout_path.read_bytes() != expected
            or digest_path(stdout_path) != row["stdout_sha256"]
            or row["stderr_sha256"] != empty_digest
            or digest_path(stderr_path) != empty_digest
        ):
            raise ValueError(f"{flavor}: failed receipt for process {sequence}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    arguments = parser.parse_args()
    expected = arguments.expected.read_bytes()
    validate_flavor(arguments.root, expected, "generic")
    validate_flavor(arguments.root, expected, "native")
    print("receipt_validation=PASS generic_processes=8 native_processes=8 timing_reported=no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
