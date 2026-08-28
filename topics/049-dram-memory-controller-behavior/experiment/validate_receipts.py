#!/usr/bin/env python3
"""Standalone verifier for exact-source Topic 49 host receipts.

This file intentionally imports neither the acquisition runner nor the analysis
program.  It freezes the schedule, schema, formulas, and receipt file set a
second time so a shared implementation bug cannot make acquisition and receipt
validation agree by construction.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import re
import stat
import statistics
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn


ARM_TARGET = "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com"
TOPIC = "topics/049-dram-memory-controller-behavior"
RUNNER_RELATIVE = f"{TOPIC}/experiment/run_host.sh"
SOURCE_RELATIVES = (
    f"{TOPIC}/experiment/dram_bench.c",
    f"{TOPIC}/experiment/run_processes.py",
    f"{TOPIC}/experiment/analyze.py",
    f"{TOPIC}/experiment/validate_receipts.py",
    RUNNER_RELATIVE,
)
SYMBOLS = (
    "topic49_walk_dependent",
    "topic49_stream_scan",
    "topic49_page_prepare",
    "topic49_run_timed",
)
SMOKES = (
    ("idle-path-a", "idle", "smoke:idle:path-a"),
    ("loaded-path-b", "loaded", "smoke:loaded:path-b"),
    ("loaded-path-a", "loaded", "smoke:loaded:path-a"),
)
FROZEN_SCHEDULE = (
    ("primary", "primary-09", "ABBA"),
    ("primary", "primary-01", "BAAB"),
    ("aa", "aa-03", "ABBA"),
    ("primary", "primary-05", "ABBA"),
    ("aa", "aa-04", "BAAB"),
    ("primary", "primary-08", "BAAB"),
    ("primary", "primary-12", "ABBA"),
    ("primary", "primary-06", "BAAB"),
    ("primary", "primary-07", "BAAB"),
    ("primary", "primary-02", "ABBA"),
    ("primary", "primary-11", "BAAB"),
    ("aa", "aa-02", "ABBA"),
    ("primary", "primary-04", "ABBA"),
    ("primary", "primary-10", "ABBA"),
    ("aa", "aa-01", "BAAB"),
    ("primary", "primary-03", "BAAB"),
)
TREATMENT_SIGNS = {
    "ABBA": (-0.5, 0.5, 0.5, -0.5),
    "BAAB": (0.5, -0.5, -0.5, 0.5),
}
T_975 = {3: 3.182446305, 5: 2.570581836, 11: 2.200985160}
BASE_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PATH": "/bin:/usr/bin", "TZ": "UTC"}
RESULT_SCHEMA = "dram-memory-controller.v1"
NODE_BYTES = 64
CHUNK_BYTES = 256 * 1024
QUIET_NS = 1_000_000_000
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

RESULT_KEYS = {
    "schema", "label", "treatment", "probe_cpu", "worker_cpus",
    "probe_start_cpu", "probe_end_cpu", "worker_start_cpus", "worker_end_cpus",
    "large_mib", "worker_mib", "warmup_ms", "chunk_bytes", "correct", "affinity_ok",
    "prefetch_state", "madv_nohugepage", "page_size_bytes", "smaps_available",
    "large_kernel_page_kib", "large_mmu_page_kib", "large_anon_huge_kib",
    "large_thpeligible", "large_vmflag_nh", "small_kernel_page_kib",
    "small_anon_huge_kib", "small_vmflag_nh", "worker_anon_huge_kib",
    "worker_vmflag_nh_all", "startup_ns", "warmup_ns", "arm_wait_ns",
    "run_epoch_ns", "teardown_ns", "total_ns", "small_loads", "small_elapsed_ns",
    "small_ns_per_load", "small_checksum", "probe_loads", "probe_elapsed_ns",
    "probe_ns_per_load", "probe_bytes", "probe_checksum", "worker_chunks",
    "worker_chunks_by_thread", "worker_bytes", "worker_bytes_lower",
    "worker_bytes_upper_inclusive", "worker_gib_per_s_lower",
    "worker_gib_per_s_upper_inclusive", "worker_checksum",
    "process_large_window_minor_faults", "process_large_window_major_faults",
    "process_large_window_voluntary_context_switches",
    "process_large_window_involuntary_context_switches", "total_major_faults",
}
ATTEMPT_KEYS = {
    "schema", "sequence", "phase", "block", "template", "position", "label",
    "logical_path", "treatment", "bench_label", "binary", "binary_sha256_expected",
    "command", "environment", "timeout_seconds", "stdout_path", "stderr_path",
    "status_path", "started_utc", "binary_sha256_before", "started_monotonic_ns", "pid",
    "ended_monotonic_ns", "wall_ns", "returncode", "timed_out", "stdout", "stderr",
    "artifact_error", "binary_sha256_after", "result", "valid", "validation_error",
}
METADATA_KEYS = {
    "schema", "created_utc", "schedule_seed", "schedule", "primary_blocks", "aa_blocks",
    "periods_per_block", "quiet_interval_ns", "fixed_stopping", "analysis_unit",
    "primary_estimand", "binary_paths_distinct", "binary_sha256_equal", "binaries",
    "config", "base_environment",
}
STATIC_FILES = {
    "source-archive.tar.gz", "source-manifest-before.sha256",
    "source-manifest-after.sha256", "source-manifest.diff", "source-files.sha256",
    "host.txt", "build.txt", "binary.sha256", "binary.file.txt",
    "binary.build-id.txt", "binary.ldd.txt", "binary/path-a/dram_bench",
    "binary/path-b/dram_bench", "codegen/all.asm", "codegen/symbols.txt",
    *(f"codegen/{symbol}.asm" for symbol in SYMBOLS),
    *(f"smoke/{name}.{suffix}" for name, _, _ in SMOKES for suffix in ("stdout", "stderr", "status.json")),
    "campaign.txt", "experiment/metadata.json", "experiment/attempts.jsonl",
    "experiment/attempt-journal.jsonl", "experiment/summary.json",
}


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def is_int(value: object) -> bool:
    return type(value) is int


def is_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def same(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(same(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    fail(f"non-finite JSON number: {token}")


def strict_json(text: str) -> object:
    return json.loads(text, object_pairs_hook=reject_pairs, parse_constant=reject_constant)


def read_json(path: Path) -> dict[str, Any]:
    value = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path}: expected a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.endswith("\n") or not line.strip():
                fail(f"{path}:{line_number}: partial or blank JSONL record")
            value = strict_json(line)
            if not isinstance(value, dict):
                fail(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def strict_json_line(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        fail("process stdout must contain exactly one nonempty JSON line")
    value = strict_json(lines[0])
    if not isinstance(value, dict):
        fail("process stdout must be one JSON object")
    return value


def host_field(text: str, name: str, pattern: str = r"[^\n]+") -> str:
    matches = re.findall(rf"^{re.escape(name)}=(.*)$", text, flags=re.MULTILINE)
    if len(matches) != 1 or not re.fullmatch(pattern, matches[0]):
        fail(f"host receipt must contain one valid {name}")
    return matches[0]


def parse_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("\\"):
            fail(f"manifest uses an escaped filename: {path}")
        digest, separator, relative = line.partition("  ")
        candidate = PurePosixPath(relative)
        if (
            not separator or not HEX64.fullmatch(digest) or not relative
            or candidate.is_absolute() or ".." in candidate.parts or relative in result
        ):
            fail(f"malformed manifest line in {path}: {line}")
        result[relative] = digest
    if not result:
        fail(f"empty manifest: {path}")
    return result


def expected_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    sequence = 0
    for phase, block, template in FROZEN_SCHEDULE:
        for position, label in enumerate(template, 1):
            sequence += 1
            logical_path = "path-a" if label == "A" else "path-b"
            treatment = "loaded" if phase == "aa" else ("idle" if label == "A" else "loaded")
            specs.append({
                "sequence": sequence, "phase": phase, "block": block, "template": template,
                "position": position, "label": label, "logical_path": logical_path,
                "treatment": treatment,
                "bench_label": f"{phase}:{block}:{template}:position-{position}:{label}:{logical_path}",
            })
    return specs


def expected_files(*, sealed: bool) -> set[str]:
    files = set(STATIC_FILES)
    for spec in expected_specs():
        base = (
            f"{spec['sequence']:03d}-{spec['block']}-p{spec['position']}-{spec['label']}"
        )
        for suffix in ("stdout", "stderr", "status.json"):
            files.add(f"experiment/raw/{spec['logical_path']}/{base}.{suffix}")
    if sealed:
        files.update({"receipt-validation.json", "MANIFEST.sha256", "SEALED"})
    return files


def validate_tree(root: Path, *, sealed: bool) -> None:
    root_mode = root.lstat().st_mode
    if not stat.S_ISDIR(root_mode):
        fail("receipt root is not a directory")
    if sealed and root_mode & 0o222:
        fail("sealed receipt root remains writable")
    files: set[str] = set()
    directories: set[str] = set()
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    fail(f"receipt contains a symbolic link: {relative}")
                if stat.S_ISDIR(mode):
                    if sealed and mode & 0o222:
                        fail(f"sealed receipt directory remains writable: {relative}")
                    directories.add(relative)
                    stack.append(path)
                elif stat.S_ISREG(mode):
                    files.add(relative)
                    if sealed and mode & 0o222:
                        fail(f"sealed receipt remains writable: {relative}")
                else:
                    fail(f"receipt contains a special entry: {relative}")
    expected = expected_files(sealed=sealed)
    if files != expected:
        fail(f"receipt file set differs; missing={sorted(expected-files)}, unexpected={sorted(files-expected)}")
    expected_directories = {
        str(parent)
        for relative in expected
        for parent in PurePosixPath(relative).parents
        if str(parent) != "."
    }
    if directories != expected_directories:
        fail(
            "receipt directory set differs; "
            f"missing={sorted(expected_directories-directories)}, "
            f"unexpected={sorted(directories-expected_directories)}"
        )


def validate_result(
    result: dict[str, Any], *, label: str, treatment: str, probe_cpu: int,
    workers: tuple[int, ...], large_mib: int, worker_mib: int, warmup_ms: int,
) -> dict[str, Any]:
    if set(result) != RESULT_KEYS:
        fail("result key set differs from the frozen v1 schema")
    exact: dict[str, object] = {
        "schema": RESULT_SCHEMA, "label": label, "treatment": treatment,
        "probe_cpu": probe_cpu, "worker_cpus": list(workers), "probe_start_cpu": probe_cpu,
        "probe_end_cpu": probe_cpu, "worker_start_cpus": list(workers),
        "worker_end_cpus": list(workers), "large_mib": large_mib,
        "worker_mib": worker_mib, "warmup_ms": warmup_ms, "chunk_bytes": CHUNK_BYTES,
        "correct": True, "affinity_ok": True, "madv_nohugepage": True,
        "prefetch_state": "production-default-unmodified",
    }
    for key, value in exact.items():
        if type(result.get(key)) is not type(value) or result.get(key) != value:
            fail(f"result field {key} differs from the fixed invocation")
    if type(result["smaps_available"]) is not bool:
        fail("smaps_available must be boolean")
    for key in ("large_vmflag_nh", "small_vmflag_nh", "worker_vmflag_nh_all"):
        if type(result[key]) is not bool:
            fail(f"{key} must be boolean")
    integer_fields = (
        "large_kernel_page_kib", "large_mmu_page_kib", "large_anon_huge_kib",
        "small_kernel_page_kib", "small_anon_huge_kib", "worker_anon_huge_kib",
        "startup_ns", "warmup_ns", "arm_wait_ns", "run_epoch_ns", "teardown_ns",
        "total_ns", "small_loads", "small_elapsed_ns", "small_checksum", "probe_loads",
        "probe_elapsed_ns", "probe_bytes", "probe_checksum", "worker_chunks",
        "worker_bytes", "worker_bytes_lower", "worker_bytes_upper_inclusive",
        "worker_checksum", "process_large_window_minor_faults",
        "process_large_window_major_faults", "process_large_window_voluntary_context_switches",
        "process_large_window_involuntary_context_switches", "total_major_faults",
    )
    for key in integer_fields:
        if not is_int(result[key]) or result[key] < 0:
            fail(f"{key} must be a nonnegative integer")
    if not is_int(result["page_size_bytes"]) or result["page_size_bytes"] <= 0:
        fail("page_size_bytes must be positive")
    if not is_int(result["large_thpeligible"]) or result["large_thpeligible"] < -1:
        fail("large_thpeligible must be -1 or nonnegative")
    for key in ("small_loads", "small_elapsed_ns", "probe_loads", "probe_elapsed_ns", "probe_bytes"):
        if result[key] <= 0:
            fail(f"{key} must be positive")
    for key in (
        "small_ns_per_load", "probe_ns_per_load", "worker_gib_per_s_lower",
        "worker_gib_per_s_upper_inclusive",
    ):
        if not is_number(result[key]) or result[key] < 0:
            fail(f"{key} must be finite and nonnegative")
    chunks = result["worker_chunks_by_thread"]
    if (
        not isinstance(chunks, list) or len(chunks) != len(workers)
        or any(not is_int(value) or value < 0 for value in chunks)
    ):
        fail("worker_chunks_by_thread must contain one nonnegative integer per worker")
    if result["total_ns"] != sum(result[key] for key in (
        "startup_ns", "warmup_ns", "arm_wait_ns", "run_epoch_ns", "teardown_ns"
    )):
        fail("total_ns does not equal the phase sum")
    if result["run_epoch_ns"] <= 0:
        fail("run_epoch_ns must be positive")
    if not math.isclose(result["small_ns_per_load"], result["small_elapsed_ns"] / result["small_loads"], rel_tol=2e-9, abs_tol=1e-9):
        fail("small_ns_per_load does not rederive")
    if not math.isclose(result["probe_ns_per_load"], result["probe_elapsed_ns"] / result["probe_loads"], rel_tol=2e-9, abs_tol=1e-9):
        fail("probe_ns_per_load does not rederive")
    expected_loads = large_mib * 1024 * 1024 // NODE_BYTES * 4
    if result["probe_loads"] != expected_loads or result["probe_bytes"] != expected_loads * NODE_BYTES:
        fail("probe load or byte count differs from the frozen traversal")
    if result["worker_chunks"] != sum(chunks):
        fail("worker_chunks does not equal its per-thread sum")
    if result["worker_bytes"] != result["worker_bytes_lower"] or result["worker_bytes"] != result["worker_chunks"] * CHUNK_BYTES:
        fail("worker lower byte bound does not equal published complete chunks")
    if treatment == "idle":
        if any(chunks) or result["worker_bytes_lower"] != 0 or result["worker_bytes_upper_inclusive"] != 0:
            fail("idle worker activity and byte bounds must be exact zero")
    else:
        if any(value < 1 for value in chunks):
            fail("loaded treatment lacks one completed chunk from every worker")
        expected_upper = result["worker_bytes_lower"] + len(workers) * CHUNK_BYTES
        if result["worker_bytes_upper_inclusive"] != expected_upper:
            fail("loaded worker inclusive upper byte bound changed")
    gib = float(1024**3)
    lower = result["worker_bytes_lower"] * 1e9 / result["run_epoch_ns"] / gib
    upper = result["worker_bytes_upper_inclusive"] * 1e9 / result["run_epoch_ns"] / gib
    if not math.isclose(result["worker_gib_per_s_lower"], lower, rel_tol=2e-9, abs_tol=1e-9):
        fail("worker lower rate does not rederive")
    if not math.isclose(result["worker_gib_per_s_upper_inclusive"], upper, rel_tol=2e-9, abs_tol=1e-9):
        fail("worker inclusive upper rate does not rederive")
    if treatment == "idle" and (lower != 0.0 or upper != 0.0):
        fail("idle rate bounds must be exact zero")
    if result["process_large_window_major_faults"] != 0 or result["total_major_faults"] != 0:
        fail("process incurred a major fault")
    if result["smaps_available"]:
        if result["large_kernel_page_kib"] <= 0 or result["large_mmu_page_kib"] <= 0 or result["small_kernel_page_kib"] <= 0:
            fail("smaps lacks mapping page-size evidence")
        if result["large_anon_huge_kib"] or result["small_anon_huge_kib"] or result["worker_anon_huge_kib"]:
            fail("a mapping used anonymous huge pages")
        if not result["large_vmflag_nh"] or not result["small_vmflag_nh"] or not result["worker_vmflag_nh_all"]:
            fail("a mapping lacks the no-hugepage flag")
    return result


def validate_metadata(metadata: dict[str, Any]) -> tuple[dict[str, Any], tuple[int, ...]]:
    if set(metadata) != METADATA_KEYS or metadata.get("schema") != "topic49-campaign-metadata.v1":
        fail("campaign metadata schema or key set changed")
    if not isinstance(metadata.get("created_utc"), str) or not UTC.fullmatch(metadata["created_utc"]):
        fail("campaign creation time is malformed")
    frozen_schedule = [
        {"phase": phase, "block": block, "template": template}
        for phase, block, template in FROZEN_SCHEDULE
    ]
    fixed: dict[str, object] = {
        "schedule_seed": 20260828, "schedule": frozen_schedule, "primary_blocks": 12,
        "aa_blocks": 4, "periods_per_block": 4, "quiet_interval_ns": QUIET_NS,
        "fixed_stopping": "run every predeclared period once; do not replace or peek",
        "analysis_unit": "one complete four-process block contrast",
        "primary_estimand": "geometric loaded/idle ratio of large-chain nanoseconds per load",
        "binary_paths_distinct": True, "binary_sha256_equal": True,
        "base_environment": BASE_ENVIRONMENT,
    }
    for key, value in fixed.items():
        if not same(metadata.get(key), value):
            fail(f"campaign metadata field {key} changed")
    binaries = metadata.get("binaries")
    if not isinstance(binaries, dict) or set(binaries) != {"path-a", "path-b"}:
        fail("campaign metadata must bind two logical binary paths")
    paths: set[str] = set()
    digests: set[str] = set()
    for name in ("path-a", "path-b"):
        item = binaries[name]
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            fail(f"malformed {name} binary metadata")
        if not isinstance(item["path"], str) or not os.path.isabs(item["path"]):
            fail(f"{name} binary path is not absolute")
        if not isinstance(item["sha256"], str) or not HEX64.fullmatch(item["sha256"]):
            fail(f"{name} binary digest is malformed")
        paths.add(item["path"])
        digests.add(item["sha256"])
    if len(paths) != 2 or len(digests) != 1:
        fail("A/A requires two distinct paths containing identical bytes")
    config = metadata.get("config")
    if not isinstance(config, dict) or set(config) != {
        "probe_cpu", "worker_cpus", "large_mib", "worker_mib", "warmup_ms", "timeout_seconds"
    }:
        fail("campaign config key set changed")
    probe = config.get("probe_cpu")
    workers_value = config.get("worker_cpus")
    if not is_int(probe) or probe < 0:
        fail("probe CPU is invalid")
    if (
        not isinstance(workers_value, list) or len(workers_value) != 8
        or any(not is_int(cpu) or cpu < 0 for cpu in workers_value)
        or len(set(workers_value)) != 8 or probe in workers_value
    ):
        fail("worker CPU list is invalid")
    frozen_config: dict[str, object] = {
        "large_mib": 512, "worker_mib": 128, "warmup_ms": 750, "timeout_seconds": 300.0
    }
    for key, value in frozen_config.items():
        if type(config.get(key)) is not type(value) or config.get(key) != value:
            fail(f"campaign config {key} differs from the frozen value")
    return config, tuple(workers_value)


def validate_campaign_binary_identity(metadata: dict[str, Any], retained_digest: str) -> None:
    if not HEX64.fullmatch(retained_digest):
        fail("retained linked-image digest is malformed")
    for logical_path in ("path-a", "path-b"):
        if metadata["binaries"][logical_path]["sha256"] != retained_digest:
            fail(f"campaign metadata {logical_path} digest differs from the retained linked image")


def expected_command(binary: str, treatment: str, config: dict[str, Any]) -> list[str]:
    return [
        binary, "--treatment", treatment, "--probe-cpu", str(config["probe_cpu"]),
        "--worker-cpus", ",".join(map(str, config["worker_cpus"])),
        "--large-mib", "512", "--worker-mib", "128", "--warmup-ms", "750",
    ]


def validate_raw_file(root: Path, relative: object, expected: str) -> Path:
    if not isinstance(relative, str):
        fail("raw receipt path must be text")
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        fail("raw receipt path escapes the receipt")
    path = root / relative
    if path.read_text(encoding="utf-8") != expected:
        fail(f"raw receipt differs from retained attempt: {relative}")
    return path


def validate_attempts(
    root: Path, metadata: dict[str, Any], config: dict[str, Any], workers: tuple[int, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = read_jsonl(root / "experiment/attempts.jsonl")
    specs = expected_specs()
    if len(rows) != 64:
        fail(f"fixed horizon needs 64 attempts, found {len(rows)}")
    binaries = metadata["binaries"]
    results: list[dict[str, Any]] = []
    pids: set[int] = set()
    previous_end: int | None = None
    for row, spec in zip(rows, specs):
        if set(row) != ATTEMPT_KEYS or row.get("schema") != "topic49-attempt.v1":
            fail(f"attempt {spec['sequence']} schema or key set changed")
        for key in (
            "sequence", "phase", "block", "template", "position", "label",
            "logical_path", "treatment", "bench_label",
        ):
            if type(row.get(key)) is not type(spec[key]) or row.get(key) != spec[key]:
                fail(f"attempt {spec['sequence']} field {key} differs from the frozen schedule")
        binary_item = binaries[spec["logical_path"]]
        binary = binary_item["path"]
        digest = binary_item["sha256"]
        if row.get("binary") != binary or row.get("binary_sha256_expected") != digest:
            fail(f"attempt {spec['sequence']} selected the wrong binary")
        if row.get("binary_sha256_before") != digest or row.get("binary_sha256_after") != digest:
            fail(f"attempt {spec['sequence']} binary identity changed")
        if row.get("command") != expected_command(binary, spec["treatment"], config):
            fail(f"attempt {spec['sequence']} command changed")
        environment = dict(BASE_ENVIRONMENT)
        environment["BENCH_LABEL"] = spec["bench_label"]
        if row.get("environment") != environment or row.get("timeout_seconds") != 300.0:
            fail(f"attempt {spec['sequence']} environment or timeout changed")
        if (
            row.get("returncode") != 0 or row.get("timed_out") is not False
            or row.get("artifact_error") is not None or row.get("validation_error") is not None
            or row.get("valid") is not True
        ):
            fail(f"attempt {spec['sequence']} was not a valid completed attempt")
        if not isinstance(row.get("started_utc"), str) or not UTC.fullmatch(row["started_utc"]):
            fail(f"attempt {spec['sequence']} start time is malformed")
        pid = row.get("pid")
        if not is_int(pid) or pid <= 0 or pid in pids:
            fail(f"attempt {spec['sequence']} does not evidence a fresh PID")
        pids.add(pid)
        started = row.get("started_monotonic_ns")
        ended = row.get("ended_monotonic_ns")
        wall = row.get("wall_ns")
        if not all(is_int(value) and value >= 0 for value in (started, ended, wall)):
            fail(f"attempt {spec['sequence']} monotonic timing is malformed")
        if ended < started or wall != ended - started:
            fail(f"attempt {spec['sequence']} wall time does not rederive")
        if previous_end is not None and started - previous_end < QUIET_NS:
            fail(f"attempt {spec['sequence']} violates the one-second quiet interval")
        previous_end = ended
        stdout = row.get("stdout")
        stderr = row.get("stderr")
        if not isinstance(stdout, str) or not isinstance(stderr, str):
            fail(f"attempt {spec['sequence']} output is not text")
        base = f"{spec['sequence']:03d}-{spec['block']}-p{spec['position']}-{spec['label']}"
        expected_paths = {
            "stdout_path": f"raw/{spec['logical_path']}/{base}.stdout",
            "stderr_path": f"raw/{spec['logical_path']}/{base}.stderr",
            "status_path": f"raw/{spec['logical_path']}/{base}.status.json",
        }
        for key, expected_relative in expected_paths.items():
            if row.get(key) != expected_relative:
                fail(f"attempt {spec['sequence']} {key} is not the deterministic path")
        stdout_path = validate_raw_file(root / "experiment", row["stdout_path"], stdout)
        validate_raw_file(root / "experiment", row["stderr_path"], stderr)
        status = read_json(root / "experiment" / row["status_path"])
        if set(status) != {"pid", "returncode", "timed_out", "wall_ns"}:
            fail(f"attempt {spec['sequence']} status key set changed")
        for key in status:
            if type(status[key]) is not type(row[key]) or status[key] != row[key]:
                fail(f"attempt {spec['sequence']} status differs on {key}")
        parsed = strict_json_line(stdout_path.read_text(encoding="utf-8"))
        if not same(parsed, row.get("result")):
            fail(f"attempt {spec['sequence']} parsed result differs from raw stdout")
        results.append(validate_result(
            parsed, label=spec["bench_label"], treatment=spec["treatment"],
            probe_cpu=config["probe_cpu"], workers=workers, large_mib=512,
            worker_mib=128, warmup_ms=750,
        ))
    for key in ("probe_loads", "probe_bytes", "probe_checksum", "small_loads", "small_checksum", "prefetch_state"):
        if len({json.dumps(result[key], sort_keys=True) for result in results}) != 1:
            fail(f"fresh processes disagree on fixed field {key}")
    return rows, results


def validate_journal(root: Path, rows: list[dict[str, Any]]) -> None:
    journal = read_jsonl(root / "experiment/attempt-journal.jsonl")
    specs = expected_specs()
    if len(journal) != 128:
        fail("complete campaign must contain exactly 128 start/end journal events")
    prior_monotonic = -1
    for index, (spec, row) in enumerate(zip(specs, rows)):
        start = journal[index * 2]
        end = journal[index * 2 + 1]
        if set(start) != {
            "schema", "event", "sequence", "phase", "block", "template", "position",
            "label", "logical_path", "treatment", "journaled_utc", "journaled_monotonic_ns",
        }:
            fail(f"attempt {spec['sequence']} start journal key set changed")
        if start.get("schema") != "topic49-attempt-journal.v1" or start.get("event") != "attempt-start":
            fail(f"attempt {spec['sequence']} lacks its pre-launch journal event")
        for key in ("sequence", "phase", "block", "template", "position", "label", "logical_path", "treatment"):
            if type(start.get(key)) is not type(spec[key]) or start.get(key) != spec[key]:
                fail(f"attempt {spec['sequence']} start journal field {key} changed")
        if set(end) != {
            "schema", "event", "sequence", "outcome", "pid", "journaled_utc", "journaled_monotonic_ns",
        }:
            fail(f"attempt {spec['sequence']} end journal key set changed")
        if (
            end.get("schema") != "topic49-attempt-journal.v1" or end.get("event") != "attempt-end"
            or end.get("sequence") != spec["sequence"] or end.get("outcome") != "valid"
            or end.get("pid") != row["pid"]
        ):
            fail(f"attempt {spec['sequence']} end journal is not a valid finalization")
        for event in (start, end):
            if not isinstance(event.get("journaled_utc"), str) or not UTC.fullmatch(event["journaled_utc"]):
                fail(f"attempt {spec['sequence']} journal UTC time is malformed")
            monotonic = event.get("journaled_monotonic_ns")
            if not is_int(monotonic) or monotonic < 0 or monotonic < prior_monotonic:
                fail(f"attempt {spec['sequence']} journal monotonic order changed")
            prior_monotonic = monotonic
        if start["journaled_monotonic_ns"] > row["started_monotonic_ns"]:
            fail(f"attempt {spec['sequence']} was launched before its start journal")
        if end["journaled_monotonic_ns"] < row["ended_monotonic_ns"]:
            fail(f"attempt {spec['sequence']} ended after its final journal event")


def descriptive(values: list[float]) -> dict[str, Any]:
    return {"count": len(values), "median": statistics.median(values), "minimum": min(values), "maximum": max(values)}


def contrast(template: str, values: list[float]) -> float:
    if template not in TREATMENT_SIGNS or len(values) != 4 or any(value <= 0 or not math.isfinite(value) for value in values):
        fail("block contrast input differs from the frozen positive four-period formula")
    return sum(sign * math.log(value) for sign, value in zip(TREATMENT_SIGNS[template], values))


def contrast_summary(values: list[float], *, interval: bool) -> dict[str, Any]:
    if len(values) < 2:
        fail("contrast summary requires at least two blocks")
    mean = statistics.fmean(values)
    sample_sd = statistics.stdev(values)
    ratios = [math.exp(value) for value in values]
    result: dict[str, Any] = {
        "blocks": len(values), "mean_log_contrast": mean, "geometric_mean_ratio": math.exp(mean),
        "sample_sd_log_contrast": sample_sd, "block_ratio_median": statistics.median(ratios),
        "block_ratio_minimum": min(ratios), "block_ratio_maximum": max(ratios),
    }
    if interval:
        df = len(values) - 1
        if df not in T_975:
            fail(f"no frozen t critical for {df} degrees of freedom")
        standard_error = sample_sd / math.sqrt(len(values))
        half = T_975[df] * standard_error
        result.update({
            "degrees_of_freedom": df, "standard_error_log_contrast": standard_error,
            "t_critical_975": T_975[df], "ci95_ratio_low": math.exp(mean - half),
            "ci95_ratio_high": math.exp(mean + half),
            "interval_scope": (
                "between-block variation in paired fresh-process log large-chain "
                "nanoseconds-per-load ratios on this exact host, binary, and run window"
            ),
        })
    return result


def phase_summary(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    by_template: dict[str, Any] = {}
    for template in ("ABBA", "BAAB"):
        selected = [block for block in blocks if block["template"] == template]
        by_template[template] = {
            "probe": contrast_summary([block["probe_log_contrast"] for block in selected], interval=False),
            "small_control": contrast_summary([block["small_log_contrast"] for block in selected], interval=False),
        }
    return {
        "probe": contrast_summary([block["probe_log_contrast"] for block in blocks], interval=True),
        "small_control": contrast_summary([block["small_log_contrast"] for block in blocks], interval=True),
        "by_template": by_template,
    }


def recompute_summary(
    metadata: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = collections.defaultdict(list)
    for row, result in zip(rows, results):
        grouped[row["block"]].append((row, result))
    blocks: list[dict[str, Any]] = []
    for phase, block_name, template in FROZEN_SCHEDULE:
        items = sorted(grouped[block_name], key=lambda item: item[0]["position"])
        if len(items) != 4 or [row["position"] for row, _ in items] != [1, 2, 3, 4]:
            fail(f"block {block_name} is incomplete")
        probe = [result["probe_elapsed_ns"] / result["probe_loads"] for _, result in items]
        small = [result["small_elapsed_ns"] / result["small_loads"] for _, result in items]
        probe_contrast = contrast(template, probe)
        small_contrast = contrast(template, small)
        blocks.append({
            "phase": phase, "block": block_name, "template": template,
            "probe_ns_per_load_by_position": probe,
            "small_ns_per_load_by_position": small,
            "probe_log_contrast": probe_contrast, "probe_ratio": math.exp(probe_contrast),
            "small_log_contrast": small_contrast, "small_ratio": math.exp(small_contrast),
            "worker_bytes_lower_by_position": [result["worker_bytes_lower"] for _, result in items],
            "worker_bytes_upper_inclusive_by_position": [
                result["worker_bytes_upper_inclusive"] for _, result in items
            ],
        })
    primary_blocks = [block for block in blocks if block["phase"] == "primary"]
    aa_blocks = [block for block in blocks if block["phase"] == "aa"]
    primary_results = [result for row, result in zip(rows, results) if row["phase"] == "primary"]
    idle = [result for result in primary_results if result["treatment"] == "idle"]
    loaded = [result for result in primary_results if result["treatment"] == "loaded"]
    if len(primary_blocks) != 12 or len(aa_blocks) != 4 or len(idle) != 24 or len(loaded) != 24:
        fail("frozen phase or treatment counts changed")
    per_treatment: dict[str, Any] = {}
    for name, selected in (("idle", idle), ("loaded", loaded)):
        per_treatment[name] = {
            "processes": len(selected),
            "probe_ns_per_load": descriptive([item["probe_elapsed_ns"] / item["probe_loads"] for item in selected]),
            "small_ns_per_load": descriptive([item["small_elapsed_ns"] / item["small_loads"] for item in selected]),
            "run_epoch_ms": descriptive([item["run_epoch_ns"] / 1_000_000 for item in selected]),
        }
    worker_bounds = {
        "processes": len(loaded),
        "lower_gib_per_s": descriptive([item["worker_gib_per_s_lower"] for item in loaded]),
        "upper_inclusive_gib_per_s": descriptive([item["worker_gib_per_s_upper_inclusive"] for item in loaded]),
        "uncounted_tail_bytes_at_most": len(config["worker_cpus"]) * CHUNK_BYTES,
        "boundary": "application useful source bytes, not cache-line, fabric, or DRAM traffic",
    }
    return {
        "schema": "topic49-analysis.v1", "status": "pass", "schedule_seed": 20260828,
        "fixed_horizon": {"primary_blocks": 12, "aa_blocks": 4, "processes": 64, "replacement_attempts": 0},
        "primary": {
            "comparison": "loaded/idle", **phase_summary(primary_blocks),
            "per_treatment": per_treatment, "worker_useful_bandwidth_bounds": worker_bounds,
        },
        "aa": {
            "comparison": "loaded-path-b/loaded-path-a", "mechanical_integrity": "pass",
            "null_calibration_claim": "none; four blocks do not estimate a false-positive rate",
            **phase_summary(aa_blocks),
        },
        "blocks": blocks,
        "measured_boundary": (
            "elapsed time, application useful bytes, process counters, affinity canaries, "
            "and mapping observations for one exact host run"
        ),
        "inference_boundary": (
            "no direct claim about DRAM-only latency, controller saturation, bank conflicts, "
            "row hits, refresh, channel mapping, or processor-family behavior"
        ),
    }


def archive_manifest(archive_path: Path, expected_commit: str) -> dict[str, str]:
    expected_prefix = f"systems-snackpack-{expected_commit}/"
    topic_prefix = expected_prefix + TOPIC + "/"
    allowed_ancestor_dirs = {
        expected_prefix.rstrip("/"), expected_prefix + "topics", topic_prefix.rstrip("/"),
    }
    required = {expected_prefix + relative for relative in SOURCE_RELATIVES}
    result: dict[str, str] = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        embedded = archive.pax_headers.get("comment")
        if embedded is None:
            embedded = next((m.pax_headers.get("comment") for m in members if m.pax_headers.get("comment")), None)
        if embedded != expected_commit:
            fail("source archive commit differs from the external expected commit")
        seen_names: set[str] = set()
        normalized: set[str] = set()
        files: dict[str, tarfile.TarInfo] = {}
        total_size = 0
        if len(members) > 256:
            fail("source archive exceeds 256 total members")
        for member in members:
            path = PurePosixPath(member.name)
            normalized_name = str(path)
            if (
                member.name in seen_names or normalized_name in normalized or path.is_absolute()
                or ".." in path.parts or not (member.isfile() or member.isdir())
            ):
                fail(f"unsafe or duplicate archive member: {member.name}")
            if member.name != expected_prefix.rstrip("/") and not member.name.startswith(expected_prefix):
                fail(f"archive member escaped its unique prefix: {member.name}")
            if member.isfile() and not member.name.startswith(topic_prefix):
                fail(f"archive is not path-limited to Topic 49: {member.name}")
            if member.isdir() and (
                member.name.rstrip("/") not in allowed_ancestor_dirs
                and not member.name.startswith(topic_prefix)
            ):
                fail(f"archive directory escaped the Topic 49 ancestor tree: {member.name}")
            seen_names.add(member.name)
            normalized.add(normalized_name)
            if member.isfile():
                files[member.name] = member
                total_size += member.size
        if not required.issubset(files):
            fail(f"archive lacks required experiment files: {sorted(required-set(files))}")
        if len(files) > 128 or total_size > 16 * 1024 * 1024:
            fail("source archive exceeds the frozen file-count or uncompressed-size cap")
        for name, member in files.items():
            source = archive.extractfile(member)
            if source is None:
                fail(f"unreadable source archive member: {name}")
            digest = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
            result[name[len(expected_prefix):]] = digest.hexdigest()
    return result


def host_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.fullmatch(r"\[([^]]+)\]", line)
        if match:
            current = match.group(1)
            if current in sections:
                fail(f"host receipt repeats section [{current}]")
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def require_host_section(sections: dict[str, str], name: str) -> str:
    body = sections.get(name)
    if body is None or not body.strip():
        fail(f"mandatory host section [{name}] is absent or empty")
    if re.search(r"(?:^|\n)(?:COMMAND_FAILED|command_status|unavailable)=", body):
        fail(f"mandatory host section [{name}] records an unavailable or failed command")
    return body


def parse_cpu_list(value: str) -> set[int]:
    cpus: set[int] = set()
    for item in value.split(","):
        if re.fullmatch(r"[0-9]+", item):
            cpus.add(int(item))
        elif re.fullmatch(r"[0-9]+-[0-9]+", item):
            first, last = (int(part) for part in item.split("-"))
            if last < first:
                fail(f"descending CPU range: {item}")
            cpus.update(range(first, last + 1))
        else:
            fail(f"malformed CPU list: {value}")
    return cpus


def validate_host(
    root: Path, *, target_label: str, hostname: str, architecture: str,
    expected_commit: str, expected_archive_sha256: str,
) -> tuple[str, int, tuple[int, ...]]:
    host = (root / "host.txt").read_text(encoding="utf-8")
    exact = {
        "source_commit": expected_commit, "source_archive_sha256": expected_archive_sha256,
        "ssh_target_label": target_label, "expected_hostname": hostname,
        "runtime_hostname": hostname, "expected_architecture": architecture,
        "architecture": architecture, "large_mib": "512", "worker_mib": "128",
        "warmup_ms": "750", "primary_blocks": "12", "aa_blocks": "4",
        "schedule_seed": "20260828", "quiet_interval_seconds": "1",
        "build_flags": "-O3 -g -std=gnu11 -Wall -Wextra -Werror -march=native -pthread",
        "distinct_physical_cores": "true", "single_numa_node": "true",
    }
    for key, value in exact.items():
        if host_field(host, key) != value:
            fail(f"host field {key} differs from external or frozen evidence")
    if target_label == "xxl":
        if architecture != "x86_64" or hostname == "xxl":
            fail("xxl must be externally resolved to a concrete x86-64 hostname")
    elif target_label == ARM_TARGET:
        if hostname != ARM_TARGET or architecture != "aarch64":
            fail("literal Arm target identity changed")
    else:
        fail("receipt names an unauthorized target")
    kernel = host_field(host, "kernel_release")
    if not kernel.strip():
        fail("kernel release evidence is empty")
    available = int(host_field(host, "available_cpu_count", r"[0-9]+"))
    if available <= 0:
        fail("available CPU count must be positive")
    cpu_model_source = host_field(host, "cpu_model_source", r"(?:lscpu-model-name|sysfs-midr-el1)")
    cpu_model = host_field(host, "cpu_model")
    probe = int(host_field(host, "probe_cpu", r"[0-9]+"))
    workers = tuple(int(value) for value in host_field(host, "worker_cpus", r"[0-9]+(?:,[0-9]+){7}").split(","))
    if len(set((probe, *workers))) != 9:
        fail("host evidence does not name nine distinct logical CPUs")
    locations: dict[int, tuple[int, int, int]] = {}
    sibling_sets: dict[int, set[int]] = {}
    for cpu in (probe, *workers):
        package = int(host_field(host, f"cpu_{cpu}_package_id", r"[0-9]+"))
        core = int(host_field(host, f"cpu_{cpu}_core_id", r"[0-9]+"))
        node = int(host_field(host, f"cpu_{cpu}_numa_node", r"[0-9]+"))
        siblings = parse_cpu_list(host_field(host, f"cpu_{cpu}_thread_siblings", r"[0-9,-]+"))
        if cpu not in siblings:
            fail(f"cpu{cpu} is absent from its recorded sibling set")
        locations[cpu] = (node, package, core)
        sibling_sets[cpu] = siblings
    selected_node = int(host_field(host, "selected_numa_node", r"[0-9]+"))
    if len({(package, core) for _, package, core in locations.values()}) != 9:
        fail("selected CPUs do not recompute to distinct physical cores")
    if {node for node, _, _ in locations.values()} != {selected_node}:
        fail("selected CPUs do not recompute to the declared single NUMA node")
    selected_cpus = (probe, *workers)
    for index, cpu in enumerate(selected_cpus):
        for other in selected_cpus[index + 1:]:
            if sibling_sets[cpu] & sibling_sets[other]:
                fail(f"selected cpu{cpu} and cpu{other} have overlapping sibling sets")
    allowed = parse_cpu_list(host_field(host, "allowed_affinity", r"[0-9,-]+"))
    if not set((probe, *workers)).issubset(allowed) or len(allowed) != available:
        fail("selected or available CPU count differs from the affinity evidence")

    sections = host_sections(host)
    mandatory = (
        "uname", "lscpu", "cpu-model-raw", "lscpu-topology", "lscpu-caches", "numa-online", "cpu-online",
        "thp-enabled", "process-cgroup", "command-v-gcc", "gcc-version", "gcc-verbose",
        "python-version", "gcc-native-target", "objdump", "readelf", "perf-version",
        "perf-pmus", "sysfs-pmus", "loadavg", "uptime", "selected-cache-topology",
    )
    bodies = {name: require_host_section(sections, name) for name in mandatory}
    lscpu = bodies["lscpu"]
    if not re.search(rf"^Architecture:\s*{re.escape(architecture)}$", lscpu, flags=re.MULTILINE):
        fail("lscpu architecture differs from the runtime architecture")
    cpu_count_match = re.search(r"^CPU\(s\):\s*([0-9]+)$", lscpu, flags=re.MULTILINE)
    if not cpu_count_match or int(cpu_count_match.group(1)) < available:
        fail("lscpu CPU count is absent or smaller than the allowed CPU count")
    if bodies["cpu-model-raw"] != cpu_model:
        fail("flat CPU model differs from its independently captured raw value")
    model_match = re.search(r"^Model name:\s*(\S.*)$", lscpu, flags=re.MULTILINE)
    if architecture == "x86_64":
        if cpu_model_source != "lscpu-model-name" or not model_match or model_match.group(1) != cpu_model:
            fail("x86-64 CPU model does not rederive from lscpu")
    elif (
        cpu_model_source != "sysfs-midr-el1"
        or not re.fullmatch(r"0x[0-9a-fA-F]+", cpu_model)
    ):
        fail("AArch64 CPU model evidence is not a concrete sysfs MIDR_EL1 value")

    topology_rows: dict[int, tuple[int, int, int]] = {}
    for line in bodies["lscpu-topology"].splitlines():
        match = re.match(r"^\s*([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+", line)
        if match:
            cpu, node, package, core = (int(value) for value in match.groups())
            if cpu in topology_rows:
                fail(f"lscpu topology repeats cpu{cpu}")
            topology_rows[cpu] = (node, package, core)
    for cpu, expected_location in locations.items():
        if topology_rows.get(cpu) != expected_location:
            fail(f"lscpu topology differs from sysfs-derived fields for cpu{cpu}")
        node, package, core = expected_location
        for sibling in sibling_sets[cpu]:
            sibling_location = topology_rows.get(sibling)
            if sibling_location is not None and sibling_location[1:] != (package, core):
                fail(f"cpu{cpu} sibling set conflicts with lscpu package/core topology")

    online_cpus = parse_cpu_list(bodies["cpu-online"])
    online_nodes = parse_cpu_list(bodies["numa-online"])
    if not set(selected_cpus).issubset(online_cpus):
        fail("a selected CPU is absent from the online CPU range")
    if selected_node not in online_nodes:
        fail("the selected NUMA node is absent from the online node range")

    cache_cpus: set[int] = set()
    for line in bodies["selected-cache-topology"].splitlines():
        match = re.fullmatch(
            r"cpu=([0-9]+) index=index[0-9]+ level=([0-9]+) type=(\S+) "
            r"size=(\S+) shared_cpu_list=([0-9,-]+) line_size=([0-9]+)", line,
        )
        if not match:
            fail("selected cache topology contains a malformed row")
        cpu, level, _, size, shared, line_size = match.groups()
        if int(level) <= 0 or int(line_size) <= 0 or not size or int(cpu) not in parse_cpu_list(shared):
            fail("selected cache topology contains an invalid row")
        cache_cpus.add(int(cpu))
    if cache_cpus != set((probe, *workers)):
        fail("selected cache topology does not cover every selected CPU")
    if len(bodies["lscpu-caches"].splitlines()) < 2:
        fail("lscpu cache evidence contains no cache rows")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\s+[0-9]+\.[0-9]+\s+[0-9]+\.[0-9]+(?:\s+.*)?", bodies["loadavg"]):
        fail("load average evidence is malformed")
    sysfs_pmus = bodies["sysfs-pmus"].splitlines()
    if not sysfs_pmus or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", name) for name in sysfs_pmus):
        fail("sysfs PMU evidence contains an invalid device name")
    perf_pmus = set(re.findall(r"\b([A-Za-z0-9_.-]+)/[^/\n]+/", bodies["perf-pmus"]))
    if not perf_pmus or not perf_pmus.issubset(set(sysfs_pmus)):
        fail("perf PMU rows are malformed or name devices absent from sysfs")
    if "-march=" not in bodies["gcc-native-target"]:
        fail("native compiler target evidence lacks -march")
    if not re.fullmatch(r"/[^\n]*gcc", bodies["command-v-gcc"]):
        fail("host evidence lacks the resolved GCC executable")
    if "11.5.0" not in bodies["gcc-version"]:
        fail("host evidence does not identify GCC 11.5.0")
    if not re.search(r"gcc version 11\.5\.0\b", bodies["gcc-verbose"]):
        fail("host evidence lacks full GCC 11.5.0 verbose output")
    if not re.match(r"Python 3\.[0-9]+\.[0-9]+", bodies["python-version"]):
        fail("host evidence lacks the full Python version")
    return host, probe, workers


def validate_source(root: Path, expected_commit: str, expected_archive_sha256: str) -> dict[str, str]:
    archive_path = root / "source-archive.tar.gz"
    if sha256(archive_path) != expected_archive_sha256:
        fail("retained source archive differs from the external digest")
    derived = archive_manifest(archive_path, expected_commit)
    before = parse_manifest(root / "source-manifest-before.sha256")
    after = parse_manifest(root / "source-manifest-after.sha256")
    if before != derived or after != derived:
        fail("source manifests do not rederive from the retained archive")
    if (root / "source-manifest.diff").read_bytes():
        fail("extracted source tree changed during host execution")
    selected = parse_manifest(root / "source-files.sha256")
    if set(selected) != set(SOURCE_RELATIVES):
        fail("source-files manifest does not bind the five experiment files")
    for relative in SOURCE_RELATIVES:
        if selected[relative] != derived.get(relative):
            fail(f"experiment source digest differs from archive: {relative}")
    return derived


def validate_build_and_binary(root: Path) -> str:
    build = (root / "build.txt").read_text(encoding="utf-8")
    flags = "FLAGS=-O3 -g -std=gnu11 -Wall -Wextra -Werror -march=native -pthread"
    if not build.startswith(flags + "\nCOMMAND=gcc ") or not build.endswith("BUILD_STATUS=pass\n"):
        fail("build receipt lacks the exact command or terminal pass marker")
    for token in (
        " -O3 ", " -g ", " -std=gnu11 ", " -Wall ", " -Wextra ", " -Werror ",
        " -march=native ", " -pthread ", "COMMAND_V_GCC=/", "GCC_DUMPFULLVERSION=11.5.0",
        "gcc version 11.5.0", "SOURCE=/", "OUTPUT=/",
    ):
        if token not in build:
            fail(f"build receipt lacks frozen evidence: {token.strip()}")
    manifest = parse_manifest(root / "binary.sha256")
    expected = {"binary/path-a/dram_bench", "binary/path-b/dram_bench"}
    if set(manifest) != expected or len(set(manifest.values())) != 1:
        fail("binary manifest does not bind identical A/A images")
    for relative, digest in manifest.items():
        if sha256(root / relative) != digest:
            fail(f"binary digest mismatch: {relative}")
    if "ELF" not in (root / "binary.file.txt").read_text(encoding="utf-8"):
        fail("file receipt does not identify ELF linked images")
    if not re.search(r"Build ID:\s*[0-9a-f]+", (root / "binary.build-id.txt").read_text(encoding="utf-8")):
        fail("linked image lacks a retained build identifier")
    ldd = (root / "binary.ldd.txt").read_text(encoding="utf-8")
    if not ldd.strip() or "not found" in ldd:
        fail("runtime library receipt is empty or has an unresolved dependency")
    return next(iter(manifest.values()))


def arm_has_next_dependent_load(assembly: str) -> bool:
    """Recognize linked AArch64 LDR/LDP forms whose next index feeds addressing."""

    lines = assembly.lower().splitlines()
    direct = re.compile(
        r"\b(?:ldr|ldp)\s+(x[0-9]+)(?:\s*,\s*x[0-9]+)?\s*,"
        r"\s*\[[^\]]*,\s*(x[0-9]+)\s*,\s*lsl\s*#(?:0x)?6\]"
    )
    for line in lines:
        match = direct.search(line)
        if match and match.group(1) == match.group(2):
            return True
    indexed_add = re.compile(
        r"\badd\s+(x[0-9]+)\s*,\s*x[0-9]+\s*,\s*(x[0-9]+)\s*,\s*lsl\s*#(?:0x)?6\b"
    )
    address_load = re.compile(
        r"\b(?:ldr|ldp)\s+(x[0-9]+)(?:\s*,\s*x[0-9]+)?\s*,\s*\[(x[0-9]+)(?:\s*,[^\]]+)?\]"
    )
    for index, line in enumerate(lines):
        address = indexed_add.search(line)
        if not address:
            continue
        address_register, next_index_register = address.groups()
        for later in lines[index + 1:index + 5]:
            loaded = address_load.search(later)
            if loaded and loaded.group(1) == next_index_register and loaded.group(2) == address_register:
                return True
    scale = re.compile(r"\blsl\s+(x[0-9]+)\s*,\s*(x[0-9]+)\s*,\s*#(?:0x)?6\b")
    load = re.compile(r"\b(?:ldr|ldp)\s+(x[0-9]+)(?:\s*,\s*x[0-9]+)?\s*,\s*\[([^\]]+)\]")
    for index, line in enumerate(lines):
        scaled = scale.search(line)
        if not scaled:
            continue
        scaled_register, next_register = scaled.groups()
        for later in lines[index + 1:index + 5]:
            loaded = load.search(later)
            if (
                loaded and loaded.group(1) == next_register
                and re.search(rf"\b{re.escape(scaled_register)}\b", loaded.group(2))
            ):
                return True
    return False


def x86_has_exact_node_shift(assembly: str) -> bool:
    return re.search(
        r"\b(?:shl|sal)\b[^\n]*(?:^|[\s,])\$(?:0x6|6)(?=\s|,|$)", assembly,
    ) is not None


def validate_codegen(root: Path, architecture: str) -> None:
    symbols_text = (root / "codegen/symbols.txt").read_text(encoding="utf-8")
    all_assembly = (root / "codegen/all.asm").read_text(encoding="utf-8")
    slices: dict[str, str] = {}
    for symbol in SYMBOLS:
        if len(re.findall(rf"\b{re.escape(symbol)}$", symbols_text, flags=re.MULTILINE)) != 1:
            fail(f"linked symbol table does not contain exactly one {symbol}")
        assembly = (root / f"codegen/{symbol}.asm").read_text(encoding="utf-8")
        if f"<{symbol}>:" not in assembly or assembly not in all_assembly:
            fail(f"per-symbol disassembly is not a slice of the linked image: {symbol}")
        slices[symbol] = assembly
        if not re.search(rf"\b(?:callq?|bl)\b[^\n]*<{re.escape(symbol)}>", all_assembly):
            fail(f"linked image lacks a call edge to {symbol}")
    walker = slices["topic49_walk_dependent"]
    stream = slices["topic49_stream_scan"]
    if architecture == "x86_64":
        if not x86_has_exact_node_shift(walker):
            fail("x86-64 dependent walker lacks its 64-byte index scale")
        if not re.search(r"\bmov[a-z]*\b[^\n]*\([^\n]*\)", walker):
            fail("x86-64 dependent walker lacks a memory load")
        if not re.search(r"\b(?:mov|vmov|vpadd|padd)[a-z0-9]*\b[^\n]*\([^\n]*\)", stream):
            fail("x86-64 stream kernel lacks a memory load")
    elif architecture == "aarch64":
        if not arm_has_next_dependent_load(walker):
            fail("AArch64 dependent walker lacks a next-dependent LDR/LDP address chain")
        if not re.search(r"\b(?:ldr|ldp|ld1[a-z0-9]*)\b", stream):
            fail("AArch64 stream kernel lacks a memory load")
    else:
        fail(f"unsupported code-generation architecture: {architecture}")


def validate_smokes(root: Path, probe: int, workers: tuple[int, ...]) -> None:
    for name, treatment, label in SMOKES:
        stdout = (root / f"smoke/{name}.stdout").read_text(encoding="utf-8")
        result = strict_json_line(stdout)
        validate_result(
            result, label=label, treatment=treatment, probe_cpu=probe, workers=workers,
            large_mib=8, worker_mib=4, warmup_ms=50,
        )
        status = read_json(root / f"smoke/{name}.status.json")
        expected = {"returncode": 0, "timed_out": False, "timeout_seconds": 60}
        if status != expected:
            fail(f"smoke process failed or status schema changed: {name}")


def validate_campaign_command(root: Path, probe: int, workers: tuple[int, ...]) -> None:
    command = (
        "COMMAND=python3 -I -B run_processes.py --binary-a path-a --binary-b path-b "
        f"--out experiment --probe-cpu {probe} --worker-cpus {','.join(map(str, workers))} "
        "--large-mib 512 --worker-mib 128 --warmup-ms 750 --seed 20260828 "
        "--timeout-seconds 300"
    )
    lines = (root / "campaign.txt").read_text(encoding="utf-8").splitlines()
    if lines != [command, "CAMPAIGN_STATUS=pass"]:
        fail("campaign receipt does not contain the exact frozen command and pass marker")


def validate_seal(root: Path) -> None:
    manifest = parse_manifest(root / "MANIFEST.sha256")
    expected = expected_files(sealed=True) - {"MANIFEST.sha256", "SEALED"}
    if set(manifest) != expected:
        fail("seal manifest excludes more than the two root seal files or has unexpected entries")
    for relative, digest in manifest.items():
        if sha256(root / relative) != digest:
            fail(f"sealed file digest mismatch: {relative}")
    seal = read_json(root / "SEALED")
    expected_seal = {
        "schema": "topic49-seal.v1", "manifest_sha256": sha256(root / "MANIFEST.sha256"),
        "file_count": len(manifest),
    }
    if not same(seal, expected_seal):
        fail("SEALED does not bind the exact retained manifest")


def validate_receipts(
    root: Path, *, expected_target_label: str, expected_hostname: str,
    expected_architecture: str, expected_source_commit: str,
    expected_source_archive_sha256: str, allow_unsealed: bool,
) -> dict[str, Any]:
    if not root.is_dir():
        fail("receipt directory does not exist")
    if not HEX40.fullmatch(expected_source_commit):
        fail("external expected source commit is malformed")
    if not HEX64.fullmatch(expected_source_archive_sha256):
        fail("external expected archive digest is malformed")
    validate_tree(root, sealed=not allow_unsealed)
    _, probe, workers = validate_host(
        root, target_label=expected_target_label, hostname=expected_hostname,
        architecture=expected_architecture, expected_commit=expected_source_commit,
        expected_archive_sha256=expected_source_archive_sha256,
    )
    validate_source(root, expected_source_commit, expected_source_archive_sha256)
    binary_digest = validate_build_and_binary(root)
    validate_codegen(root, expected_architecture)
    validate_smokes(root, probe, workers)
    validate_campaign_command(root, probe, workers)
    metadata = read_json(root / "experiment/metadata.json")
    config, metadata_workers = validate_metadata(metadata)
    validate_campaign_binary_identity(metadata, binary_digest)
    if config["probe_cpu"] != probe or metadata_workers != workers:
        fail("campaign CPU selection differs from concrete host evidence")
    rows, results = validate_attempts(root, metadata, config, workers)
    validate_journal(root, rows)
    recomputed = recompute_summary(metadata, config, rows, results)
    retained = read_json(root / "experiment/summary.json")
    if not same(recomputed, retained):
        fail("retained analysis does not independently recompute from raw attempts")
    required_digests = {relative: sha256(root / relative) for relative in sorted(STATIC_FILES)}
    result: dict[str, Any] = {
        "schema": "topic49-receipt-validation.v1", "status": "pass",
        "target_label": expected_target_label, "runtime_hostname": expected_hostname,
        "architecture": expected_architecture,
        "source_commit": expected_source_commit,
        "source_archive_sha256": expected_source_archive_sha256,
        "external_source_commit_anchor": expected_source_commit,
        "external_source_archive_sha256_anchor": expected_source_archive_sha256,
        "binary_sha256": binary_digest, "required_file_sha256": required_digests,
        "process_replication": "12 primary and 4 A/A four-process blocks; 64 fresh PIDs",
        "interval_scope": "between-block variation on one exact host, binary, input, and run window",
    }
    if not allow_unsealed:
        validate_seal(root)
        retained_validation = read_json(root / "receipt-validation.json")
        if not same(retained_validation, result):
            fail("retained pre-seal validation differs from standalone sealed validation")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone validation of an exact-source Topic 49 receipt.")
    parser.add_argument("receipt_dir", type=Path)
    parser.add_argument("--expected-target-label", required=True)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-source-archive-sha256", required=True)
    parser.add_argument("--allow-unsealed", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"validation output already exists: {output}")
    try:
        result = validate_receipts(
            args.receipt_dir.resolve(), expected_target_label=args.expected_target_label,
            expected_hostname=args.expected_hostname,
            expected_architecture=args.expected_architecture,
            expected_source_commit=args.expected_source_commit.lower(),
            expected_source_archive_sha256=args.expected_source_archive_sha256.lower(),
            allow_unsealed=args.allow_unsealed,
        )
    except (OSError, ValueError, TypeError, tarfile.TarError) as error:
        raise SystemExit(f"Topic 49 receipt validation failed: {error}") from error
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        destination.flush()
        os.fsync(destination.fileno())


if __name__ == "__main__":
    main()
