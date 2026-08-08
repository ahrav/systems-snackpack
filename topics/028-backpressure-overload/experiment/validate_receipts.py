#!/usr/bin/env python3
"""Validate Topic 28 schedules, raw receipts, semantic controls, and analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import build_analysis
from run_processes import (
    AA_TEMPLATES,
    CALLERS,
    CONTROL_SUMMARY_FIELDS,
    KEY_DIGEST,
    MAIN_TEMPLATES,
    MAX_ATTEMPTS,
    ORIGIN_CAPACITY,
    PROBE_SUMMARY_FIELDS,
    RETRY_TOKENS,
    SEMANTIC_CONTROL_SPECS,
    SUMMARY_FIELDS,
    TARGET_ATTEMPT_NS,
    WAITER_CAP,
    assignments,
    canonical_hash,
    parse_summary,
)

LOGICAL_FIELDS = (
    "logical_id",
    "pid",
    "phase",
    "block",
    "period",
    "label",
    "treatment",
    "key_digest",
    "role",
    "flight_id",
    "admission_ns",
    "settled_ns",
    "status",
    "result_digest",
)

ATTEMPT_FIELDS = (
    "pid",
    "phase",
    "block",
    "period",
    "label",
    "treatment",
    "flight_id",
    "attempt_no",
    "retry_token_charged",
    "retry_tokens_after",
    "queued_ns",
    "start_ns",
    "end_ns",
    "outcome",
    "active_at_start",
    "work_checksum",
)

MASK64 = (1 << 64) - 1


def require(condition: bool, message: str) -> None:
    """Stop at the first receipt violation."""
    if not condition:
        raise SystemExit(message)


def as_int(record: Any, field: str) -> int:
    """Convert one receipt field to an integer, stopping on malformed input."""
    try:
        return int(record[field])
    except (KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"malformed receipt field {field!r}: {error}") from error


def load_json(path: Path) -> Any:
    """Load one retained JSON document, stopping on malformed input."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"unreadable retained document {path.name}: {error}") from error


def read_receipt_text(path: Path) -> str:
    """Read one retained text receipt, stopping on a missing file."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise SystemExit(f"unreadable retained receipt {path.name}: {error}") from error


def read_csv(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    """Load one CSV and require its exact field order."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == expected_fields, f"wrong CSV schema: {path}")
        rows = list(reader)
    require(
        all(None not in row and None not in row.values() for row in rows),
        f"malformed CSV row: {path}",
    )
    return rows


def mix64(value: int) -> int:
    """Mirror the probe's wrapping seed mixer."""
    value &= MASK64
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & MASK64
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & MASK64
    return (value ^ (value >> 31)) & MASK64


def completed_digest(key_digest: int) -> int:
    """Mirror the deterministic completed-result digest."""
    return mix64(key_digest ^ 0x434F4D504C455445)


def exhausted_digest(key_digest: int) -> int:
    """Mirror the deterministic exhausted-result digest."""
    return mix64(key_digest ^ 0x4558484155535445)


def origin_work(iterations: int, seed: int) -> int:
    """Mirror the probe's calibrated origin work loop."""
    value = (seed ^ 0x9E3779B97F4A7C15) & MASK64
    for _ in range(iterations):
        value = (value * 0xD6E8FEB86659FD93 + 0xA0761D6478BD642F) & MASK64
        value ^= ((value << 23) | (value >> 41)) & MASK64
    return value


def work_seed(seed: int, flight_id: int, attempt_no: int) -> int:
    """Mirror the probe's per-attempt work-seed derivation."""
    return mix64((seed ^ ((flight_id * 0x9E3779B9) & MASK64) ^ attempt_no) & MASK64)


def calibration_checksum(iterations: int) -> int:
    """Mirror the probe's 512-repetition calibration checksum."""
    checksum = 0
    for repetition in range(512):
        checksum ^= origin_work(iterations, mix64((repetition + 28) & MASK64))
    return checksum


def require_equal(expected: Any, actual: Any, context: str) -> None:
    """Require recursive JSON equality with tight float tolerance."""
    if isinstance(expected, float) or isinstance(actual, float):
        require(
            isinstance(expected, (int, float))
            and isinstance(actual, (int, float))
            and math.isclose(float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-9),
            f"analysis mismatch at {context}",
        )
    elif isinstance(expected, dict):
        require(
            isinstance(actual, dict) and set(actual) == set(expected),
            f"keys differ at {context}",
        )
        for key in expected:
            require_equal(expected[key], actual[key], f"{context}.{key}")
    elif isinstance(expected, list):
        require(
            isinstance(actual, list) and len(actual) == len(expected),
            f"length differs at {context}",
        )
        for index, item in enumerate(expected):
            require_equal(item, actual[index], f"{context}[{index}]")
    else:
        require(expected == actual, f"value differs at {context}")


def modeled_counts(
    treatment: str, callers: int, waiter_cap: int, retry_tokens: int
) -> dict[str, int]:
    """Return the independent closed-form count model."""
    admitted = min(callers, waiter_cap)
    flights = admitted if treatment == "naive" else (1 if admitted != 0 else 0)
    attempts_per_flight = min(MAX_ATTEMPTS, retry_tokens + 1, 3)
    succeeds = attempts_per_flight == 3
    return {
        "completed": admitted if succeeds else 0,
        "retry_exhausted": 0 if succeeds else admitted,
        "shed": callers - admitted,
        "leaders": flights if treatment == "controlled" else 0,
        "followers": admitted - flights if treatment == "controlled" else 0,
        "flights": flights,
        "origin_attempts": flights * attempts_per_flight,
        "retry_attempts": flights * max(0, attempts_per_flight - 1),
        "transient_attempts": flights * min(attempts_per_flight, 2),
        "successful_attempts": flights if succeeds else 0,
        "peak_admitted": admitted,
    }


def retained_raw_path(directory: Path, recorded: str) -> Path:
    """Resolve a recorded raw path by basename inside the retained raw directory."""
    name = Path(recorded).name
    require(name not in ("", ".", ".."), "invalid retained raw basename")
    path = directory / "raw" / name
    require(path.is_file(), f"missing retained raw file: {name}")
    return path


def validate_process_receipts(
    directory: Path,
    summary: dict[str, str],
) -> dict[str, int]:
    """Recompute one process summary from its logical and physical receipts."""
    logical_path = retained_raw_path(directory, summary["logical_path"])
    attempt_path = retained_raw_path(directory, summary["attempt_path"])
    logical = read_csv(logical_path, LOGICAL_FIELDS)
    attempts = read_csv(attempt_path, ATTEMPT_FIELDS)

    callers = as_int(summary, "callers")
    waiter_cap = as_int(summary, "waiter_cap")
    origin_capacity = as_int(summary, "origin_capacity")
    max_attempts = as_int(summary, "max_attempts")
    retry_tokens = as_int(summary, "retry_tokens")
    key_digest = as_int(summary, "key_digest")
    seed = as_int(summary, "seed")
    work_iters = as_int(summary, "work_iters")
    treatment = summary["treatment"]
    require(len(logical) == callers, "logical receipt population differs from callers")
    logical_ids = [as_int(row, "logical_id") for row in logical]
    require(logical_ids == list(range(callers)), "logical IDs are not unique contiguous IDs")
    require(max_attempts == MAX_ATTEMPTS, "maximum attempts changed")
    require(origin_capacity == ORIGIN_CAPACITY, "origin capacity changed")
    require(key_digest == KEY_DIGEST, "one-key identity changed")
    require(as_int(summary, "work_iters") > 0, "work iterations are not positive")
    require(as_int(summary, "burst_ns") > 0, "burst duration is not positive")
    require(as_int(summary, "setup_ns") > 0, "setup duration is not positive")

    identity_fields = ("pid", "phase", "block", "period", "label", "treatment")
    for row in logical:
        for field in identity_fields:
            require(row[field] == summary[field], f"logical {field} differs from summary")
        require(row["key_digest"] == summary["key_digest"], "logical key digest differs")
    for row in attempts:
        for field in identity_fields:
            require(row[field] == summary[field], f"attempt {field} differs from summary")

    attempts_by_flight: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in attempts:
        flight_id = as_int(row, "flight_id")
        attempts_by_flight[flight_id].append(row)
        queued_ns = as_int(row, "queued_ns")
        start_ns = as_int(row, "start_ns")
        end_ns = as_int(row, "end_ns")
        require(0 <= queued_ns <= start_ns < end_ns, "attempt timestamps are not strictly ordered")
        active = as_int(row, "active_at_start")
        require(1 <= active <= origin_capacity, "origin active count exceeds permit cap")
        require(row["outcome"] in ("transient", "success"), "unknown attempt outcome")
        require(
            as_int(row, "work_checksum")
            == origin_work(work_iters, work_seed(seed, flight_id, as_int(row, "attempt_no"))),
            "work checksum does not match the calibrated origin loop",
        )

    # The recorded active counter cannot prove cap conformance; interval overlap validates the origin cap.
    active_attempts = 0
    for _, delta in sorted(
        event
        for row in attempts
        for event in ((as_int(row, "start_ns"), 1), (as_int(row, "end_ns"), -1))
    ):
        active_attempts += delta
        require(
            active_attempts <= origin_capacity,
            "physical attempt intervals exceed the origin cap",
        )

    if attempts:
        first_queue_ns = min(as_int(row, "queued_ns") for row in attempts)
        require(
            max(as_int(row, "admission_ns") for row in logical) <= first_queue_ns,
            "physical attempts began before every admission decision",
        )

    for flight_id, flight_attempts in attempts_by_flight.items():
        flight_attempts.sort(key=lambda row: as_int(row, "attempt_no"))
        numbers = [as_int(row, "attempt_no") for row in flight_attempts]
        require(
            numbers == list(range(1, len(flight_attempts) + 1)),
            f"flight {flight_id} does not contain an exact attempt prefix",
        )
        require(len(numbers) <= max_attempts, "flight exceeded maximum attempts")
        previous_end = -1
        for row in flight_attempts:
            attempt_no = as_int(row, "attempt_no")
            charged = as_int(row, "retry_token_charged")
            tokens_after = as_int(row, "retry_tokens_after")
            require(charged == (1 if attempt_no > 1 else 0), "retry-token charge flag is wrong")
            require(
                tokens_after == retry_tokens - max(0, attempt_no - 1),
                "retry-token balance is wrong",
            )
            require(tokens_after >= 0, "retry-token balance is negative")
            expected_outcome = "success" if attempt_no == 3 else "transient"
            require(row["outcome"] == expected_outcome, "synthetic outcome prefix changed")
            require(as_int(row, "queued_ns") >= previous_end, "one flight's attempts overlap")
            previous_end = as_int(row, "end_ns")

    success_digest = completed_digest(key_digest)
    error_digest = exhausted_digest(key_digest)
    statuses = defaultdict(int)
    roles = defaultdict(int)
    checksum = 0
    for row in logical:
        admission_ns = as_int(row, "admission_ns")
        settled_ns = as_int(row, "settled_ns")
        require(0 <= admission_ns <= settled_ns, "logical timestamps are not monotone")
        require(settled_ns <= as_int(summary, "burst_ns"), "logical settled after burst end")
        status = row["status"]
        role = row["role"]
        require(status in ("completed", "retry_exhausted", "shed"), "unknown logical status")
        require(role in ("independent", "leader", "follower", "shed"), "unknown role")
        statuses[status] += 1
        roles[role] += 1
        if status == "shed":
            require(role == "shed", "shed logical caller has a non-shed role")
            require(not row["flight_id"] and not row["result_digest"], "shed caller has flight work")
            continue
        require(bool(row["flight_id"]), "admitted caller has no flight")
        flight_id = as_int(row, "flight_id")
        require(flight_id in attempts_by_flight, "logical caller refers to missing flight")
        flight_end = max(as_int(attempt, "end_ns") for attempt in attempts_by_flight[flight_id])
        require(
            settled_ns >= flight_end,
            "logical caller settled before its flight's final attempt ended",
        )
        digest = as_int(row, "result_digest")
        checksum = (checksum + mix64(digest ^ as_int(row, "logical_id"))) & MASK64
        outcomes = [attempt["outcome"] for attempt in attempts_by_flight[flight_id]]
        if status == "completed":
            require(outcomes.count("success") == 1, "completed caller lacks one successful flight")
            require(digest == success_digest, "completed result digest is not deterministic")
        else:
            require("success" not in outcomes, "exhausted caller's flight succeeded")
            require(digest == error_digest, "exhausted result digest was not propagated")

    if treatment == "naive":
        require(roles["leader"] == roles["follower"] == 0, "naive role taxonomy changed")
        require(roles["independent"] == callers - statuses["shed"], "naive independent count differs")
        non_shed_flights = {
            as_int(row, "flight_id") for row in logical if row["status"] != "shed"
        }
        require(len(non_shed_flights) == callers - statuses["shed"], "naive callers share a flight")
    else:
        require(roles["independent"] == 0, "controlled caller is marked independent")
        require(roles["leader"] == (1 if callers > statuses["shed"] else 0), "controlled leader count differs")
        require(
            roles["follower"] == callers - statuses["shed"] - roles["leader"],
            "controlled follower count differs",
        )

    recomputed = {
        "completed": statuses["completed"],
        "retry_exhausted": statuses["retry_exhausted"],
        "shed": statuses["shed"],
        "leaders": roles["leader"],
        "followers": roles["follower"],
        "flights": len(attempts_by_flight),
        "origin_attempts": len(attempts),
        "retry_attempts": sum(as_int(row, "retry_token_charged") for row in attempts),
        "transient_attempts": sum(row["outcome"] == "transient" for row in attempts),
        "successful_attempts": sum(row["outcome"] == "success" for row in attempts),
        "peak_origin_active": max(
            (as_int(row, "active_at_start") for row in attempts), default=0
        ),
        "peak_admitted": callers - statuses["shed"],
        "result_checksum": checksum,
    }
    for field in (
        "completed",
        "shed",
        "leaders",
        "followers",
        "flights",
        "origin_attempts",
        "retry_attempts",
        "transient_attempts",
        "successful_attempts",
        "peak_origin_active",
        "peak_admitted",
        "result_checksum",
    ):
        require(as_int(summary, field) == recomputed[field], f"summary {field} differs from raw")
    require(recomputed["peak_origin_active"] <= origin_capacity, "origin peak exceeds capacity")
    if treatment == "controlled":
        require(recomputed["peak_admitted"] <= waiter_cap, "controlled admitted peak exceeds W")
    expected = modeled_counts(treatment, callers, waiter_cap, retry_tokens)
    for field, value in expected.items():
        require(recomputed[field] == value, f"runtime {field} differs from closed-form model")
    require(
        max((as_int(row, "end_ns") for row in attempts), default=0)
        <= as_int(summary, "burst_ns"),
        "physical attempt ended after burst timing",
    )
    return recomputed


def main() -> None:
    """Validate one completed per-host process directory."""
    parser = argparse.ArgumentParser()
    parser.add_argument("process_directory", type=Path)
    args = parser.parse_args()
    directory = args.process_directory

    schedule_document = load_json(directory / "schedule.json")
    expected_assignments = list(assignments())
    require(schedule_document["main_templates"] == list(MAIN_TEMPLATES), "main templates changed")
    require(schedule_document["aa_templates"] == list(AA_TEMPLATES), "A/A templates changed")
    require(schedule_document["replacement_policy"].startswith("none"), "replacement policy changed")
    scheduled = schedule_document["assignments"]
    require(len(scheduled) == len(expected_assignments) == 48, "schedule is not 48 periods")
    binary_hash = schedule_document["binary_sha256"]
    settings_hash = schedule_document["settings_sha256"]
    require(canonical_hash(schedule_document["settings"]) == settings_hash, "settings hash differs")
    try:
        settings_bytes = (directory / "settings.json").read_bytes()
    except OSError as error:
        raise SystemExit(f"unreadable retained document settings.json: {error}") from error
    require(hashlib.sha256(settings_bytes).hexdigest() == settings_hash, "settings file hash differs")
    require(
        read_receipt_text(directory / "settings.sha256").strip()
        == f"{settings_hash}  settings.json",
        "settings hash receipt differs",
    )
    require(
        read_receipt_text(directory / "binary.sha256").split()[0]
        == binary_hash,
        "binary hash receipt differs",
    )
    parent_binary_receipt = directory.parent / "binary.sha256"
    if parent_binary_receipt.is_file():
        require(
            read_receipt_text(parent_binary_receipt).split()[0] == binary_hash,
            "process binary differs from the retained host artifact",
        )
    require(
        schedule_document["settings"]
        == {
            "callers": CALLERS,
            "key_digest": KEY_DIGEST,
            "max_attempts": MAX_ATTEMPTS,
            "origin_capacity": ORIGIN_CAPACITY,
            "retry_tokens": RETRY_TOKENS,
            "target_attempt_ns": TARGET_ATTEMPT_NS,
            "waiter_cap": WAITER_CAP,
            "work_iters": schedule_document["settings"]["work_iters"],
        },
            "timing settings changed",
        )
    schedule_work_iters = as_int(schedule_document["settings"], "work_iters")
    require(schedule_work_iters > 0, "sealed work iterations are not positive")

    calibration = read_csv(
        directory / "calibration.csv",
        (
            "target_attempt_ns",
            "work_iters",
            "calibrated_mean_ns",
            "calibration_checksum",
            "binary_sha256",
            "settings_sha256",
        ),
    )
    require(len(calibration) == 1, "calibration must contain one row")
    calibration_row = calibration[0]
    require(as_int(calibration_row, "target_attempt_ns") == TARGET_ATTEMPT_NS, "target changed")
    require(
        as_int(calibration_row, "work_iters") == schedule_work_iters,
        "calibration iterations differ from the sealed settings",
    )
    require(as_int(calibration_row, "calibrated_mean_ns") > 0, "invalid calibration duration")
    require(
        as_int(calibration_row, "calibration_checksum")
        == calibration_checksum(schedule_work_iters),
        "calibration checksum does not match the calibrated origin loop",
    )
    require(calibration_row["binary_sha256"] == binary_hash, "calibration binary differs")
    require(calibration_row["settings_sha256"] == settings_hash, "calibration settings differ")

    summaries = read_csv(directory / "summaries.csv", SUMMARY_FIELDS)
    require(len(summaries) == 48, "summary process count is not 48")
    seen_pids: set[str] = set()
    for position, (expected, assignment, summary) in enumerate(
        zip(expected_assignments, scheduled, summaries), start=1
    ):
        for field in ("phase", "block", "template", "period", "label", "treatment", "seed"):
            require(assignment[field] == expected[field], f"schedule period {position} wrong {field}")
        require(assignment["binary_sha256"] == binary_hash, "schedule binary hash differs")
        require(assignment["settings_sha256"] == settings_hash, "schedule settings hash differs")
        for field in ("phase", "label", "treatment", "template"):
            require(summary[field] == str(expected[field]), f"summary period {position} wrong {field}")
        for field in ("block", "period", "seed"):
            require(as_int(summary, field) == as_int(expected, field), f"summary period {position} wrong {field}")
        require(summary["binary_sha256"] == binary_hash, "summary binary hash differs")
        require(summary["settings_sha256"] == settings_hash, "summary settings hash differs")
        require(as_int(summary, "callers") == CALLERS, "scheduled callers changed")
        require(as_int(summary, "waiter_cap") == WAITER_CAP, "scheduled waiter cap changed")
        require(as_int(summary, "retry_tokens") == RETRY_TOKENS, "scheduled retry budget changed")
        require(
            as_int(summary, "work_iters") == schedule_work_iters,
            "scheduled work iterations differ from the sealed settings",
        )
        require(summary["pid"] not in seen_pids, "scheduled process PID was reused")
        seen_pids.add(summary["pid"])
        require(
            as_int(summary, "process_started_utc_ns")
            <= as_int(summary, "process_ended_utc_ns"),
            "process timestamps are not monotone",
        )
        require(as_int(summary, "process_wall_ns") > 0, "process wall time is not positive")
        validate_process_receipts(directory, summary)

    controls = read_csv(directory / "semantic-controls.csv", CONTROL_SUMMARY_FIELDS)
    control_specs = schedule_document["semantic_controls"]
    require(len(controls) == len(control_specs) == 2, "semantic controls are incomplete")
    for spec, predeclared in zip(control_specs, SEMANTIC_CONTROL_SPECS):
        require(
            {key: spec.get(key) for key in predeclared} == predeclared,
            "semantic control specification differs from the predeclared controls",
        )
    for spec, summary in zip(control_specs, controls):
        require(summary["control_id"] == spec["control_id"], "semantic control identity differs")
        for field in ("phase", "label", "treatment"):
            require(summary[field] == str(spec[field]), f"semantic control wrong {field}")
        for field in ("block", "period", "seed", "callers", "waiter_cap", "retry_tokens"):
            require(as_int(summary, field) == as_int(spec, field), f"semantic control wrong {field}")
        require(summary["binary_sha256"] == binary_hash, "semantic control binary differs")
        require(
            summary["control_settings_sha256"] == spec["control_settings_sha256"],
            "semantic control settings hash differs",
        )
        control_settings = {
            **schedule_document["settings"],
            "callers": spec["callers"],
            "waiter_cap": spec["waiter_cap"],
            "retry_tokens": spec["retry_tokens"],
        }
        require(
            canonical_hash(control_settings) == spec["control_settings_sha256"],
            "semantic control settings hash is invalid",
        )
        require(
            as_int(summary, "work_iters") == schedule_work_iters,
            "semantic control work iterations differ from the sealed settings",
        )
        require(summary["pid"] not in seen_pids, "semantic control PID was reused")
        seen_pids.add(summary["pid"])
        recomputed = validate_process_receipts(directory, summary)
        for field, value in spec["expected"].items():
            require(recomputed[field] == value, f"semantic control {spec['control_id']} wrong {field}")

    require(len(seen_pids) == 50, "fresh process population is not 50 unique PIDs")
    ledger = []
    for line in read_receipt_text(directory / "subprocess-attempts.jsonl").splitlines():
        if not line:
            continue
        try:
            ledger.append(json.loads(line))
        except ValueError as error:
            raise SystemExit(f"malformed subprocess ledger line: {error}") from error
    calibration_attempts = [row for row in ledger if row["stage"] == "calibration"]
    period_attempts = [row for row in ledger if row["stage"] == "period"]
    control_attempts = [row for row in ledger if row["stage"] == "semantic-control"]
    require(
        len(calibration_attempts) == 1
        and len(period_attempts) == 48
        and len(control_attempts) == 2
        and len(ledger) == 51,
        "subprocess ledger implies a missing or replacement attempt",
    )
    require(
        [row["stage"] for row in ledger]
        == ["calibration"] + ["period"] * 48 + ["semantic-control"] * 2,
        "subprocess ledger stage order differs from the fixed schedule",
    )
    previous_ended_utc_ns = 0
    for row in ledger:
        require(
            row["started_utc_ns"] >= previous_ended_utc_ns,
            "subprocess windows overlap or run out of schedule order",
        )
        previous_ended_utc_ns = row["ended_utc_ns"]
    require(
        all(row["returncode"] == 0 and not row["timed_out"] for row in ledger),
        "subprocess ledger contains a failure or timeout",
    )
    for row in ledger:
        require(row["started_utc_ns"] <= row["ended_utc_ns"], "ledger time order invalid")
        require(row["elapsed_ns"] > 0 and row["timeout_seconds"] > 0, "ledger timing invalid")
        require(isinstance(row["command"], list) and row["command"], "ledger command missing")
        require("stdout" in row and "stderr" in row, "ledger capture missing")
    sealed_cpu_list = schedule_document["cpu_list"]
    if sealed_cpu_list:
        pinned_taskset = ledger[0]["command"][0]
        for row in ledger:
            require(
                row["command"][:3] == [pinned_taskset, "--cpu-list", sealed_cpu_list],
                "ledger command is not pinned to the sealed CPU list",
            )
    executable_index = 3 if sealed_cpu_list else 0
    ledger_executables = {row["command"][executable_index] for row in ledger}
    require(
        len(ledger_executables) == 1,
        "ledger commands name more than one probe executable",
    )
    ledger_binary = Path(next(iter(ledger_executables)))
    if ledger_binary.is_file():
        try:
            ledger_binary_hash = hashlib.sha256(ledger_binary.read_bytes()).hexdigest()
        except OSError as error:
            raise SystemExit(f"unreadable ledger probe executable: {error}") from error
        require(
            ledger_binary_hash == binary_hash,
            "ledger probe executable differs from the sealed binary hash",
        )
    parent_artifacts = directory.parent / "artifacts"
    if parent_artifacts.is_dir():
        require(
            ledger_binary.parts[-2:] == ("artifacts", ledger_binary.name),
            "ledger probe executable is not the retained bundle artifact",
        )
        retained_artifact = parent_artifacts / ledger_binary.name
        require(
            retained_artifact.is_file(),
            "retained bundle is missing the probe artifact the ledger names",
        )
        try:
            artifact_hash = hashlib.sha256(retained_artifact.read_bytes()).hexdigest()
        except OSError as error:
            raise SystemExit(f"unreadable retained artifact: {error}") from error
        require(
            artifact_hash == binary_hash,
            "retained artifact differs from the sealed binary hash",
        )
    calibration_values = calibration_attempts[0]["stdout"].strip().split(",")
    require(len(calibration_values) == 3, "calibration ledger stdout is malformed")
    require(
        calibration_values
        == [
            calibration_row["work_iters"],
            calibration_row["calibrated_mean_ns"],
            calibration_row["calibration_checksum"],
        ],
        "calibration ledger differs from calibration receipt",
    )
    for expected, attempt, summary in zip(expected_assignments, period_attempts, summaries):
        for field in ("phase", "block", "template", "period", "label", "treatment", "seed"):
            require(attempt[field] == expected[field], f"ledger period wrong {field}")
        attempted_summary = parse_summary(attempt["stdout"].strip())
        for field in PROBE_SUMMARY_FIELDS:
            require(attempted_summary[field] == summary[field], f"ledger stdout differs at {field}")
        require(
            as_int(summary, "setup_ns") + as_int(summary, "burst_ns") <= attempt["elapsed_ns"],
            "summary durations exceed the subprocess elapsed time",
        )
    for spec, attempt, summary in zip(control_specs, control_attempts, controls):
        require(attempt["control_id"] == spec["control_id"], "control ledger identity differs")
        attempted_summary = parse_summary(attempt["stdout"].strip())
        for field in PROBE_SUMMARY_FIELDS:
            require(attempted_summary[field] == summary[field], f"control stdout differs at {field}")
        require(
            as_int(summary, "setup_ns") + as_int(summary, "burst_ns") <= attempt["elapsed_ns"],
            "control durations exceed the subprocess elapsed time",
        )

    status = load_json(directory / "run-status.json")
    require(status["status"] == "complete", "run status is not complete")
    require(status["completed_periods"] == 48, "run status period count differs")
    require(status["completed_semantic_controls"] == 2, "run status control count differs")
    require(status["failed_period"] is None, "run status retains a failed period")
    require(
        isinstance(status["replacement_permitted"], bool) and not status["replacement_permitted"],
        "replacement policy changed",
    )
    require(status["binary_sha256"] == binary_hash, "run status binary differs")
    require(status["settings_sha256"] == settings_hash, "run status settings differs")

    retained_analysis = load_json(directory / "analysis.json")
    require_equal(build_analysis(directory), retained_analysis, "analysis")
    print("receipt validation: PASS")


if __name__ == "__main__":
    main()
