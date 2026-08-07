#!/usr/bin/env python3
"""Independently validate a retained Topic 26 evidence directory."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_processes import MEASUREMENT_KEYS

SEGMENT_BYTES = 1200
SEGMENTS_PER_BATCH = 32
MEASURED_ROUNDS = 1000
WARMUP_ROUNDS = 100
GRO_CONTROL_ROUNDS = 4
AB_BLOCKS_PER_COMPARISON = 8
AA_BLOCKS = 4
SCHEDULE_SEED = 26_202_608_05
TIMEOUT_SECONDS = 120
SOURCE_ARCHIVE_PATHS = ("Cargo.toml", "Cargo.lock", "topics/026-nic-datapath")
FIXED_ATTEMPTS = 2 * AB_BLOCKS_PER_COMPARISON * 4 + AA_BLOCKS * 4 + 2
IDENTITY_KEYS = {
    "sequence",
    "family",
    "comparison",
    "block",
    "template",
    "position",
    "label",
}
ATTEMPT_EXTRA_KEYS = {
    "mode",
    "gro_enabled",
    "command",
    "timeout_seconds",
    "timed_out",
    "spawn_error",
    "returncode",
    "process_ns",
    "stdout",
    "stderr",
    "parse_status",
    "parse_error",
}
DESIGN_KEYS = {
    "schema",
    "binary_sha256",
    "transport",
    "segment_bytes",
    "segments_per_batch",
    "measured_rounds_per_primary_process",
    "warmup_rounds_per_primary_process",
    "gro_control_rounds",
    "schedule_seed",
    "primary_schedule",
    "aa_schedule",
    "gro_control_schedule",
    "fixed_attempt_count",
    "treatment_application_unit",
    "randomization_unit",
    "analysis_unit",
    "subsamples",
    "assignment",
    "stopping",
    "invalid_attempt_policy",
    "primary_receive_semantics",
    "estimands",
    "interval",
    "aa_scope",
    "gro_control_scope",
    "timing_boundary",
}
T_CRITICAL = {4: 3.182446305, 8: 2.364624251}


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        values = [json.loads(line) for line in lines]
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not values or not all(isinstance(value, dict) for value in values):
        fail(f"{path} must contain JSON objects")
    return values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(observed: float, expected: float, name: str) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12):
        fail(f"{name} differs: {observed!r} != {expected!r}")


def parse_one_json_line(text: str, name: str) -> dict[str, Any]:
    if not isinstance(text, str) or not text.endswith("\n") or text.count("\n") != 1:
        fail(f"{name} is not exactly one newline-terminated JSON line")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        fail(f"{name} contains invalid JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{name} JSON must be an object")
    return value


def require_int(value: Any, name: str, *, positive: bool = False) -> int:
    if type(value) is not int:
        fail(f"{name} must be an integer")
    if positive and value <= 0:
        fail(f"{name} must be positive")
    return value


def expected_payload_checksum(total_rounds: int) -> int:
    checksum = 0
    for round_index in range(total_rounds):
        for slot in range(SEGMENTS_PER_BATCH):
            receipt = (round_index << 32) ^ (slot << 16) ^ SEGMENT_BYTES
            checksum = (checksum + receipt) & ((1 << 64) - 1)
    return checksum


def validate_measurement(
    value: dict[str, Any],
    *,
    mode: str,
    gro_enabled: bool,
    measured_rounds: int,
    warmup_rounds: int,
) -> None:
    if set(value) != MEASUREMENT_KEYS:
        fail(f"measurement fields differ: {sorted(set(value) ^ MEASUREMENT_KEYS)}")
    fixed = {
        "schema": 1,
        "kind": "measurement",
        "status": "pass",
        "mode": mode,
        "gro_enabled": gro_enabled,
        "transport": "udp_ipv4_loopback",
        "segment_bytes": SEGMENT_BYTES,
        "segments_per_batch": SEGMENTS_PER_BATCH,
        "warmup_rounds": warmup_rounds,
        "measured_rounds": measured_rounds,
    }
    for field, expected in fixed.items():
        if value.get(field) != expected or type(value.get(field)) is not type(expected):
            fail(f"measurement {field} differs")

    logical_datagrams = measured_rounds * SEGMENTS_PER_BATCH
    verified_datagrams = (measured_rounds + warmup_rounds) * SEGMENTS_PER_BATCH
    checksum = expected_payload_checksum(measured_rounds + warmup_rounds)
    derived = {
        "logical_datagrams": logical_datagrams,
        "logical_bytes": logical_datagrams * SEGMENT_BYTES,
        "verified_datagrams": verified_datagrams,
        "payload_checksum": checksum,
        "expected_payload_checksum": checksum,
        "payload_verified": True,
    }
    for field, expected in derived.items():
        if value.get(field) != expected or type(value.get(field)) is not type(expected):
            fail(f"measurement {field} differs")

    for field in (
        "setup_ns",
        "elapsed_ns",
        "data_send_syscalls",
        "data_receive_syscalls",
        "actual_receive_buffer",
        "actual_send_buffer",
    ):
        require_int(value.get(field), field, positive=True)
    for field in (
        "user_cpu_ns",
        "system_cpu_ns",
        "gro_control_messages",
        "max_gro_segments_per_receive",
    ):
        if require_int(value.get(field), field) < 0:
            fail(f"{field} must be nonnegative")
    for field in (
        "sender_cpu",
        "receiver_cpu",
        "sender_observed_cpu",
        "receiver_observed_cpu",
        "sender_affinity_count",
        "receiver_affinity_count",
    ):
        require_int(value.get(field), field)

    if value["sender_cpu"] == value["receiver_cpu"]:
        fail("sender and receiver CPUs are not distinct")
    if (
        value["sender_observed_cpu"] != value["sender_cpu"]
        or value["receiver_observed_cpu"] != value["receiver_cpu"]
        or value["sender_affinity_count"] != 1
        or value["receiver_affinity_count"] != 1
    ):
        fail("CPU-affinity receipt differs")
    if not (
        measured_rounds
        <= value["data_receive_syscalls"]
        <= logical_datagrams
    ):
        fail("data receive syscall count is outside possible bounds")
    minimum_send_calls = logical_datagrams if mode == "scalar" else measured_rounds
    if value["data_send_syscalls"] < minimum_send_calls:
        fail("data send syscall count is below the mode minimum")

    if gro_enabled:
        if mode != "udp_segment":
            fail("UDP_GRO control used a non-UDP_SEGMENT sender")
        if value["gro_control_messages"] < measured_rounds or (
            value["max_gro_segments_per_receive"] <= 1
        ):
            fail("UDP_GRO control did not observe coalesced delivery")
    elif (
        value["gro_control_messages"] != 0
        or value["max_gro_segments_per_receive"] != 0
    ):
        fail("no-GRO path reports UDP_GRO delivery")

    observed = value.get("ns_per_datagram")
    if not isinstance(observed, (int, float)) or isinstance(observed, bool):
        fail("ns_per_datagram is not numeric")
    expected = value["elapsed_ns"] / logical_datagrams
    if not math.isclose(float(observed), expected, rel_tol=1e-9, abs_tol=1e-6):
        fail("ns_per_datagram differs from elapsed/datagrams")


def interval(contrasts: list[float]) -> dict[str, float | int]:
    if len(contrasts) not in T_CRITICAL:
        fail(f"no declared critical value for {len(contrasts)} blocks")
    mean = statistics.fmean(contrasts)
    deviation = statistics.stdev(contrasts)
    half = T_CRITICAL[len(contrasts)] * deviation / math.sqrt(len(contrasts))
    return {
        "n_complete_blocks": len(contrasts),
        "geometric_mean_ratio": math.exp(mean),
        "log_t_95_low": math.exp(mean - half),
        "log_t_95_high": math.exp(mean + half),
        "mean_log_contrast": mean,
        "log_sd": deviation,
    }


def compare_interval(
    observed: dict[str, Any],
    expected: dict[str, float | int],
    name: str,
    *,
    scope: str | None = None,
) -> None:
    expected_keys = set(expected) | ({"scope"} if scope is not None else set())
    if not isinstance(observed, dict) or set(observed) != expected_keys:
        fail(f"{name} interval fields differ")
    for field, value in expected.items():
        if field == "n_complete_blocks":
            if observed[field] != value:
                fail(f"{name}.{field} differs")
        else:
            close(observed[field], value, f"{name}.{field}")
    if scope is not None and observed.get("scope") != scope:
        fail(f"{name}.scope differs")


def verify_source_archive(evidence: Path, identity_lines: list[str]) -> None:
    archive = evidence / "source.tar.gz"
    if not archive.is_file():
        fail("source archive is absent")
    observed = sha256(archive)
    recorded_path = evidence / "source-archive.sha256"
    if not recorded_path.is_file():
        fail("source archive digest is absent")
    recorded = recorded_path.read_text(encoding="utf-8").split()
    if not recorded or recorded[0] != observed:
        fail("source archive differs from source-archive.sha256")
    for line in identity_lines:
        if line.startswith("source_archive_sha256="):
            if line.split("=", 1)[1].strip() != observed:
                fail("source archive differs from source identity")
            return
    fail("source identity lacks the source archive digest")


def experiment_digests_from_archive(evidence: Path) -> dict[str, str]:
    prefix = "topics/026-nic-datapath/experiment/"
    digests: dict[str, str] = {}
    with tarfile.open(evidence / "source.tar.gz", "r:gz") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith(prefix):
                handle = archive.extractfile(member)
                if handle is None:
                    fail(f"unreadable archive member: {member.name}")
                digests[Path(member.name).name] = hashlib.sha256(
                    handle.read()
                ).hexdigest()
    return digests


def normalized_tar_entries(data: bytes, name: str) -> dict[str, tuple[str, int, bytes]]:
    """Return tracked file and symlink content without tar-format metadata."""
    entries: dict[str, tuple[str, int, bytes]] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            for member in archive.getmembers():
                if member.isdir():
                    continue
                if member.isfile():
                    handle = archive.extractfile(member)
                    if handle is None:
                        fail(f"unreadable regular file in {name}: {member.name}")
                    kind = "file"
                    content = handle.read()
                elif member.issym():
                    kind = "symlink"
                    content = member.linkname.encode("utf-8")
                else:
                    fail(f"unsupported archive member in {name}: {member.name}")
                if member.name in entries:
                    fail(f"duplicate archive member in {name}: {member.name}")
                entries[member.name] = (kind, member.mode & 0o777, content)
    except tarfile.TarError as error:
        fail(f"cannot parse {name}: {error}")
    return entries


def verify_source_identity(
    evidence: Path, source_root: Path, binary_digest: str
) -> None:
    binary_line = (evidence / "binary.sha256").read_text(
        encoding="utf-8"
    ).split()
    if not binary_line or binary_line[0] != binary_digest:
        fail("binary SHA-256 differs from experiment design")

    identity_lines = (evidence / "source-identity.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    recorded = None
    recorded_tree = None
    recorded_scope = None
    for line in identity_lines:
        if line.startswith("source_commit="):
            recorded = line.split("=", 1)[1].strip()
        elif line.startswith("source_tree="):
            recorded_tree = line.split("=", 1)[1].strip()
        elif line.startswith("source_archive_scope="):
            recorded_scope = line.split("=", 1)[1].strip()
    def is_hex_digest(candidate: str) -> bool:
        return len(candidate) in {40, 64} and all(
            character in "0123456789abcdef" for character in candidate
        )

    if recorded is None or not is_hex_digest(recorded):
        fail("source identity lacks a recorded source commit")
    if recorded_tree is None or not is_hex_digest(recorded_tree):
        fail("source identity lacks a recorded source tree")
    if recorded_scope != " ".join(SOURCE_ARCHIVE_PATHS):
        fail("source identity has the wrong archive scope")
    verify_source_archive(evidence, identity_lines)
    archive_digests = experiment_digests_from_archive(evidence)

    # The validating repository may lack the recorded collection commit
    # (shallow clone, squash merge). When the commit is reachable, bind the
    # receipts to its blobs; otherwise rely on the retained source archive,
    # which verify_source_archive binds to both recorded digests.
    commit_reachable = subprocess.run(
        [
            "git",
            "-C",
            str(source_root),
            "cat-file",
            "-e",
            f"{recorded}^{{commit}}",
        ],
        capture_output=True,
        check=False,
    ).returncode == 0
    if commit_reachable:
        tree = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", f"{recorded}^{{tree}}"],
            capture_output=True,
            check=False,
            text=True,
        )
        if tree.returncode != 0 or tree.stdout.strip() != recorded_tree:
            fail("recorded source tree differs from the source commit")
        archived = subprocess.run(
            [
                "git",
                "-C",
                str(source_root),
                "archive",
                "--format=tar",
                recorded,
                "--",
                *SOURCE_ARCHIVE_PATHS,
            ],
            capture_output=True,
            check=False,
        )
        if archived.returncode != 0:
            fail("cannot archive the recorded source commit")
        try:
            retained_tar = gzip.decompress((evidence / "source.tar.gz").read_bytes())
        except (OSError, EOFError) as error:
            fail(f"cannot decompress retained source archive: {error}")
        if normalized_tar_entries(retained_tar, "retained source archive") != (
            normalized_tar_entries(archived.stdout, "recorded commit archive")
        ):
            fail("retained source archive differs from the recorded topic source")

    expected_files = {
        "udp_batch.c",
        "run_processes.py",
        "validate_receipts.py",
        "run_host.sh",
    }
    found: set[str] = set()
    for line in identity_lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            continue
        name = Path(parts[1].strip()).name
        if name not in expected_files:
            continue
        if archive_digests.get(name) != parts[0]:
            fail(f"source archive identity differs for {name}")
        if commit_reachable:
            blob = subprocess.run(
                [
                    "git",
                    "-C",
                    str(source_root),
                    "show",
                    f"{recorded}:topics/026-nic-datapath/experiment/{name}",
                ],
                capture_output=True,
                check=False,
            )
            if blob.returncode != 0:
                fail(f"recorded source commit lacks {name}")
            if hashlib.sha256(blob.stdout).hexdigest() != parts[0]:
                fail(f"recorded source identity differs for {name}")
        found.add(name)
    if found != expected_files:
        fail("source identity does not cover every experiment file")


def verify_evidence_manifest(evidence: Path) -> None:
    manifest_path = evidence / "evidence.sha256"
    status_path = evidence / "run.status"
    if not manifest_path.is_file():
        if status_path.exists():
            fail("run.status is present but evidence.sha256 is missing")
        return
    if not status_path.is_file():
        fail("sealed bundle lacks run.status")
    before = evidence / "source-files.before.sha256"
    after = evidence / "source-files.after.sha256"
    if not before.is_file() or not after.is_file():
        fail("sealed bundle lacks a before or after source manifest")
    if before.read_bytes() != after.read_bytes():
        fail("before and after source manifests differ")
    status_lines = status_path.read_text(encoding="utf-8").splitlines()
    if "exit=0" not in status_lines or "source_manifest=match" not in status_lines:
        fail("run.status does not record a clean, source-stable run")

    listed: set[str] = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            fail("malformed evidence manifest line")
        name = parts[1].strip()
        target = (evidence / name).resolve()
        if evidence.resolve() not in target.parents:
            fail(f"evidence manifest escapes the bundle: {name}")
        if not target.is_file() or sha256(target) != parts[0]:
            fail(f"evidence hash differs for {name}")
        listed.add(str(target))
    for path in evidence.rglob("*"):
        if path.is_file() and path.name != "evidence.sha256":
            if str(path.resolve()) not in listed:
                fail(f"retained file is not sealed: {path.relative_to(evidence)}")


def validate_design(design: dict[str, Any]) -> None:
    if set(design) != DESIGN_KEYS:
        fail(f"design fields differ: {sorted(set(design) ^ DESIGN_KEYS)}")
    fixed = {
        "schema": 1,
        "transport": "UDP/IPv4 loopback",
        "segment_bytes": SEGMENT_BYTES,
        "segments_per_batch": SEGMENTS_PER_BATCH,
        "measured_rounds_per_primary_process": MEASURED_ROUNDS,
        "warmup_rounds_per_primary_process": WARMUP_ROUNDS,
        "gro_control_rounds": GRO_CONTROL_ROUNDS,
        "schedule_seed": SCHEDULE_SEED,
        "fixed_attempt_count": FIXED_ATTEMPTS,
    }
    for field, expected in fixed.items():
        if design.get(field) != expected:
            fail(f"design {field} differs")
    if (
        not isinstance(design.get("binary_sha256"), str)
        or len(design["binary_sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in design["binary_sha256"]
        )
    ):
        fail("design binary digest is invalid")
    required_phrases = {
        "stopping": (
            "fixed 8 blocks",
            "4 A/A blocks",
            "no peeking, retry, or replacement",
        ),
        "invalid_attempt_policy": ("retain every attempt", "fails the run"),
        "primary_receive_semantics": ("UDP_GRO disabled",),
        "interval": ("Student-t", "complete-block", "run window"),
    }
    for field, phrases in required_phrases.items():
        if not all(phrase in design.get(field, "") for phrase in phrases):
            fail(f"design {field} does not state the required contract")


def validate_schedules(
    design: dict[str, Any], observations: list[dict[str, Any]]
) -> list[tuple[Any, ...]]:
    primary = design.get("primary_schedule")
    aa = design.get("aa_schedule")
    controls = design.get("gro_control_schedule")
    if not isinstance(primary, list) or len(primary) != 16:
        fail("primary schedule must contain two sets of eight blocks")
    if not isinstance(aa, list) or len(aa) != AA_BLOCKS:
        fail("A/A schedule must contain four blocks")
    if controls != [
        {"label": "gro_disabled", "mode": "udp_segment", "gro_enabled": False},
        {"label": "gro_enabled", "mode": "udp_segment", "gro_enabled": True},
    ]:
        fail("GRO semantic-control schedule differs")

    primary_specs = {
        "sendmmsg_over_scalar": (
            "scalar",
            "scalar",
            "sendmmsg",
            "sendmmsg",
        ),
        "udp_segment_over_scalar": (
            "scalar",
            "scalar",
            "udp_segment",
            "udp_segment",
        ),
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in primary:
        if set(block) != {
            "comparison",
            "baseline_label",
            "baseline_mode",
            "candidate_label",
            "candidate_mode",
            "block",
            "template",
        }:
            fail("primary schedule block fields differ")
        grouped[block["comparison"]].append(block)
    if set(grouped) != set(primary_specs):
        fail("primary comparisons differ")
    for comparison, blocks in grouped.items():
        expected_spec = primary_specs[comparison]
        for block in blocks:
            if [
                block["baseline_label"],
                block["baseline_mode"],
                block["candidate_label"],
                block["candidate_mode"],
            ] != list(expected_spec):
                fail(f"{comparison} treatment mapping differs")
        if [block["block"] for block in blocks] != list(
            range(1, AB_BLOCKS_PER_COMPARISON + 1)
        ):
            fail(f"{comparison} block identifiers differ")
        if Counter(block["template"] for block in blocks) != Counter(
            {"ABBA": 4, "BAAB": 4}
        ):
            fail(f"{comparison} is not position balanced")

    if Counter(block.get("template") for block in aa) != Counter(
        {"ABBA": 2, "BAAB": 2}
    ):
        fail("A/A schedule is not position balanced")
    for index, block in enumerate(aa, start=1):
        expected_block = {
            "comparison": "aa_right_over_aa_left",
            "baseline_label": "aa_left",
            "baseline_mode": "sendmmsg",
            "candidate_label": "aa_right",
            "candidate_mode": "sendmmsg",
            "block": index,
            "template": block["template"],
        }
        if block != expected_block:
            fail("A/A schedule mapping differs")

    expected: list[tuple[Any, ...]] = []
    sequence = 0
    for family, schedule in (("primary", primary), ("aa", aa)):
        for block in schedule:
            for position, letter in enumerate(block["template"], start=1):
                candidate = letter == "B"
                label = (
                    block["candidate_label"]
                    if candidate
                    else block["baseline_label"]
                )
                mode = (
                    block["candidate_mode"]
                    if candidate
                    else block["baseline_mode"]
                )
                expected.append(
                    (
                        sequence,
                        family,
                        block["comparison"],
                        block["block"],
                        block["template"],
                        position,
                        label,
                        mode,
                        False,
                    )
                )
                sequence += 1
    for position, gro_enabled in enumerate((False, True), start=1):
        expected.append(
            (
                sequence,
                "gro_control",
                "gro_semantics",
                1,
                "CG",
                position,
                "gro_enabled" if gro_enabled else "gro_disabled",
                "udp_segment",
                gro_enabled,
            )
        )
        sequence += 1
    observed = [
        (
            row["sequence"],
            row["family"],
            row["comparison"],
            row["block"],
            row["template"],
            row["position"],
            row["label"],
            row["mode"],
            row["gro_enabled"],
        )
        for row in observations
    ]
    if observed != expected:
        fail("observations differ from the fixed schedule or include replacements")
    return expected


def block_contrasts(
    observations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows_by_block: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        if row["family"] in {"primary", "aa"}:
            rows_by_block[
                (row["family"], row["comparison"], row["block"])
            ].append(row)
    result = []
    for (family, comparison, block), rows in rows_by_block.items():
        numerator, denominator = {
            "sendmmsg_over_scalar": ("sendmmsg", "scalar"),
            "udp_segment_over_scalar": ("udp_segment", "scalar"),
            "aa_right_over_aa_left": ("aa_right", "aa_left"),
        }[comparison]
        numerator_logs = [
            math.log(row["elapsed_ns"]) for row in rows if row["label"] == numerator
        ]
        denominator_logs = [
            math.log(row["elapsed_ns"])
            for row in rows
            if row["label"] == denominator
        ]
        if len(numerator_logs) != 2 or len(denominator_logs) != 2:
            fail("a complete block lacks two observations per label")
        contrast = statistics.fmean(numerator_logs) - statistics.fmean(
            denominator_logs
        )
        result.append(
            {
                "family": family,
                "comparison": comparison,
                "block": block,
                "template": rows[0]["template"],
                "log_contrast": contrast,
                "ratio": math.exp(contrast),
            }
        )
    return result


def validate_contrast_csv(
    path: Path, expected: list[dict[str, Any]]
) -> None:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [
            "family",
            "comparison",
            "block",
            "template",
            "log_contrast",
            "ratio",
        ]:
            fail("block contrast CSV fields differ")
        observed = list(reader)
    if len(observed) != len(expected):
        fail("block contrast CSV row count differs")
    for actual, wanted in zip(observed, expected):
        for field in ("family", "comparison", "template"):
            if actual[field] != wanted[field]:
                fail(f"block contrast {field} differs")
        if int(actual["block"]) != wanted["block"]:
            fail("block contrast block differs")
        close(float(actual["log_contrast"]), wanted["log_contrast"], "CSV log contrast")
        close(float(actual["ratio"]), wanted["ratio"], "CSV ratio")


def calculate_mode_diagnostics(
    observations: list[dict[str, Any]], mode: str
) -> dict[str, Any]:
    rows = [
        row
        for row in observations
        if row["family"] in {"primary", "aa"} and row["mode"] == mode
    ]
    return {
        "processes": len(rows),
        "median_ns_per_datagram": statistics.median(
            row["ns_per_datagram"] for row in rows
        ),
        "median_data_send_syscalls": statistics.median(
            row["data_send_syscalls"] for row in rows
        ),
        "median_data_receive_syscalls": statistics.median(
            row["data_receive_syscalls"] for row in rows
        ),
    }


def validate_summary(
    experiment: Path,
    design: dict[str, Any],
    summary: dict[str, Any],
    observations: list[dict[str, Any]],
) -> None:
    if set(summary) != {
        "schema",
        "binary_sha256",
        "attempt_count",
        "valid_observation_count",
        "primary_gro_enabled",
        "summaries",
        "mode_diagnostics",
        "gro_control",
    }:
        fail("summary fields differ")
    fixed = {
        "schema": 1,
        "binary_sha256": design["binary_sha256"],
        "attempt_count": FIXED_ATTEMPTS,
        "valid_observation_count": FIXED_ATTEMPTS,
        "primary_gro_enabled": False,
    }
    for field, expected in fixed.items():
        if summary.get(field) != expected:
            fail(f"summary {field} differs")

    contrasts = block_contrasts(observations)
    validate_contrast_csv(experiment / "block-contrasts.csv", contrasts)
    summary_intervals = summary.get("summaries")
    if not isinstance(summary_intervals, dict) or set(summary_intervals) != {
        "sendmmsg_over_scalar",
        "udp_segment_over_scalar",
        "aa_right_over_aa_left",
    }:
        fail("summary comparison set differs")
    for comparison in summary_intervals:
        expected = interval(
            [
                row["log_contrast"]
                for row in contrasts
                if row["comparison"] == comparison
            ]
        )
        compare_interval(
            summary_intervals[comparison],
            expected,
            comparison,
            scope=design["aa_scope"]
            if comparison == "aa_right_over_aa_left"
            else None,
        )

    diagnostics = summary.get("mode_diagnostics")
    if not isinstance(diagnostics, dict) or set(diagnostics) != {
        "scalar",
        "sendmmsg",
        "udp_segment",
    }:
        fail("mode diagnostic set differs")
    for mode in diagnostics:
        expected = calculate_mode_diagnostics(observations, mode)
        if set(diagnostics[mode]) != set(expected):
            fail(f"{mode} diagnostic fields differ")
        for field, value in expected.items():
            if field == "processes":
                if diagnostics[mode][field] != value:
                    fail(f"{mode} process count differs")
            else:
                close(diagnostics[mode][field], value, f"{mode}.{field}")

    gro_rows = [
        row for row in observations if row["family"] == "gro_control"
    ]
    if len(gro_rows) != 2:
        fail("GRO semantic control must have two observations")
    by_label = {row["label"]: row for row in gro_rows}
    gro_file = load_json(experiment / "gro-control.json")
    if set(gro_file) != {
        "schema",
        "scope",
        "gro_disabled",
        "gro_enabled",
        "same_logical_payload",
        "coalesced_delivery_observed",
        "timing_claim",
    }:
        fail("GRO semantic-control fields differ")
    if (
        gro_file["schema"] != 1
        or gro_file["scope"] != design["gro_control_scope"]
        or gro_file["gro_disabled"] != by_label["gro_disabled"]
        or gro_file["gro_enabled"] != by_label["gro_enabled"]
        or gro_file["same_logical_payload"] is not True
        or gro_file["coalesced_delivery_observed"] is not True
        or gro_file["timing_claim"] is not None
    ):
        fail("GRO semantic-control receipt differs")
    expected_gro_summary = {
        "same_logical_payload": True,
        "coalesced_delivery_observed": True,
        "timing_claim": None,
    }
    if summary.get("gro_control") != expected_gro_summary:
        fail("summary GRO control differs")


def validate_host_receipt(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required = (
        "architecture=",
        "kernel=",
        "online_cpu_count=",
        "\nuname\n",
        "\ncompiler\n",
        "\nlscpu\n",
        "\nnetwork_interfaces\n",
        "\nnetwork_sysctls\n",
        "\nnetwork_steering\n",
        "\nproc_softirqs\n",
        "\nproc_net_softnet_stat\n",
        ".driver=",
        ".driver_module_version=",
        "net/core/somaxconn=",
        "net/ipv4/tcp_max_syn_backlog=",
        "net/ipv4/tcp_moderate_rcvbuf=",
        "net/ipv4/tcp_rmem=",
        "net/ipv4/tcp_wmem=",
        "net/ipv4/tcp_syncookies=",
    )
    if not all(marker in text for marker in required):
        fail("host receipt lacks architecture, toolchain, NIC, or steering metadata")
    if "ethtool_status=available" not in text and (
        "ethtool_status=unavailable"
    ) not in text:
        fail("host receipt does not explicitly record ethtool availability")


def validate_codegen(evidence: Path) -> None:
    expected = {
        "codegen-scalar.txt": "topic26_send_scalar_batch",
        "codegen-sendmmsg.txt": "topic26_send_mmsg_batch",
        "codegen-udp-segment.txt": "topic26_send_gso_batch",
    }
    for name, symbol in expected.items():
        text = (evidence / name).read_text(encoding="utf-8")
        if f"<{symbol}>:" not in text:
            fail(f"{name} does not contain linked symbol {symbol}")
    if not (evidence / "codegen.txt.gz").is_file() or (
        evidence / "codegen.txt.gz"
    ).stat().st_size == 0:
        fail("full linked-image disassembly is absent")


def validate_smoke(evidence: Path) -> None:
    if (evidence / "control-smoke.stderr").stat().st_size != 0:
        fail("smoke control wrote to stderr")
    rows = load_jsonl(evidence / "control-smoke.jsonl")
    expected = [
        ("scalar", False),
        ("sendmmsg", False),
        ("udp_segment", False),
        ("udp_segment", True),
    ]
    if len(rows) != len(expected):
        fail("smoke control row count differs")
    for row, (mode, gro_enabled) in zip(rows, expected):
        validate_measurement(
            row,
            mode=mode,
            gro_enabled=gro_enabled,
            measured_rounds=2,
            warmup_rounds=0,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    source_root = args.source_root.resolve()
    experiment = evidence / "experiment"

    design = load_json(experiment / "design.json")
    summary = load_json(experiment / "summary.json")
    status = load_json(experiment / "run-status.json")
    attempts = load_jsonl(experiment / "attempts.jsonl")
    observations = load_jsonl(experiment / "observations.jsonl")
    validate_design(design)
    if status != {
        "schema": 1,
        "complete": True,
        "attempts": FIXED_ATTEMPTS,
        "valid_observations": FIXED_ATTEMPTS,
        "invalid_attempts": 0,
        "fixed_attempt_count": FIXED_ATTEMPTS,
    }:
        fail("run status differs from the fixed complete design")
    if len(attempts) != FIXED_ATTEMPTS or len(observations) != FIXED_ATTEMPTS:
        fail("attempt or observation count differs from fixed stopping")
    validate_schedules(design, observations)
    verify_source_identity(evidence, source_root, design["binary_sha256"])
    verify_evidence_manifest(evidence)

    for attempt, observation in zip(attempts, observations):
        if set(attempt) != IDENTITY_KEYS | ATTEMPT_EXTRA_KEYS:
            fail("attempt fields differ")
        if set(observation) != IDENTITY_KEYS | {"process_ns"} | MEASUREMENT_KEYS:
            fail("observation fields differ")
        if (
            attempt["returncode"] != 0
            or attempt["timed_out"] is not False
            or attempt["spawn_error"] != ""
            or attempt["stderr"] != ""
            or attempt["parse_status"] != "ok"
            or attempt["parse_error"] != ""
            or attempt["timeout_seconds"] != TIMEOUT_SECONDS
            or require_int(attempt["process_ns"], "attempt process_ns") <= 0
        ):
            fail("an attempted process did not pass")
        measured_rounds = (
            GRO_CONTROL_ROUNDS
            if attempt["family"] == "gro_control"
            else MEASURED_ROUNDS
        )
        warmup_rounds = (
            0 if attempt["family"] == "gro_control" else WARMUP_ROUNDS
        )
        command = attempt["command"]
        expected_command_tail = [
            attempt["mode"],
            str(measured_rounds),
            str(warmup_rounds),
        ] + (["--gro"] if attempt["gro_enabled"] else [])
        if (
            not isinstance(command, list)
            or len(command) != len(expected_command_tail) + 1
            or Path(command[0]).name != "udp-batch"
            or command[1:] != expected_command_tail
        ):
            fail("attempt command differs from its declared treatment")
        measurement = parse_one_json_line(attempt["stdout"], "attempt stdout")
        validate_measurement(
            measurement,
            mode=attempt["mode"],
            gro_enabled=attempt["gro_enabled"],
            measured_rounds=measured_rounds,
            warmup_rounds=warmup_rounds,
        )
        for field, value in measurement.items():
            if observation.get(field) != value:
                fail(f"observation differs from stdout for {field}")
        for field in IDENTITY_KEYS:
            if observation.get(field) != attempt.get(field):
                fail(f"observation identity differs for {field}")
        if observation["process_ns"] != attempt["process_ns"]:
            fail("observation process duration differs from attempt")

    aa_commands = {
        tuple(attempt["command"])
        for attempt in attempts
        if attempt["family"] == "aa"
    }
    if len(aa_commands) != 1:
        fail("A/A labels did not use an identical command path")
    primary = [row for row in observations if row["family"] == "primary"]
    if len(primary) != 64 or any(row["gro_enabled"] for row in primary):
        fail("primary timing path is not exactly 64 no-GRO processes")
    cpu_pairs = {
        (row["sender_cpu"], row["receiver_cpu"]) for row in observations
    }
    if len(cpu_pairs) != 1:
        fail("sender and receiver CPU pair changed during the fixed schedule")

    validate_summary(experiment, design, summary, observations)
    validate_smoke(evidence)
    validate_host_receipt(evidence / "host.txt")
    validate_codegen(evidence)

    required_gates = {
        "git-diff-check.log",
        "cargo-fmt.log",
        "cargo-test-lib-examples.log",
        "cargo-test-doc.log",
        "cargo-clippy.log",
        "cargo-bench-no-run.log",
        "cargo-doc.log",
        "script-syntax.log",
    }
    gates = evidence / "gates"
    if not gates.is_dir() or {path.name for path in gates.iterdir()} != required_gates:
        fail("workspace gate receipt set differs")

    print(
        json.dumps(
            {
                "status": "pass",
                "attempts": len(attempts),
                "complete_primary_blocks": 2 * AB_BLOCKS_PER_COMPARISON,
                "complete_aa_blocks": AA_BLOCKS,
                "source_identity": "match",
                "payloads": "verified",
                "affinity": "verified",
                "cpu_pair": list(next(iter(cpu_pairs))),
                "primary_gro": "disabled",
                "gro_control": "coalesced-delivery-observed",
                "codegen": "linked-symbols-present",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
