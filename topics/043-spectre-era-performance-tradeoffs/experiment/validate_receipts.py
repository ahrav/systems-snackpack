#!/usr/bin/env python3
"""Validate Topic 43 host, codegen, process, and analysis receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tarfile
from pathlib import Path

from analyze import analyze_aa, analyze_timing, load_rows
from codegen_checks import CodegenError, check_codegen_dir

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


def summaries_match(expected: object, actual: object) -> bool:
    """Structural equality with a float tolerance.

    Last-bit floating-point results of ``fmean``/``stdev`` differ across
    Python versions, so a retained summary must not be rejected for a 1-ulp
    disagreement with the recomputation. Everything except non-bool numerics
    still compares exactly, including dict key sets and list lengths.
    """

    numeric = (int, float)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, numeric) and isinstance(actual, numeric):
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(
            summaries_match(expected[key], actual[key]) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            summaries_match(one, other) for one, other in zip(expected, actual)
        )
    return type(expected) is type(actual) and expected == actual


def archive_manifest(archive: Path) -> bytes:
    """Re-derive the source manifest from the retained archive itself.

    Mirrors the runner's ``write_source_manifest``: per-file sha256sum lines
    over byte-sorted paths relative to the archive's top-level prefix, with
    the same ``target/`` and ``.git`` exclusions.
    """

    entries = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            name = member.name.split("/", 1)[1] if "/" in member.name else member.name
            if name.startswith(("target/", ".git/")) or name == ".git":
                continue
            handle = tar.extractfile(member)
            if handle is None:
                raise ValueError(f"unreadable archive member: {member.name}")
            entries.append((name, hashlib.sha256(handle.read()).hexdigest()))
    entries.sort(key=lambda entry: entry[0].encode("utf-8"))
    return "".join(f"{digest}  {name}\n" for name, digest in entries).encode("utf-8")


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
    # Neither retained manifest is trusted: the archive side re-derives from
    # the retained archive bytes, and the executing side must equal it.
    if (root / "source-manifest-archive.sha256").read_bytes() != archive_manifest(
        root / "source-archive.tar.gz"
    ):
        raise SystemExit("archive manifest does not re-derive from the retained archive")
    if (root / "source-manifest-archive.sha256").read_bytes() != (
        root / "source-manifest-executing.sha256"
    ).read_bytes():
        raise SystemExit("retained source manifests disagree")
    codegen_text = (root / "codegen/codegen-check.txt").read_text(encoding="utf-8")
    if "status=pass" not in codegen_text:
        raise SystemExit("codegen inspection did not pass")
    host_architectures = re.findall(r"^architecture=(\S+)$", host, flags=re.MULTILINE)
    codegen_architectures = re.findall(r"^architecture=(\S+)$", codegen_text, flags=re.MULTILINE)
    if len(host_architectures) != 1 or host_architectures != codegen_architectures:
        raise SystemExit("codegen receipt architecture differs from the host receipt")
    # The pass marker is itself a receipt; re-run the instruction checks over
    # the retained assembly so the marker cannot certify evidence the checks
    # would reject.
    try:
        barrier_order = check_codegen_dir(root / "codegen", host_architectures[0])
    except CodegenError as error:
        raise SystemExit(f"retained codegen evidence fails inspection: {error}") from error
    if f"barrier_order={barrier_order}" not in codegen_text:
        raise SystemExit("codegen receipt barrier order differs from the retained assembly")
    if read_json(root / "self-test.json").get("status") != "pass":
        raise SystemExit("self-test did not pass")

    aa_rows = load_rows(root / "aa-processes.jsonl")
    timing_rows = load_rows(root / "timing-processes.jsonl")
    aa_recomputed = analyze_aa(aa_rows)
    timing_recomputed = analyze_timing(timing_rows)
    if not summaries_match(read_json(root / "aa-summary.json"), aa_recomputed):
        raise SystemExit("A/A summary differs from retained process records")
    if not summaries_match(read_json(root / "timing-summary.json"), timing_recomputed):
        raise SystemExit("timing summary differs from retained process records")
    if aa_recomputed["status"] != "pass" or timing_recomputed["status"] != "pass":
        raise SystemExit("a fixed experiment gate failed")

    # Each analysis enforces one CPU within its own records; the receipt-level
    # boundary is one pinned CPU across the whole schedule, matching host.txt.
    cpus = {row.get("cpu") for row in aa_rows + timing_rows}
    if len(cpus) != 1:
        raise SystemExit("process records span more than one CPU")
    host_cpus = re.findall(r"^cpu=([0-9]+)$", host, flags=re.MULTILINE)
    if len(host_cpus) != 1 or int(host_cpus[0]) != cpus.pop():
        raise SystemExit("host receipt CPU differs from the process records")

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
