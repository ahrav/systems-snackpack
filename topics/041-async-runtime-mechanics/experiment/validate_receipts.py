#!/usr/bin/env python3
"""Validate the eight-process Topic 41 correctness receipt set."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
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
    """Validate the retained deterministic probe output."""

    match = OUTPUT_PATTERN.fullmatch(output)
    if match is None:
        raise ValueError("canonical output does not match the receipt schema")
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
        raise ValueError("canonical output violates a deterministic invariant")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.root.resolve()

    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    required_keys = {
        "binary",
        "binary_sha256",
        "canonical_output",
        "canonical_output_sha256",
        "fresh_process_runs",
        "future_large_bytes",
        "future_small_bytes",
        "measurement_kind",
        "retry_policy",
        "timing_reported",
    }
    if set(config) != required_keys or any(
        (
            config["binary"] != "probe",
            config["canonical_output"] != "canonical.stdout",
            config["fresh_process_runs"] != 8,
            config["measurement_kind"]
            != "deterministic correctness and code generation only",
            config["retry_policy"] != "none",
            config["timing_reported"] is not False,
        )
    ):
        raise ValueError("configuration contract changed")

    binary = root / config["binary"]
    canonical_path = root / config["canonical_output"]
    canonical = canonical_path.read_bytes()
    values = validate_output(canonical)
    if any(
        (
            digest_path(binary) != config["binary_sha256"],
            digest_path(canonical_path) != config["canonical_output_sha256"],
            values["large"] != config["future_large_bytes"],
            values["small"] != config["future_small_bytes"],
        )
    ):
        raise ValueError("configuration digest or future-size record changed")

    with (root / "runs.tsv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        expected_fields = [
            "sequence",
            "binary_sha256_at_launch",
            "return_code",
            "invariants_passed",
            "stdout_matches_canonical",
            "stdout_sha256",
            "stderr_sha256",
            "stderr_bytes",
        ]
        if reader.fieldnames != expected_fields:
            raise ValueError("process receipt schema changed")
        rows = list(reader)
    if len(rows) != 8:
        raise ValueError(f"expected eight process rows, found {len(rows)}")
    if [row["sequence"] for row in rows] != [str(value) for value in range(1, 9)]:
        raise ValueError("process sequence is not exactly 1..8")

    empty_digest = hashlib.sha256(b"").hexdigest()
    for row in rows:
        sequence = int(row["sequence"])
        stdout_path = root / "raw" / f"run-{sequence:02d}.stdout"
        stderr_path = root / "raw" / f"run-{sequence:02d}.stderr"
        if any(
            (
                row["binary_sha256_at_launch"] != config["binary_sha256"],
                row["return_code"] != "0",
                row["invariants_passed"] != "yes",
                row["stdout_matches_canonical"] != "yes",
                stdout_path.read_bytes() != canonical,
                digest_path(stdout_path) != row["stdout_sha256"],
                row["stderr_sha256"] != empty_digest,
                digest_path(stderr_path) != empty_digest,
                row["stderr_bytes"] != "0",
            )
        ):
            raise ValueError(f"failed receipt for process {sequence}")

    print(
        "receipt_validation=PASS "
        f"processes=8 future_large_bytes={values['large']} "
        f"future_small_bytes={values['small']} timing_reported=no"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
