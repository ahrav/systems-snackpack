#!/usr/bin/env python3
"""Independent validation for exact-source Topic 50 host receipts.

The validator imports neither the process runner nor the analyzer. It freezes
the schedule, schemas, assignment rules, and block-level interval calculation
a second time so acquisition and validation cannot agree through one shared
implementation bug.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import stat
import statistics
import tarfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn


ARM_TARGET = "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com"
TOPIC = "topics/050-cpu-service-chain"
SOURCE_RELATIVES = (
    f"{TOPIC}/experiment/README.md",
    f"{TOPIC}/experiment/lock_holder_preemption.c",
    f"{TOPIC}/experiment/run_processes.py",
    f"{TOPIC}/experiment/analyze.py",
    f"{TOPIC}/experiment/validate_receipts.py",
    f"{TOPIC}/experiment/run_host.sh",
)
PRIMARY_SCHEDULE = ("BAAB", "ABBA", "ABBA", "BAAB", "BAAB", "ABBA", "BAAB", "ABBA")
AA_SCHEDULE = ("YXXY", "YXXY", "XYYX", "YXXY", "XYYX", "XYYX", "XYYX", "YXXY")
T975_DF7 = 2.364624251
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
HEADER = (
    "label", "block", "period", "mode", "pid", "started_realtime_ns",
    "holder_cpu_requested", "waiter_cpu_requested", "hog_cpu_requested",
    "holder_nice_requested", "holder_nice_set_rc", "holder_nice_set_errno",
    "holder_nice_observed", "waiter_nice_observed", "hog_nice_observed",
    "holder_sched_get_rc", "holder_sched_policy", "holder_sched_priority",
    "waiter_sched_get_rc", "waiter_sched_policy", "waiter_sched_priority",
    "hog_sched_get_rc", "hog_sched_policy", "hog_sched_priority",
    "holder_pin_rc", "waiter_pin_rc", "hog_pin_rc",
    "holder_affinity_exact", "waiter_affinity_exact", "hog_affinity_exact",
    "holder_wall_ns", "holder_cpu_ns", "holder_start_cpu", "holder_end_cpu",
    "waiter_wait_ns", "waiter_start_cpu", "waiter_end_cpu", "hog_wall_ns",
    "hog_cpu_ns", "hog_start_cpu", "hog_end_cpu", "holder_voluntary_context_switches",
    "holder_involuntary_context_switches", "waiter_voluntary_context_switches",
    "waiter_involuntary_context_switches", "hog_voluntary_context_switches",
    "hog_involuntary_context_switches",
)
INTEGER_FIELDS = set(HEADER) - {"label", "mode"}
BASE_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PATH": "/bin:/usr/bin", "TZ": "UTC"}
STATIC_FILES = {
    "source-archive.tar.gz",
    "source-manifest-before.sha256",
    "source-manifest-after.sha256",
    "source-manifest.diff",
    "source-files.sha256",
    "host.json",
    "build.txt",
    "binary.sha256",
    "binary.file.txt",
    "binary.ldd.txt",
    "binary.build-id.txt",
    "campaign.txt",
    "codegen/all.asm",
    "codegen/symbols.txt",
    "codegen/holder_main.asm",
    "codegen/waiter_main.asm",
    "codegen/hog_main.asm",
    "codegen/burn_thread_cpu.asm",
    "smoke/same-cpu.stdout",
    "smoke/same-cpu.stderr",
    "smoke/same-cpu.status.json",
    "smoke/separate-core.stdout",
    "smoke/separate-core.stderr",
    "smoke/separate-core.status.json",
    "experiment/metadata.json",
    "experiment/schedule.json",
    "experiment/raw.csv",
    "experiment/attempts.jsonl",
    "experiment/attempt-journal.jsonl",
    "experiment/failures.jsonl",
    "experiment/build.stdout",
    "experiment/build.stderr",
    "experiment/build.status.json",
    "experiment/lock_holder_preemption",
    "experiment/summary.json",
}


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def reject_constant(token: str) -> NoReturn:
    fail(f"non-finite JSON number: {token}")


def strict_json(text: str) -> object:
    return json.loads(text, object_pairs_hook=reject_pairs, parse_constant=reject_constant)


def read_json(path: Path) -> dict[str, Any]:
    value = strict_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path}: expected one JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.endswith("\n") or not line.strip():
                fail(f"{path}:{line_number}: partial or blank JSONL record")
            value = strict_json(line)
            if not isinstance(value, dict):
                fail(f"{path}:{line_number}: expected one JSON object")
            rows.append(value)
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def same(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if type(left) in (int, float) and type(right) in (int, float):
        return math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-12)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(same(left[key], right[key]) for key in left)
    return type(left) is type(right) and left == right


def parse_manifest(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        candidate = PurePosixPath(relative)
        if (
            not separator
            or not HEX64.fullmatch(digest)
            or not relative
            or candidate.is_absolute()
            or ".." in candidate.parts
            or relative in result
        ):
            fail(f"malformed manifest line in {path}: {line}")
        result[relative] = digest
    if not result:
        fail(f"empty manifest: {path}")
    return result


def parse_cpu_list(text: str) -> set[int]:
    cpus = set()
    for piece in text.split(","):
        bounds = piece.split("-", 1)
        try:
            first = int(bounds[0])
            last = int(bounds[-1])
        except ValueError as error:
            fail(f"malformed topology CPU list: {text}: {error}")
        if first < 0 or last < first:
            fail(f"malformed topology CPU range: {piece}")
        cpus.update(range(first, last + 1))
    if not cpus:
        fail("topology CPU list is empty")
    return cpus


def expected_specs() -> list[dict[str, object]]:
    specs = []
    sequence = 0
    for experiment, schedule in (("treatment", PRIMARY_SCHEDULE), ("aa", AA_SCHEDULE)):
        for block, template in enumerate(schedule, 1):
            for period, label in enumerate(template, 1):
                sequence += 1
                mode = "same_cpu" if experiment == "treatment" and label == "A" else "separate_core"
                specs.append(
                    {
                        "sequence": sequence,
                        "experiment": experiment,
                        "block": block,
                        "template": template,
                        "period": period,
                        "label": label,
                        "mode": mode,
                    }
                )
    return specs


def expected_files(sealed: bool) -> set[str]:
    files = set(STATIC_FILES)
    for spec in expected_specs():
        stem = (
            f"{spec['sequence']:03d}-{spec['experiment']}-block{spec['block']:02d}-"
            f"p{spec['period']}-{spec['label']}"
        )
        for suffix in ("stdout", "stderr", "status.json"):
            files.add(f"experiment/raw/{stem}.{suffix}")
    if sealed:
        files.update({"receipt-validation.json", "MANIFEST.sha256", "SEALED"})
    return files


def validate_tree(root: Path, sealed: bool) -> None:
    if not root.is_dir() or root.is_symlink():
        fail("receipt root is not a plain directory")
    files = set()
    stack = [root]
    while stack:
        directory = stack.pop()
        if sealed and directory.lstat().st_mode & 0o222:
            fail(f"sealed directory remains writable: {directory.relative_to(root)}")
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    fail(f"receipt contains a symbolic link: {relative}")
                if stat.S_ISDIR(mode):
                    stack.append(path)
                elif stat.S_ISREG(mode):
                    if sealed and mode & 0o222:
                        fail(f"sealed file remains writable: {relative}")
                    files.add(relative)
                else:
                    fail(f"receipt contains a special entry: {relative}")
    expected = expected_files(sealed)
    if files != expected:
        fail(f"receipt file set changed; missing={sorted(expected-files)}, unexpected={sorted(files-expected)}")


def validate_archive(root: Path, commit: str, archive_digest: str) -> dict[str, bytes]:
    archive_path = root / "source-archive.tar.gz"
    if sha256(archive_path) != archive_digest:
        fail("retained source archive digest differs from controller digest")
    prefix = f"systems-snackpack-{commit}/"
    topic = prefix + TOPIC + "/"
    expected_names = {prefix + relative for relative in SOURCE_RELATIVES}
    payloads = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        embedded = archive.pax_headers.get("comment")
        if embedded is None:
            embedded = next(
                (member.pax_headers.get("comment") for member in members if member.pax_headers.get("comment")),
                None,
            )
        if embedded != commit:
            fail("retained source archive does not embed controller commit")
        if len(members) > 256:
            fail("retained source archive exceeds member cap")
        seen = set()
        total = 0
        for member in members:
            path = PurePosixPath(member.name)
            if (
                member.name in seen
                or path.is_absolute()
                or ".." in path.parts
                or not (member.isdir() or member.isfile())
            ):
                fail(f"unsafe retained archive member: {member.name}")
            seen.add(member.name)
            if member.isfile():
                if not member.name.startswith(topic):
                    fail(f"retained archive file escaped Topic 50: {member.name}")
                total += member.size
                extracted = archive.extractfile(member)
                if extracted is None:
                    fail(f"cannot read retained source member: {member.name}")
                payloads[member.name] = extracted.read()
        if total > 16 * 1024 * 1024 or len(payloads) > 128:
            fail("retained archive exceeds size cap")
    if not expected_names.issubset(payloads):
        fail(f"retained archive lacks sources: {sorted(expected_names-set(payloads))}")
    return payloads


def validate_sources(root: Path, payloads: dict[str, bytes], commit: str) -> None:
    before = parse_manifest(root / "source-manifest-before.sha256")
    after = parse_manifest(root / "source-manifest-after.sha256")
    frozen = parse_manifest(root / "source-files.sha256")
    if before != after or before != frozen:
        fail("source before/after/frozen manifests differ")
    if (root / "source-manifest.diff").read_bytes():
        fail("source mutation diff is nonempty")
    if set(before) != set(SOURCE_RELATIVES):
        fail("source manifest path set changed")
    prefix = f"systems-snackpack-{commit}/"
    for relative, digest in before.items():
        payload = payloads.get(prefix + relative)
        if payload is None or hashlib.sha256(payload).hexdigest() != digest:
            fail(f"archived source differs from retained source manifest: {relative}")


def validate_identity(
    root: Path,
    target_label: str,
    expected_hostname: str,
    expected_architecture: str,
    commit: str,
    archive_digest: str,
) -> None:
    host = read_json(root / "host.json")
    for key, expected in (
        ("schema", "topic50-host.v1"),
        ("target_label", target_label),
        ("expected_hostname", expected_hostname),
        ("expected_architecture", expected_architecture),
        ("source_commit", commit),
        ("source_archive_sha256", archive_digest),
        ("machine", expected_architecture),
    ):
        if host.get(key) != expected:
            fail(f"host identity field changed: {key}")
    runtime = host.get("runtime_hostname")
    if not isinstance(runtime, dict) or runtime.get("returncode") != 0 or runtime.get("output") != expected_hostname:
        fail("host receipt does not prove expected runtime hostname")
    if target_label == "xxl":
        if expected_architecture != "x86_64":
            fail("controller expectation is not an authorized runtime-resolved xxl target")
    elif target_label == ARM_TARGET:
        if expected_hostname != ARM_TARGET or expected_architecture != "aarch64":
            fail("controller expectation is not the literal authorized Arm target")
    else:
        fail("receipt names an unauthorized target")


def validate_metadata(
    root: Path,
    target_label: str,
    expected_hostname: str,
    expected_architecture: str,
    commit: str,
    archive_digest: str,
) -> tuple[dict[str, Any], dict[str, int], str]:
    metadata = read_json(root / "experiment/metadata.json")
    expected_fields = {
        "schema": "topic50-campaign.v1",
        "target_label": target_label,
        "expected_hostname": expected_hostname,
        "expected_architecture": expected_architecture,
        "source_commit": commit,
        "source_archive_sha256": archive_digest,
        "base_environment": BASE_ENVIRONMENT,
    }
    for key, expected in expected_fields.items():
        if metadata.get(key) != expected:
            fail(f"campaign metadata field changed: {key}")
    uname = metadata.get("uname")
    hostname = metadata.get("hostname_f")
    if not isinstance(uname, dict) or uname.get("machine") != expected_architecture or uname.get("node") != expected_hostname:
        fail("campaign uname identity changed")
    if not isinstance(hostname, dict) or hostname.get("returncode") != 0 or hostname.get("output") != expected_hostname:
        fail("campaign hostname probe changed")
    if not isinstance(metadata.get("cpu_count_configured"), int) or metadata["cpu_count_configured"] < 3:
        fail("configured CPU count is missing or too small")
    affinity = metadata.get("effective_affinity")
    if not isinstance(affinity, list) or len(affinity) < 3 or any(type(cpu) is not int for cpu in affinity):
        fail("effective affinity metadata is malformed")
    if metadata.get("cpu_count_allowed") != len(affinity):
        fail("allowed CPU count differs from effective affinity")
    if (
        metadata.get("process_scheduler_policy") != 0
        or metadata.get("process_scheduler_priority") != 0
        or metadata.get("process_nice") != 0
    ):
        fail("campaign controller did not run under SCHED_OTHER priority 0 and nice 0")
    selected = metadata.get("selected")
    if not isinstance(selected, dict) or set(selected) != {"holder", "waiter", "control", "holder_sibling"}:
        fail("selected CPU metadata changed")
    if any(type(selected[key]) is not int for key in selected):
        fail("selected CPU values are not integers")
    chosen = [selected["holder"], selected["waiter"], selected["control"]]
    if len(set(chosen)) != 3 or any(cpu not in affinity for cpu in chosen):
        fail("selected CPUs are not three allowed logical CPUs")
    topology = metadata.get("topology")
    if not isinstance(topology, dict) or topology.get("allowed") != affinity or not isinstance(topology.get("records"), list):
        fail("topology metadata changed")
    location = {}
    for record in topology["records"]:
        if not isinstance(record, dict) or not {"cpu", "package", "core", "thread_siblings_list"}.issubset(record):
            fail("topology record is malformed")
        if (
            type(record["cpu"]) is not int
            or type(record["package"]) is not int
            or type(record["core"]) is not int
            or record["package"] < 0
            or record["core"] < 0
            or not isinstance(record["thread_siblings_list"], str)
            or record["cpu"] not in parse_cpu_list(record["thread_siblings_list"])
        ):
            fail("topology record lacks strict package/core/sibling evidence")
        location[record["cpu"]] = (record["package"], record["core"])
    if any(cpu not in location for cpu in chosen) or len({location[cpu] for cpu in chosen}) != 3:
        fail("selected holder, waiter, and control do not occupy distinct physical-core groups")
    design = metadata.get("design")
    if not isinstance(design, dict):
        fail("campaign design metadata is missing")
    for key, expected in (
        ("seed", 500829),
        ("complete_blocks", 8),
        ("holder_cpu_target_us", 5000),
        ("holder_nice", 19),
        ("analysis_unit", "one complete four-period block log contrast"),
    ):
        if design.get(key) != expected:
            fail(f"campaign design field changed: {key}")
    scheduler = metadata.get("scheduler_exposure")
    if not isinstance(scheduler, dict) or "/proc/sys/kernel/sched_autogroup_enabled" not in scheduler:
        fail("scheduler exposure metadata is missing")
    sysfs = metadata.get("sysfs")
    if not isinstance(sysfs, dict) or not {"smt_active", "smt_control", "cpus"}.issubset(sysfs):
        fail("SMT/cpufreq/cpuidle metadata is missing")
    cpu_meta = sysfs.get("cpus")
    if not isinstance(cpu_meta, dict):
        fail("per-CPU power metadata is missing")
    for role in ("holder", "waiter", "control"):
        entry = cpu_meta.get(role)
        if not isinstance(entry, dict) or not isinstance(entry.get("cpufreq"), dict) or not isinstance(
            entry.get("cpuidle"), list
        ):
            fail(f"cpufreq/cpuidle exposure is missing for {role}")
    toolchain = metadata.get("toolchain")
    if not isinstance(toolchain, dict):
        fail("toolchain metadata is missing")
    for name in ("cc", "python"):
        probe = toolchain.get(name)
        if not isinstance(probe, dict) or probe.get("returncode") != 0 or not probe.get("output"):
            fail(f"required toolchain probe failed: {name}")
    if "gcc" not in toolchain["cc"]["output"].lower():
        fail("exact burn-loop codegen contract requires GCC")
    binary_digest = metadata.get("binary_sha256")
    if not isinstance(binary_digest, str) or not HEX64.fullmatch(binary_digest):
        fail("campaign binary digest is malformed")
    source_digest = metadata.get("source_sha256")
    if not isinstance(source_digest, str) or not HEX64.fullmatch(source_digest):
        fail("native source digest is malformed")
    return metadata, {key: int(value) for key, value in selected.items()}, binary_digest


def validate_schedule(root: Path) -> None:
    schedule = read_json(root / "experiment/schedule.json")
    expected = {"seed": 500829, "treatment": list(PRIMARY_SCHEDULE), "aa": list(AA_SCHEDULE)}
    if schedule != expected:
        fail("retained schedule differs from the frozen successful scratch schedule")


def parse_native_line(text: str) -> dict[str, object]:
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        fail("native stdout must contain exactly one nonempty CSV line")
    try:
        values = next(csv.reader([lines[0]]))
    except csv.Error as error:
        fail(f"native stdout is not CSV: {error}")
    if len(values) != len(HEADER):
        fail(f"native stdout has {len(values)} fields, expected {len(HEADER)}")
    result: dict[str, object] = dict(zip(HEADER, values))
    try:
        for field in INTEGER_FIELDS:
            result[field] = int(result[field])
    except (TypeError, ValueError) as error:
        fail(f"native stdout has a non-integer field: {error}")
    return result


def validate_result(result: dict[str, object], spec: dict[str, object], selected: dict[str, int]) -> None:
    if set(result) != set(HEADER):
        fail(f"attempt {spec['sequence']} result schema changed")
    expected_hog = selected["holder"] if spec["mode"] == "same_cpu" else selected["control"]
    expected = {
        "label": spec["label"],
        "block": spec["block"],
        "period": spec["period"],
        "mode": spec["mode"],
        "holder_cpu_requested": selected["holder"],
        "waiter_cpu_requested": selected["waiter"],
        "hog_cpu_requested": expected_hog,
        "holder_nice_requested": 19,
        "holder_nice_set_rc": 0,
        "holder_nice_set_errno": 0,
        "holder_nice_observed": 19,
        "waiter_nice_observed": 0,
        "hog_nice_observed": 0,
        "holder_sched_get_rc": 0,
        "holder_sched_policy": 0,
        "holder_sched_priority": 0,
        "waiter_sched_get_rc": 0,
        "waiter_sched_policy": 0,
        "waiter_sched_priority": 0,
        "hog_sched_get_rc": 0,
        "hog_sched_policy": 0,
        "hog_sched_priority": 0,
        "holder_pin_rc": 0,
        "waiter_pin_rc": 0,
        "hog_pin_rc": 0,
        "holder_affinity_exact": 1,
        "waiter_affinity_exact": 1,
        "hog_affinity_exact": 1,
        "holder_start_cpu": selected["holder"],
        "holder_end_cpu": selected["holder"],
        "waiter_start_cpu": selected["waiter"],
        "waiter_end_cpu": selected["waiter"],
        "hog_start_cpu": expected_hog,
        "hog_end_cpu": expected_hog,
    }
    for key, value in expected.items():
        if result.get(key) != value:
            fail(f"attempt {spec['sequence']} result field changed: {key}")
    for field in (
        "pid",
        "started_realtime_ns",
        "holder_wall_ns",
        "holder_cpu_ns",
        "waiter_wait_ns",
        "hog_wall_ns",
        "hog_cpu_ns",
    ):
        if type(result.get(field)) is not int or result[field] <= 0:
            fail(f"attempt {spec['sequence']} has invalid positive field: {field}")
    if not 4_900_000 <= result["holder_cpu_ns"] <= 6_000_000:
        fail(f"attempt {spec['sequence']} holder CPU time escaped the frozen 4.9-6.0 ms control range")
    for field in HEADER:
        if field.endswith("context_switches") and (type(result[field]) is not int or result[field] < 0):
            fail(f"attempt {spec['sequence']} has invalid context-switch count")


def validate_attempts(
    root: Path, selected: dict[str, int], binary_digest: str
) -> list[dict[str, object]]:
    attempts = read_jsonl(root / "experiment/attempts.jsonl")
    specs = expected_specs()
    if len(attempts) != 64:
        fail("complete campaign must contain exactly 64 retained attempts")
    if (root / "experiment/failures.jsonl").read_bytes():
        fail("published complete campaign contains a failed attempt")

    with (root / "experiment/raw.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("experiment", *HEADER):
            fail("raw CSV header changed")
        csv_rows = list(reader)
    if len(csv_rows) != 64:
        fail("raw CSV must contain exactly 64 process rows")

    command_binary = None
    pids = set()
    typed_rows = []
    for index, (spec, attempt, raw_csv) in enumerate(zip(specs, attempts, csv_rows), 1):
        for key in ("sequence", "experiment", "block", "period", "label", "mode"):
            if attempt.get(key) != spec[key]:
                fail(f"attempt {index} assignment changed: {key}")
        if attempt.get("schema") != "topic50-attempt.v1":
            fail(f"attempt {index} schema changed")
        if attempt.get("environment") != BASE_ENVIRONMENT or attempt.get("timeout_seconds") != 30:
            fail(f"attempt {index} environment or timeout changed")
        command = attempt.get("command")
        if not isinstance(command, list) or len(command) != 10 or any(not isinstance(item, str) for item in command):
            fail(f"attempt {index} command is malformed")
        if command_binary is None:
            command_binary = command[0]
        if command[0] != command_binary or not command[0].endswith("/experiment/lock_holder_preemption"):
            fail(f"attempt {index} did not use the one retained campaign binary")
        expected_hog = selected["holder"] if spec["mode"] == "same_cpu" else selected["control"]
        expected_argv = [
            str(spec["label"]), str(spec["block"]), str(spec["period"]), str(spec["mode"]),
            str(selected["holder"]), str(selected["waiter"]), str(expected_hog), "19", "5000",
        ]
        if command[1:] != expected_argv:
            fail(f"attempt {index} native arguments changed")
        for key, expected in (
            ("returncode", 0),
            ("timed_out", False),
            ("artifact_error", None),
            ("valid", True),
            ("validation_error", None),
            ("binary_sha256_before", binary_digest),
            ("binary_sha256_after", binary_digest),
        ):
            if attempt.get(key) != expected:
                fail(f"attempt {index} outcome field changed: {key}")
        if not isinstance(attempt.get("started_utc"), str) or not UTC.fullmatch(attempt["started_utc"]):
            fail(f"attempt {index} UTC timestamp is malformed")
        for field in ("started_monotonic_ns", "ended_monotonic_ns", "wall_ns", "pid"):
            if type(attempt.get(field)) is not int or attempt[field] <= 0:
                fail(f"attempt {index} timing/PID field is malformed: {field}")
        if attempt["ended_monotonic_ns"] <= attempt["started_monotonic_ns"]:
            fail(f"attempt {index} monotonic interval is not positive")
        if attempt["wall_ns"] != attempt["ended_monotonic_ns"] - attempt["started_monotonic_ns"]:
            fail(f"attempt {index} wall interval changed")

        stem = f"{index:03d}-{spec['experiment']}-block{spec['block']:02d}-p{spec['period']}-{spec['label']}"
        expected_paths = {
            "stdout_path": f"raw/{stem}.stdout",
            "stderr_path": f"raw/{stem}.stderr",
            "status_path": f"raw/{stem}.status.json",
        }
        for key, relative in expected_paths.items():
            if attempt.get(key) != relative:
                fail(f"attempt {index} retained path changed: {key}")
        raw_root = root / "experiment"
        stdout = (raw_root / expected_paths["stdout_path"]).read_text(encoding="utf-8")
        stderr = (raw_root / expected_paths["stderr_path"]).read_text(encoding="utf-8")
        status = read_json(raw_root / expected_paths["status_path"])
        if stdout != attempt.get("stdout") or stderr != attempt.get("stderr") or not same(status, attempt):
            fail(f"attempt {index} raw receipt differs from attempts ledger")
        result = parse_native_line(stdout)
        retained_result = attempt.get("result")
        if not isinstance(retained_result, dict) or not same(result, retained_result):
            fail(f"attempt {index} parsed result differs from retained result")
        validate_result(result, spec, selected)
        if result["pid"] != attempt["pid"] or result["pid"] in pids:
            fail(f"attempt {index} does not have a fresh matching PID")
        pids.add(result["pid"])
        if raw_csv.get("experiment") != spec["experiment"]:
            fail(f"attempt {index} raw CSV experiment changed")
        for field in HEADER:
            expected_text = str(result[field])
            if raw_csv.get(field) != expected_text:
                fail(f"attempt {index} raw CSV differs on {field}")
        typed_rows.append({"experiment": spec["experiment"], **result})
    if len(pids) != 64:
        fail("campaign does not contain 64 fresh PIDs")
    return typed_rows


def validate_journal(root: Path, attempts: list[dict[str, Any]]) -> None:
    journal = read_jsonl(root / "experiment/attempt-journal.jsonl")
    specs = expected_specs()
    if len(journal) != 128:
        fail("complete campaign must contain exactly 128 journal events")
    previous = -1
    for index, (spec, attempt) in enumerate(zip(specs, attempts)):
        start = journal[index * 2]
        end = journal[index * 2 + 1]
        expected_start = {
            "schema": "topic50-attempt-journal.v1",
            "event": "attempt-start",
            "sequence": spec["sequence"],
            "experiment": spec["experiment"],
            "block": spec["block"],
            "period": spec["period"],
            "label": spec["label"],
            "mode": spec["mode"],
        }
        for key, value in expected_start.items():
            if start.get(key) != value:
                fail(f"attempt {spec['sequence']} start journal changed: {key}")
        expected_end = {
            "schema": "topic50-attempt-journal.v1",
            "event": "attempt-end",
            "sequence": spec["sequence"],
            "outcome": "valid",
            "pid": attempt["pid"],
        }
        for key, value in expected_end.items():
            if end.get(key) != value:
                fail(f"attempt {spec['sequence']} end journal changed: {key}")
        for event in (start, end):
            if not isinstance(event.get("journaled_utc"), str) or not UTC.fullmatch(event["journaled_utc"]):
                fail(f"attempt {spec['sequence']} journal UTC is malformed")
            current = event.get("journaled_monotonic_ns")
            if type(current) is not int or current <= previous:
                fail(f"attempt {spec['sequence']} journal order changed")
            previous = current
        if start["journaled_monotonic_ns"] > attempt["started_monotonic_ns"]:
            fail(f"attempt {spec['sequence']} launched before its start journal")
        if end["journaled_monotonic_ns"] < attempt["ended_monotonic_ns"]:
            fail(f"attempt {spec['sequence']} ended after its end journal")


def describe(values: list[int], scale: float = 1.0) -> dict[str, object]:
    scaled = [value / scale for value in values]
    return {
        "n_processes": len(scaled),
        "median": statistics.median(scaled),
        "min": min(scaled),
        "max": max(scaled),
    }


def independent_interval(
    rows: list[dict[str, object]], experiment: str, numerator: str, denominator: str, metric: str
) -> dict[str, object]:
    groups: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["experiment"] == experiment:
            groups[int(row["block"])].append(row)
    if sorted(groups) != list(range(1, 9)):
        fail(f"{experiment} does not contain eight complete block identifiers")
    contrasts = []
    block_rows = []
    for block in range(1, 9):
        group = groups[block]
        num = [int(row[metric]) for row in group if row["label"] == numerator]
        den = [int(row[metric]) for row in group if row["label"] == denominator]
        if len(group) != 4 or len(num) != 2 or len(den) != 2 or min(num + den) <= 0:
            fail(f"{experiment} block {block} is incomplete for {metric}")
        contrast = statistics.fmean(math.log(value) for value in num) - statistics.fmean(
            math.log(value) for value in den
        )
        contrasts.append(contrast)
        block_rows.append({"block": block, "log_contrast": contrast, "ratio": math.exp(contrast)})
    mean = statistics.fmean(contrasts)
    sd = statistics.stdev(contrasts)
    half_width = T975_DF7 * sd / math.sqrt(8)
    return {
        "metric": metric,
        "ratio": f"{numerator}/{denominator}",
        "complete_blocks": 8,
        "point_estimate_geometric_ratio": math.exp(mean),
        "two_sided_95pct_t_interval": [math.exp(mean - half_width), math.exp(mean + half_width)],
        "sample_sd_log_contrast": sd,
        "block_contrasts": block_rows,
        "boundary": "interval covers dispersion across complete four-period blocks on this host/window; it does not cover host, kernel, build, or workload populations",
    }


def independent_descriptives(rows: list[dict[str, object]]) -> dict[str, object]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["experiment"]), str(row["label"]))].append(row)
    output = {}
    for (experiment, label), group in sorted(groups.items()):
        output[f"{experiment}:{label}"] = {
            "holder_wall_ms": describe([int(row["holder_wall_ns"]) for row in group], 1e6),
            "holder_cpu_ms": describe([int(row["holder_cpu_ns"]) for row in group], 1e6),
            "waiter_wait_ms": describe([int(row["waiter_wait_ns"]) for row in group], 1e6),
            "holder_involuntary_context_switches": describe(
                [int(row["holder_involuntary_context_switches"]) for row in group]
            ),
        }
    return output


def validate_analysis(root: Path, rows: list[dict[str, object]], binary_digest: str) -> None:
    summary = read_json(root / "experiment/summary.json")
    if summary.get("schema") != "topic50-analysis.v1":
        fail("analysis schema changed")
    validation = summary.get("validation")
    if not isinstance(validation, dict):
        fail("analysis validation object is missing")
    for key, expected in (
        ("pass", True),
        ("row_count", 64),
        ("expected_row_count", 64),
        ("unique_pid_count", 64),
        ("failed_attempt_file_empty", True),
        ("errors", []),
    ):
        if validation.get(key) != expected:
            fail(f"analysis validation field changed: {key}")
    aa = validation.get("aa_mechanical_identity")
    if not isinstance(aa, dict) or aa.get("binary_sha256") != binary_digest:
        fail("analysis A/A identity does not bind the retained binary")
    expected = {
        "process_descriptives": independent_descriptives(rows),
        "treatment_holder_wall": independent_interval(rows, "treatment", "A", "B", "holder_wall_ns"),
        "treatment_waiter_wait": independent_interval(rows, "treatment", "A", "B", "waiter_wait_ns"),
        "aa_holder_wall": independent_interval(rows, "aa", "X", "Y", "holder_wall_ns"),
        "aa_waiter_wait": independent_interval(rows, "aa", "X", "Y", "waiter_wait_ns"),
    }
    for key, value in expected.items():
        if not same(summary.get(key), value):
            fail(f"analysis differs from independent calculation: {key}")


def validate_binary_and_codegen(root: Path, architecture: str, binary_digest: str) -> None:
    binary = root / "experiment/lock_holder_preemption"
    if sha256(binary) != binary_digest:
        fail("retained campaign binary digest changed")
    digest_line = (root / "binary.sha256").read_text(encoding="utf-8").strip().split()
    if not digest_line or digest_line[0] != binary_digest:
        fail("binary digest receipt changed")
    file_text = (root / "binary.file.txt").read_text(encoding="utf-8")
    if "ELF" not in file_text:
        fail("file receipt does not identify an ELF binary")
    if architecture == "x86_64" and "x86-64" not in file_text:
        fail("x86 receipt does not identify an x86-64 linked image")
    if architecture == "aarch64" and not re.search(r"ARM aarch64|aarch64", file_text, re.IGNORECASE):
        fail("Arm receipt does not identify an AArch64 linked image")
    ldd_text = (root / "binary.ldd.txt").read_text(encoding="utf-8")
    if not ldd_text.strip() or "not found" in ldd_text:
        fail("linked-library receipt is empty or unresolved")
    build_status = read_json(root / "experiment/build.status.json")
    command = build_status.get("command")
    if (
        build_status.get("schema") != "topic50-build.v1"
        or build_status.get("returncode") != 0
        or build_status.get("environment") != BASE_ENVIRONMENT
        or not isinstance(command, list)
        or len(command) != 11
        or command[:8] != ["cc", "-O2", "-g", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pthread"]
        or not command[8].endswith(f"/{TOPIC}/experiment/lock_holder_preemption.c")
        or command[9] != "-o"
        or not command[10].endswith("/experiment/lock_holder_preemption")
    ):
        fail("native build receipt changed")
    if (root / "experiment/build.stderr").read_text(encoding="utf-8").strip():
        fail("warning-clean native build emitted stderr")
    symbols = (root / "codegen/symbols.txt").read_text(encoding="utf-8")
    assembly = (root / "codegen/all.asm").read_text(encoding="utf-8")
    if len(assembly) < 1000:
        fail("linked disassembly is unexpectedly short")
    for symbol in ("holder_main", "waiter_main", "hog_main", "burn_thread_cpu"):
        if not re.search(rf"\b{symbol}$", symbols, re.MULTILINE):
            fail(f"linked symbol is missing: {symbol}")
        focused = (root / f"codegen/{symbol}.asm").read_text(encoding="utf-8")
        if symbol not in focused or len(focused) < 100:
            fail(f"focused linked disassembly is missing: {symbol}")


def validate_smokes(root: Path, selected: dict[str, int]) -> None:
    for name, mode, hog in (
        ("same-cpu", "same_cpu", selected["holder"]),
        ("separate-core", "separate_core", selected["control"]),
    ):
        stdout = (root / f"smoke/{name}.stdout").read_text(encoding="utf-8")
        stderr = (root / f"smoke/{name}.stderr").read_text(encoding="utf-8")
        status = read_json(root / f"smoke/{name}.status.json")
        if stderr or status != {
            "schema": "topic50-smoke.v1",
            "name": name,
            "mode": mode,
            "hog_cpu": hog,
            "started_realtime_ns": status.get("started_realtime_ns"),
            "ended_realtime_ns": status.get("ended_realtime_ns"),
            "returncode": 0,
        }:
            fail(f"smoke status changed: {name}")
        if type(status["started_realtime_ns"]) is not int or type(status["ended_realtime_ns"]) is not int:
            fail(f"smoke timestamps are malformed: {name}")
        if status["ended_realtime_ns"] <= status["started_realtime_ns"]:
            fail(f"smoke interval is not positive: {name}")
        result = parse_native_line(stdout)
        spec = {"sequence": f"smoke:{name}", "label": "smoke", "block": 0, "period": 0, "mode": mode}
        validate_result(result, spec, selected)


def validate_campaign_receipts(root: Path, selected: dict[str, int], binary_digest: str) -> None:
    campaign_text = (root / "campaign.txt").read_text(encoding="utf-8")
    lines = campaign_text.splitlines()
    if len(lines) != 1:
        fail("campaign launcher receipt must contain one JSON line")
    campaign = strict_json(lines[0])
    if not isinstance(campaign, dict) or campaign.get("binary_sha256") != binary_digest or campaign.get(
        "selected"
    ) != selected:
        fail("campaign launcher receipt changed")
    build_text = (root / "build.txt").read_text(encoding="utf-8")
    for marker in ("[compiler]", "[python]", "[build-command]", "-g", "-Werror", "lock_holder_preemption.c"):
        if marker not in build_text:
            fail(f"build summary lacks marker: {marker}")


def validate_seal(root: Path, result: dict[str, object], commit: str, target_label: str) -> None:
    manifest = parse_manifest(root / "MANIFEST.sha256")
    expected = expected_files(True) - {"MANIFEST.sha256", "SEALED"}
    if set(manifest) != expected:
        fail("sealed manifest path set changed")
    for relative, digest in manifest.items():
        if sha256(root / relative) != digest:
            fail(f"sealed file digest mismatch: {relative}")
    seal = read_json(root / "SEALED")
    expected_seal = {
        "schema": "topic50-seal.v1",
        "manifest_sha256": sha256(root / "MANIFEST.sha256"),
        "manifest_file_count": len(manifest),
        "source_commit": commit,
        "target_label": target_label,
    }
    if seal != expected_seal:
        fail("SEALED does not bind the retained manifest")
    retained = read_json(root / "receipt-validation.json")
    if not same(retained, result):
        fail("retained pre-seal validation differs from controller validation")


def validate_receipt(
    root: Path,
    *,
    target_label: str,
    expected_hostname: str,
    expected_architecture: str,
    commit: str,
    archive_digest: str,
    allow_unsealed: bool,
) -> dict[str, object]:
    if not HEX40.fullmatch(commit) or not HEX64.fullmatch(archive_digest):
        fail("controller source commitment is malformed")
    validate_tree(root, sealed=not allow_unsealed)
    payloads = validate_archive(root, commit, archive_digest)
    validate_sources(root, payloads, commit)
    validate_identity(root, target_label, expected_hostname, expected_architecture, commit, archive_digest)
    metadata, selected, binary_digest = validate_metadata(
        root, target_label, expected_hostname, expected_architecture, commit, archive_digest
    )
    native_name = f"systems-snackpack-{commit}/{TOPIC}/experiment/lock_holder_preemption.c"
    if hashlib.sha256(payloads[native_name]).hexdigest() != metadata["source_sha256"]:
        fail("campaign source digest differs from retained archive source")
    validate_schedule(root)
    rows = validate_attempts(root, selected, binary_digest)
    attempts = read_jsonl(root / "experiment/attempts.jsonl")
    validate_journal(root, attempts)
    validate_analysis(root, rows, binary_digest)
    validate_binary_and_codegen(root, expected_architecture, binary_digest)
    validate_smokes(root, selected)
    validate_campaign_receipts(root, selected, binary_digest)
    result = {
        "schema": "topic50-receipt-validation.v1",
        "status": "pass",
        "target_label": target_label,
        "hostname": expected_hostname,
        "architecture": expected_architecture,
        "source_commit": commit,
        "source_archive_sha256": archive_digest,
        "binary_sha256": binary_digest,
        "attempt_count": 64,
        "fresh_pid_count": 64,
        "primary_blocks": 8,
        "aa_blocks": 8,
        "periods_per_block": 4,
        "analysis_unit": "one complete four-period block log contrast",
        "failed_attempts": 0,
        "source_mutation": False,
    }
    if not allow_unsealed:
        validate_seal(root, result, commit, target_label)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone validation of an exact-source Topic 50 receipt.")
    parser.add_argument("receipt_dir", type=Path)
    parser.add_argument("--expected-target-label", required=True)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-architecture", choices=("aarch64", "x86_64"), required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-source-archive-sha256", required=True)
    parser.add_argument("--allow-unsealed", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate_receipt(
            args.receipt_dir.resolve(),
            target_label=args.expected_target_label,
            expected_hostname=args.expected_hostname,
            expected_architecture=args.expected_architecture,
            commit=args.expected_source_commit.lower(),
            archive_digest=args.expected_source_archive_sha256.lower(),
            allow_unsealed=args.allow_unsealed,
        )
    except (OSError, ValueError, KeyError, TypeError, csv.Error, tarfile.TarError) as error:
        raise SystemExit(f"Topic 50 receipt validation failed: {error}") from error
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
