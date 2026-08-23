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
from probe_environment import PROBE_ENVIRONMENT
from self_test import ITERATIONS as SELF_TEST_ITERATIONS
from self_test import MODES as SELF_TEST_MODES
from self_test import SEED as SELF_TEST_SEED

RUNNER_RELATIVE = "topics/043-spectre-era-performance-tradeoffs/experiment/run_host.sh"
AUTHORIZED_TARGETS = {
    "xxl": ("x86_64",),
    "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com": ("aarch64", "arm64"),
}

REQUIRED = (
    "source-archive.tar.gz",
    "source-manifest-executing.sha256",
    "source-manifest-archive.sha256",
    "source-manifest.diff",
    "source-manifest-post-run.sha256",
    "source-manifest-post-run.diff",
    "host.txt",
    "correctness.txt",
    "build.txt",
    "probe.sha256",
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


def host_field(host: str, name: str, pattern: str = r"[^\n]+") -> str:
    """Return the unique ``name=value`` line's value from the host receipt."""

    values = re.findall(rf"^{re.escape(name)}=(.*)$", host, flags=re.MULTILINE)
    if len(values) != 1:
        raise SystemExit(f"host receipt must record exactly one {name}")
    if not re.fullmatch(pattern, values[0]):
        raise SystemExit(f"host receipt records an invalid {name}")
    return values[0]


def archive_manifest(archive: Path) -> bytes:
    """Re-derive the source manifest from the retained archive itself.

    Mirrors the runner's ``write_source_manifest``: per-file sha256sum lines
    over byte-sorted paths relative to the archive repository root, with the
    same ``target/`` and ``.git`` exclusions. The root is anchored on the
    unique Topic 43 runner path exactly as the runner locates it, so archives
    both with and without a ``git archive --prefix`` directory re-derive
    correctly.
    """

    entries = []
    with tarfile.open(archive, "r:gz") as tar:
        files = [member for member in tar.getmembers() if member.isfile()]
        anchors = [
            member.name
            for member in files
            if member.name == RUNNER_RELATIVE or member.name.endswith("/" + RUNNER_RELATIVE)
        ]
        if len(anchors) != 1:
            raise ValueError("source archive must contain exactly one Topic 43 host runner")
        prefix = anchors[0][: -len(RUNNER_RELATIVE)]
        for member in files:
            if not member.name.startswith(prefix):
                continue
            name = member.name[len(prefix):]
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.receipt_dir.resolve()
    output = args.output.resolve() if args.output else root / "receipt-validation.json"
    if output.exists():
        raise SystemExit("receipt validation output already exists")
    missing = [relative for relative in REQUIRED if not (root / relative).is_file()]
    if missing:
        raise SystemExit(f"missing receipts: {missing}")

    host = (root / "host.txt").read_text(encoding="utf-8")
    if any(
        marker not in host
        for marker in (
            "build_flags=-C target-cpu=native",
            "source_manifest_match=pass",
        )
    ):
        raise SystemExit("host receipt lacks build flags or source binding")
    # Re-apply the runner's target authorization offline: the label must be
    # an authorized target, the resolved and runtime hostnames must agree,
    # and the architecture must match the label.
    architecture = host_field(host, "architecture", r"\S+")
    target_label = host_field(host, "ssh_target_label")
    resolved_hostname = host_field(host, "ssh_resolved_hostname")
    runtime_hostname = host_field(host, "runtime_hostname")
    if runtime_hostname != resolved_hostname:
        raise SystemExit("runtime hostname differs from the resolved target")
    if architecture not in AUTHORIZED_TARGETS.get(target_label, ()):
        raise SystemExit("host receipt names an unauthorized target or architecture")
    archive_digest = hashlib.sha256((root / "source-archive.tar.gz").read_bytes()).hexdigest()
    for field in ("source_archive_sha256", "source_archive_verified_sha256"):
        if host_field(host, field, r"[0-9a-f]{64}") != archive_digest:
            raise SystemExit(f"retained source archive differs from {field}")
    # Bind the retained archive to the recorded commit exactly as the runner
    # does: git archive embeds the commit in the pax comment header.
    source_commit = host_field(host, "source_commit", r"[0-9a-f]{40}")
    with tarfile.open(root / "source-archive.tar.gz", "r:gz") as tar:
        embedded_commit = tar.pax_headers.get("comment", "")
    if embedded_commit != source_commit:
        raise SystemExit("retained archive does not embed the recorded source commit")
    # The runner appends each marker only after every command in the captured
    # log succeeds, so a truncated or failing log cannot be recertified.
    for name, marker in (
        ("correctness.txt", "correctness_status=pass"),
        ("build.txt", "build_status=pass"),
    ):
        lines = (root / name).read_text(encoding="utf-8").splitlines()
        if not lines or lines[-1] != marker:
            raise SystemExit(f"{name} lacks its terminal success marker")
    for name in ("source-manifest.diff", "source-manifest-post-run.diff"):
        if (root / name).read_bytes():
            raise SystemExit(f"{name} is not empty")
    # None of the retained manifests is trusted: the archive side re-derives
    # from archive bytes, and both executing-tree snapshots must equal it.
    retained_archive_manifest = (root / "source-manifest-archive.sha256").read_bytes()
    if retained_archive_manifest != archive_manifest(root / "source-archive.tar.gz"):
        raise SystemExit("archive manifest does not re-derive from the retained archive")
    for name in ("source-manifest-executing.sha256", "source-manifest-post-run.sha256"):
        if retained_archive_manifest != (root / name).read_bytes():
            raise SystemExit(f"{name} differs from the retained archive manifest")
    codegen_text = (root / "codegen/codegen-check.txt").read_text(encoding="utf-8")
    if "status=pass" not in codegen_text:
        raise SystemExit("codegen inspection did not pass")
    codegen_architectures = re.findall(r"^architecture=(\S+)$", codegen_text, flags=re.MULTILINE)
    if codegen_architectures != [architecture]:
        raise SystemExit("codegen receipt architecture differs from the host receipt")
    # The pass marker is itself a receipt; re-run the instruction checks over
    # the retained assembly so the marker cannot certify evidence the checks
    # would reject.
    try:
        barrier_order = check_codegen_dir(root / "codegen", architecture)
    except CodegenError as error:
        raise SystemExit(f"retained codegen evidence fails inspection: {error}") from error
    if f"barrier_order={barrier_order}" not in codegen_text:
        raise SystemExit("codegen receipt barrier order differs from the retained assembly")
    # The self-test status string is not evidence; re-check the retained
    # records for the fixed seed, iteration count, mode coverage, and
    # cross-mode checksum equivalence.
    self_test = read_json(root / "self-test.json")
    if self_test.get("status") != "pass" or self_test.get("schema") != "topic43-self-test-v1":
        raise SystemExit("self-test did not pass")
    if (
        self_test.get("iterations") != SELF_TEST_ITERATIONS
        or self_test.get("seed") != SELF_TEST_SEED
        or self_test.get("environment") != PROBE_ENVIRONMENT
    ):
        raise SystemExit("self-test inputs differ from the fixed protocol")
    records = self_test.get("records")
    if not isinstance(records, list) or len(records) != len(SELF_TEST_MODES):
        raise SystemExit("self-test must retain one record per mode")
    for mode, record in zip(SELF_TEST_MODES, records):
        if not isinstance(record, dict) or record.get("mode") != mode:
            raise SystemExit("self-test records do not cover the three modes in order")
        if (
            record.get("iterations") != SELF_TEST_ITERATIONS
            or record.get("seed") != SELF_TEST_SEED
        ):
            raise SystemExit(f"self-test {mode} record differs from the fixed inputs")
    for key in ("checksum", "warmup_checksum"):
        values = {record.get(key) for record in records}
        if len(values) != 1 or not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in values
        ):
            raise SystemExit(f"self-test {key} values are not equivalent across modes")

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

    # A/A controls and timing comparisons must exercise one workload. Each
    # phase validates these fields internally; this check binds the phases.
    combined_results = [row["result"] for row in aa_rows + timing_rows]
    for field in ("iterations", "checksum", "warmup_checksum"):
        if len({result[field] for result in combined_results}) != 1:
            raise SystemExit(f"process records disagree across phases on {field}")

    # Each analysis enforces one CPU within its own records; the receipt-level
    # boundary is one pinned CPU across the whole schedule, matching host.txt.
    cpus = {row.get("cpu") for row in aa_rows + timing_rows}
    if len(cpus) != 1:
        raise SystemExit("process records span more than one CPU")
    if int(host_field(host, "cpu", r"[0-9]+")) != cpus.pop():
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
