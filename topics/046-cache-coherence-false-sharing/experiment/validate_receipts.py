#!/usr/bin/env python3
"""Validate source-bound Topic 46 Linux host receipts."""

import argparse
import hashlib
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt_dir")
    parser.add_argument("--expected-label", required=True)
    parser.add_argument("--expected-resolved-host", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-blocks", required=True, type=int)
    parser.add_argument("--expected-aa-blocks", required=True, type=int)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def key_values(path):
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values.setdefault(key, value)
    return values


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    args = parse_args()
    root = Path(args.receipt_dir).resolve()
    output = Path(args.output).resolve()
    required = [
        "source-archive.tar.gz",
        "source-manifest-before.sha256",
        "source-manifest-after.sha256",
        "source-manifest.diff",
        "host.txt",
        "correctness.txt",
        "build.txt",
        "binary.sha256",
        "codegen-increment.txt",
        "codegen-check.txt",
        "smoke-packed.json",
        "smoke-padded.json",
        "experiment/metadata.json",
        "experiment/attempts.jsonl",
        "experiment/summary.json",
    ]
    for relative in required:
        require((root / relative).is_file(), f"missing receipt: {relative}")

    host = key_values(root / "host.txt")
    expected_host = {
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_archive_sha256,
        "ssh_target_label": args.expected_label,
        "ssh_resolved_hostname": args.expected_resolved_host,
        "runtime_hostname": args.expected_resolved_host,
        "architecture": args.expected_architecture,
        "blocks": str(args.expected_blocks),
        "aa_blocks": str(args.expected_aa_blocks),
    }
    require(all(host.get(key) == value for key, value in expected_host.items()), "host identity mismatch")
    require("/coherency_line_size:64" in host.get("coherence_line_sizes", ""), "missing 64-byte line evidence")
    require(sha256(root / "source-archive.tar.gz") == args.expected_archive_sha256, "archive digest mismatch")
    require((root / "source-manifest-before.sha256").read_bytes() == (root / "source-manifest-after.sha256").read_bytes(), "source changed during run")
    require((root / "source-manifest.diff").read_bytes() == b"", "source manifest diff is not empty")
    require("CORRECTNESS_STATUS=pass" in (root / "correctness.txt").read_text(), "correctness gate failed")
    require("BUILD_STATUS=pass" in (root / "build.txt").read_text(), "build gate failed")
    require("status=PASS" in (root / "codegen-check.txt").read_text(), "codegen check failed")

    smoke_packed = json.loads((root / "smoke-packed.json").read_text())
    smoke_padded = json.loads((root / "smoke-padded.json").read_text())
    require(smoke_packed.get("mode") == "packed" and smoke_packed.get("correct") is True, "packed smoke failed")
    require(smoke_padded.get("mode") == "padded" and smoke_padded.get("correct") is True, "padded smoke failed")

    metadata = json.loads((root / "experiment/metadata.json").read_text())
    attempts = [json.loads(line) for line in (root / "experiment/attempts.jsonl").read_text().splitlines()]
    summary = json.loads((root / "experiment/summary.json").read_text())
    expected_attempts = 4 * (args.expected_blocks + args.expected_aa_blocks)
    require(len(attempts) == expected_attempts, "wrong attempt count")
    require(all(record.get("valid") is True for record in attempts), "invalid attempt retained")
    require([record.get("attempt") for record in attempts] == list(range(1, expected_attempts + 1)), "attempt sequence mismatch")
    require(summary.get("attempts") == expected_attempts, "summary attempt count mismatch")
    require(summary.get("all_attempts_valid") is True and summary.get("invalid_blocks") == [], "summary reports invalid blocks")
    require(summary.get("identity_unchanged") is True, "runner or binary changed")
    require(metadata.get("blocks") == args.expected_blocks and metadata.get("aa_blocks") == args.expected_aa_blocks, "metadata block count mismatch")

    primary = summary.get("pairs", {}).get("packed_over_padded", {})
    aa = summary.get("pairs", {}).get("padded_A_over_padded_B", {})
    require(primary.get("complete_blocks") == args.expected_blocks and primary.get("estimable") is True, "primary estimate incomplete")
    require(aa.get("complete_blocks") == args.expected_aa_blocks and aa.get("estimable") is True, "A/A estimate incomplete")

    binary_digest = (root / "binary.sha256").read_text().split()[0]
    require(binary_digest == metadata.get("binary_sha256"), "binary digest mismatch")
    result = {
        "status": "PASS",
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_archive_sha256,
        "binary_sha256": binary_digest,
        "attempts": expected_attempts,
        "primary_blocks": args.expected_blocks,
        "aa_blocks": args.expected_aa_blocks,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
