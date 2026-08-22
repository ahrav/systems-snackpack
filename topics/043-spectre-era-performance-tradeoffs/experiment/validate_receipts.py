#!/usr/bin/env python3
"""Validate Topic 43 host, codegen, process, and analysis receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analyze import analyze_aa, analyze_timing, load_rows

REQUIRED = (
    "source-archive.tar.gz",
    "source-manifest-executing.sha256",
    "source-manifest-archive.sha256",
    "source-manifest.diff",
    "host.txt",
    "correctness.txt",
    "build.txt",
    "self-test.json",
    "aa-processes.jsonl",
    "aa-summary.json",
    "timing-processes.jsonl",
    "timing-summary.json",
    "codegen/codegen-check.txt",
    "codegen/topic43_plain_lookup.asm",
    "codegen/topic43_mask_lookup.asm",
    "codegen/topic43_barrier_lookup.asm",
    "codegen/topic43_speculation_barrier.asm",
)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt_dir", type=Path)
    args = parser.parse_args()
    root = args.receipt_dir.resolve()
    output = root / "receipt-validation.json"
    if output.exists():
        raise SystemExit("receipt validation output already exists")
    missing = [relative for relative in REQUIRED if not (root / relative).is_file()]
    if missing:
        raise SystemExit(f"missing receipts: {missing}")

    host = (root / "host.txt").read_text(encoding="utf-8")
    if any(
        marker not in host
        for marker in (
            "architecture=",
            "build_flags=-C target-cpu=native",
            "source_manifest_match=pass",
        )
    ):
        raise SystemExit("host receipt lacks architecture, build flags, or source binding")
    archive_digest = hashlib.sha256((root / "source-archive.tar.gz").read_bytes()).hexdigest()
    if f"source_archive_verified_sha256={archive_digest}" not in host:
        raise SystemExit("retained source archive differs from the verified digest")
    if (root / "source-manifest.diff").read_bytes():
        raise SystemExit("source manifest comparison is not empty")
    if "status=pass" not in (root / "codegen/codegen-check.txt").read_text(encoding="utf-8"):
        raise SystemExit("codegen inspection did not pass")
    if read_json(root / "self-test.json").get("status") != "pass":
        raise SystemExit("self-test did not pass")

    aa_recomputed = analyze_aa(load_rows(root / "aa-processes.jsonl"))
    timing_recomputed = analyze_timing(load_rows(root / "timing-processes.jsonl"))
    if read_json(root / "aa-summary.json") != aa_recomputed:
        raise SystemExit("A/A summary differs from retained process records")
    if read_json(root / "timing-summary.json") != timing_recomputed:
        raise SystemExit("timing summary differs from retained process records")
    if aa_recomputed["status"] != "pass" or timing_recomputed["status"] != "pass":
        raise SystemExit("a fixed experiment gate failed")

    digests = {}
    for relative in REQUIRED:
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        digests[relative] = digest
    validation = {
        "schema": "topic43-receipts-v1",
        "status": "pass",
        "required_file_sha256": digests,
        "process_replication": "8 paired A/A blocks and 24 three-process timing blocks",
        "interval_scope": "between-block variation in paired fresh-process log elapsed-time ratios",
        "security_claim": "none",
    }
    output.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
