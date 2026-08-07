#!/usr/bin/env python3
"""Run the fixed Topic 28 fresh-process schedule without replacement."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

MAIN_TEMPLATES = (
    "ABBA",
    "ABBA",
    "BAAB",
    "BAAB",
    "BAAB",
    "ABBA",
    "ABBA",
    "BAAB",
)
AA_TEMPLATES = ("ABBA", "BAAB", "BAAB", "ABBA")
MAIN_SCHEDULE_SEED = 28_082_026
AA_SCHEDULE_SEED = 28_082_027
CALLERS = 64
WAITER_CAP = 64
ORIGIN_CAPACITY = 4
MAX_ATTEMPTS = 3
RETRY_TOKENS = 2
TARGET_ATTEMPT_NS = 200_000
KEY_DIGEST = 2_808_202_801
TIMEOUT_SECONDS = 300

PROBE_SUMMARY_FIELDS = (
    "pid",
    "phase",
    "block",
    "period",
    "label",
    "treatment",
    "seed",
    "key_digest",
    "callers",
    "waiter_cap",
    "origin_capacity",
    "max_attempts",
    "retry_tokens",
    "work_iters",
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
    "burst_ns",
    "setup_ns",
    "result_checksum",
    "logical_path",
    "attempt_path",
)

SUMMARY_FIELDS = PROBE_SUMMARY_FIELDS + (
    "template",
    "binary_sha256",
    "settings_sha256",
    "process_started_utc_ns",
    "process_ended_utc_ns",
    "process_wall_ns",
    "command",
)

CONTROL_SUMMARY_FIELDS = PROBE_SUMMARY_FIELDS + (
    "control_id",
    "binary_sha256",
    "control_settings_sha256",
    "process_started_utc_ns",
    "process_ended_utc_ns",
    "process_wall_ns",
    "command",
)


def assignments() -> Iterator[dict[str, Any]]:
    """Yield all 32 main periods followed by all 16 A/A periods."""
    for phase, templates, seed_prefix in (
        ("main", MAIN_TEMPLATES, MAIN_SCHEDULE_SEED),
        ("aa", AA_TEMPLATES, AA_SCHEDULE_SEED),
    ):
        for block, template in enumerate(templates, start=1):
            for period, label in enumerate(template, start=1):
                yield {
                    "phase": phase,
                    "block": block,
                    "template": template,
                    "period": period,
                    "label": label,
                    "treatment": (
                        "naive" if phase == "main" and label == "A" else "controlled"
                    ),
                    "seed": seed_prefix * 100 + block,
                }


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    """Hash one JSON value with stable separators and key ordering."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_summary(stdout: str) -> dict[str, str]:
    """Parse the probe's one-line CSV summary."""
    lines = stdout.splitlines()
    if len(lines) != 1:
        raise ValueError(f"probe emitted {len(lines)} summary lines")
    header = io.StringIO(",".join(PROBE_SUMMARY_FIELDS) + "\n" + stdout)
    rows = list(csv.DictReader(header))
    if len(rows) != 1 or None in rows[0] or None in rows[0].values():
        raise ValueError(f"malformed probe summary: {stdout!r}")
    return rows[0]


def captured_text(value: str | bytes | None) -> str:
    """Normalize captured timeout output for the attempt ledger."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def append_ledger(path: Path, record: dict[str, Any]) -> None:
    """Append and flush one immutable subprocess-attempt record."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()


def execute(
    command: Sequence[str],
    ledger_path: Path,
    identity: dict[str, Any],
    timeout_seconds: int = TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Execute once, append stdout/stderr and timing, and never retry."""
    started_utc_ns = time.time_ns()
    started_monotonic_ns = time.monotonic_ns()
    try:
        process = subprocess.run(
            list(command), capture_output=True, text=True, timeout=timeout_seconds
        )
    except subprocess.TimeoutExpired as error:
        ended_utc_ns = time.time_ns()
        append_ledger(
            ledger_path,
            {
                **identity,
                "command": list(command),
                "started_utc_ns": started_utc_ns,
                "ended_utc_ns": ended_utc_ns,
                "elapsed_ns": time.monotonic_ns() - started_monotonic_ns,
                "timeout_seconds": timeout_seconds,
                "returncode": None,
                "stdout": captured_text(error.stdout),
                "stderr": captured_text(error.stderr),
                "timed_out": True,
            },
        )
        raise RuntimeError("subprocess timed out; no replacement is permitted") from error
    ended_utc_ns = time.time_ns()
    append_ledger(
        ledger_path,
        {
            **identity,
            "command": list(command),
            "started_utc_ns": started_utc_ns,
            "ended_utc_ns": ended_utc_ns,
            "elapsed_ns": time.monotonic_ns() - started_monotonic_ns,
            "timeout_seconds": timeout_seconds,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "timed_out": False,
        },
    )
    return process


def main() -> None:
    """Calibrate once, then execute all 48 predeclared process periods."""
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument(
        "cpu_list",
        nargs="?",
        default="",
        help="taskset CPU list; omit only for a local correctness run without taskset",
    )
    args = parser.parse_args()

    binary = args.binary.resolve(strict=True)
    output = args.output_directory.resolve(strict=False)
    if output.exists():
        raise SystemExit(f"output directory already exists: {output}")
    raw_directory = output / "raw"
    raw_directory.mkdir(parents=True)
    ledger_path = output / "subprocess-attempts.jsonl"

    taskset_prefix: list[str] = []
    if args.cpu_list:
        if shutil.which("taskset") is None:
            raise SystemExit("a CPU list was supplied but taskset is unavailable")
        taskset_prefix = ["taskset", "--cpu-list", args.cpu_list]

    binary_sha256 = sha256_file(binary)
    calibration_command = taskset_prefix + [
        str(binary),
        "--calibrate",
        str(TARGET_ATTEMPT_NS),
    ]
    calibration = execute(
        calibration_command,
        ledger_path,
        {"stage": "calibration"},
    )
    if calibration.returncode != 0:
        raise SystemExit("calibration failed; no measurement periods were started")
    try:
        work_iters, calibrated_mean_ns, calibration_checksum = map(
            int, calibration.stdout.strip().split(",")
        )
    except ValueError as error:
        raise SystemExit(f"invalid calibration receipt: {calibration.stdout!r}") from error
    if work_iters <= 0 or calibrated_mean_ns <= 0:
        raise SystemExit("calibration returned a nonpositive iteration or duration")

    settings = {
        "callers": CALLERS,
        "key_digest": KEY_DIGEST,
        "max_attempts": MAX_ATTEMPTS,
        "origin_capacity": ORIGIN_CAPACITY,
        "retry_tokens": RETRY_TOKENS,
        "target_attempt_ns": TARGET_ATTEMPT_NS,
        "waiter_cap": WAITER_CAP,
        "work_iters": work_iters,
    }
    settings_sha256 = canonical_hash(settings)
    (output / "settings.json").write_text(
        json.dumps(settings, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    (output / "settings.sha256").write_text(
        f"{settings_sha256}  settings.json\n", encoding="utf-8"
    )
    (output / "binary.sha256").write_text(
        f"{binary_sha256}  {binary.name}\n", encoding="utf-8"
    )
    with (output / "calibration.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "target_attempt_ns",
                "work_iters",
                "calibrated_mean_ns",
                "calibration_checksum",
                "binary_sha256",
                "settings_sha256",
            )
        )
        writer.writerow(
            (
                TARGET_ATTEMPT_NS,
                work_iters,
                calibrated_mean_ns,
                calibration_checksum,
                binary_sha256,
                settings_sha256,
            )
        )

    schedule = list(assignments())
    for assignment in schedule:
        assignment["binary_sha256"] = binary_sha256
        assignment["settings_sha256"] = settings_sha256
    semantic_controls = [
        {
            "control_id": "saturation-n128-w64-q2",
            "phase": "aa",
            "block": 9001,
            "period": 1,
            "label": "A",
            "treatment": "controlled",
            "seed": AA_SCHEDULE_SEED * 100 + 9001,
            "callers": 128,
            "waiter_cap": 64,
            "retry_tokens": 2,
            "expected": {
                "completed": 64,
                "shed": 64,
                "leaders": 1,
                "followers": 63,
                "flights": 1,
                "origin_attempts": 3,
                "retry_attempts": 2,
                "retry_exhausted": 0,
            },
        },
        {
            "control_id": "retry-exhaustion-n64-w64-q1",
            "phase": "aa",
            "block": 9002,
            "period": 1,
            "label": "A",
            "treatment": "controlled",
            "seed": AA_SCHEDULE_SEED * 100 + 9002,
            "callers": 64,
            "waiter_cap": 64,
            "retry_tokens": 1,
            "expected": {
                "completed": 0,
                "shed": 0,
                "leaders": 1,
                "followers": 63,
                "flights": 1,
                "origin_attempts": 2,
                "retry_attempts": 1,
                "retry_exhausted": 64,
            },
        },
    ]
    for control in semantic_controls:
        control_settings = {
            **settings,
            "callers": control["callers"],
            "waiter_cap": control["waiter_cap"],
            "retry_tokens": control["retry_tokens"],
        }
        control["control_settings_sha256"] = canonical_hash(control_settings)
    schedule_document = {
        "protocol": "topic28-one-key-miss-wave-v1",
        "main_templates": list(MAIN_TEMPLATES),
        "aa_templates": list(AA_TEMPLATES),
        "main_schedule_seed": MAIN_SCHEDULE_SEED,
        "aa_schedule_seed": AA_SCHEDULE_SEED,
        "analysis_unit": "one complete four-process block contrast",
        "experimental_unit": "one fresh process",
        "replacement_policy": "none; any failed period invalidates the run",
        "cpu_list": args.cpu_list,
        "binary_sha256": binary_sha256,
        "settings_sha256": settings_sha256,
        "settings": settings,
        "assignments": schedule,
        "semantic_controls": semantic_controls,
    }
    (output / "schedule.json").write_text(
        json.dumps(schedule_document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary_path = output / "summaries.csv"
    completed_periods = 0
    failed_period: str | None = None
    try:
        with summary_path.open("w", newline="", encoding="utf-8") as summary_handle:
            writer = csv.DictWriter(summary_handle, fieldnames=SUMMARY_FIELDS)
            writer.writeheader()
            for assignment in schedule:
                run_id = (
                    f"{assignment['phase']}-b{assignment['block']:02d}-"
                    f"p{assignment['period']}-{assignment['label']}"
                )
                failed_period = run_id
                logical_path = raw_directory / f"{run_id}-logical.csv"
                attempt_path = raw_directory / f"{run_id}-attempts.csv"
                command = taskset_prefix + [
                    str(binary),
                    "--phase",
                    assignment["phase"],
                    "--block",
                    str(assignment["block"]),
                    "--period",
                    str(assignment["period"]),
                    "--label",
                    assignment["label"],
                    "--treatment",
                    assignment["treatment"],
                    "--seed",
                    str(assignment["seed"]),
                    "--key-digest",
                    str(KEY_DIGEST),
                    "--callers",
                    str(CALLERS),
                    "--waiter-cap",
                    str(WAITER_CAP),
                    "--origin-cap",
                    str(ORIGIN_CAPACITY),
                    "--max-attempts",
                    str(MAX_ATTEMPTS),
                    "--retry-tokens",
                    str(RETRY_TOKENS),
                    "--work-iters",
                    str(work_iters),
                    "--logical",
                    str(logical_path),
                    "--attempts",
                    str(attempt_path),
                ]
                period_identity = {
                    "stage": "period",
                    **assignment,
                    "run_id": run_id,
                }
                process = execute(command, ledger_path, period_identity)
                ledger_entry = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[-1])
                if process.returncode != 0:
                    raise RuntimeError(f"{run_id} failed; no replacement is permitted")
                row = parse_summary(process.stdout)
                row.update(
                    {
                        "template": assignment["template"],
                        "binary_sha256": binary_sha256,
                        "settings_sha256": settings_sha256,
                        "process_started_utc_ns": ledger_entry["started_utc_ns"],
                        "process_ended_utc_ns": ledger_entry["ended_utc_ns"],
                        "process_wall_ns": ledger_entry["elapsed_ns"],
                        "command": " ".join(command),
                    }
                )
                writer.writerow(row)
                summary_handle.flush()
                completed_periods += 1
                failed_period = None
    except Exception as error:
        (output / "run-status.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "completed_periods": completed_periods,
                    "failed_period": failed_period,
                    "error": str(error),
                    "replacement_permitted": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise

    completed_semantic_controls = 0
    failed_control: str | None = None
    control_summary_path = output / "semantic-controls.csv"
    try:
        with control_summary_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CONTROL_SUMMARY_FIELDS)
            writer.writeheader()
            for control in semantic_controls:
                control_id = str(control["control_id"])
                failed_control = control_id
                logical_path = raw_directory / f"control-{control_id}-logical.csv"
                attempt_path = raw_directory / f"control-{control_id}-attempts.csv"
                command = taskset_prefix + [
                    str(binary),
                    "--phase",
                    str(control["phase"]),
                    "--block",
                    str(control["block"]),
                    "--period",
                    str(control["period"]),
                    "--label",
                    str(control["label"]),
                    "--treatment",
                    str(control["treatment"]),
                    "--seed",
                    str(control["seed"]),
                    "--key-digest",
                    str(KEY_DIGEST),
                    "--callers",
                    str(control["callers"]),
                    "--waiter-cap",
                    str(control["waiter_cap"]),
                    "--origin-cap",
                    str(ORIGIN_CAPACITY),
                    "--max-attempts",
                    str(MAX_ATTEMPTS),
                    "--retry-tokens",
                    str(control["retry_tokens"]),
                    "--work-iters",
                    str(work_iters),
                    "--logical",
                    str(logical_path),
                    "--attempts",
                    str(attempt_path),
                ]
                process = execute(
                    command,
                    ledger_path,
                    {
                        "stage": "semantic-control",
                        "control_id": control_id,
                        "binary_sha256": binary_sha256,
                        "control_settings_sha256": control[
                            "control_settings_sha256"
                        ],
                    },
                )
                ledger_entry = json.loads(
                    ledger_path.read_text(encoding="utf-8").splitlines()[-1]
                )
                if process.returncode != 0:
                    raise RuntimeError(
                        f"semantic control {control_id} failed; no replacement is permitted"
                    )
                row = parse_summary(process.stdout)
                row.update(
                    {
                        "control_id": control_id,
                        "binary_sha256": binary_sha256,
                        "control_settings_sha256": control[
                            "control_settings_sha256"
                        ],
                        "process_started_utc_ns": ledger_entry["started_utc_ns"],
                        "process_ended_utc_ns": ledger_entry["ended_utc_ns"],
                        "process_wall_ns": ledger_entry["elapsed_ns"],
                        "command": " ".join(command),
                    }
                )
                writer.writerow(row)
                handle.flush()
                completed_semantic_controls += 1
                failed_control = None
    except Exception as error:
        (output / "run-status.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "completed_periods": completed_periods,
                    "completed_semantic_controls": completed_semantic_controls,
                    "failed_semantic_control": failed_control,
                    "error": str(error),
                    "replacement_permitted": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise

    if sha256_file(binary) != binary_sha256:
        (output / "run-status.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "completed_periods": completed_periods,
                    "completed_semantic_controls": completed_semantic_controls,
                    "error": "binary changed during the process schedule",
                    "replacement_permitted": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError("binary changed during the process schedule")
    (output / "run-status.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "completed_periods": completed_periods,
                "completed_semantic_controls": completed_semantic_controls,
                "failed_period": None,
                "replacement_permitted": False,
                "binary_sha256": binary_sha256,
                "settings_sha256": settings_sha256,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
