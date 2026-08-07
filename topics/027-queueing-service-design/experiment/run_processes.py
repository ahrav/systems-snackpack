#!/usr/bin/env python3
"""Run the fixed Topic 27 fresh-process schedule without replacement."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

MAIN_TEMPLATES = (
    "BAAB",
    "ABBA",
    "BAAB",
    "ABBA",
    "ABBA",
    "BAAB",
    "ABBA",
    "BAAB",
)
AA_TEMPLATES = ("ABBA", "BAAB", "BAAB", "ABBA")
SCHEDULE_SEED = 27_082_026
REQUESTS = 8_000
QUEUE_CAPACITY = 4
TARGET_SERVICE_NS = 200_000
SUMMARY_FIELDS: tuple[str, ...] = (
    "pid",
    "label",
    "phase",
    "block",
    "period",
    "mode",
    "seed",
    "requests",
    "queue_cap",
    "base_iters",
    "interval_ns",
    "offered_work_x4",
    "admitted",
    "completed",
    "rejected",
    "rejection_pct",
    "duration_ns",
    "goodput_rps",
    "mean_schedule_lag_ns",
    "p50_schedule_lag_ns",
    "p99_schedule_lag_ns",
    "mean_wait_ns",
    "p50_wait_ns",
    "p99_wait_ns",
    "mean_service_ns",
    "p50_service_ns",
    "p99_service_ns",
    "service_cs2",
    "checksum",
    "raw_path",
)


def assignments() -> Iterator[dict[str, Any]]:
    """Yield the complete main and A/A schedules in execution order."""
    for phase, templates, seed_prefix in (
        ("main", MAIN_TEMPLATES, SCHEDULE_SEED),
        ("aa", AA_TEMPLATES, SCHEDULE_SEED + 1),
    ):
        for block, template in enumerate(templates, start=1):
            for period, label in enumerate(template, start=1):
                yield {
                    "phase": phase,
                    "block": block,
                    "template": template,
                    "period": period,
                    "label": label,
                    "mode": "variable" if phase == "main" and label == "B" else "fixed",
                    "seed": seed_prefix * 100 + block,
                }


def parse_summary(stdout: str) -> dict[str, str]:
    """Parse the probe's single CSV receipt."""
    lines = stdout.splitlines()
    if len(lines) != 1:
        raise ValueError(f"probe emitted {len(lines)} summary lines")
    reader = csv.DictReader(io.StringIO(",".join(SUMMARY_FIELDS) + "\n" + stdout))
    rows = list(reader)
    if len(rows) != 1 or None in rows[0] or None in rows[0].values():
        raise ValueError(f"malformed probe summary: {stdout!r}")
    return rows[0]


def captured_text(value: str | bytes | None) -> str:
    """Normalize subprocess timeout output for the JSON attempt ledger."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def main() -> None:
    """Calibrate once, then execute all 48 predeclared processes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("cpu_list")
    args = parser.parse_args()

    taskset_path = shutil.which("taskset")
    if taskset_path is None:
        raise SystemExit("taskset is required; run this harness on Linux")
    taskset_path = str(Path(taskset_path).resolve())
    binary = args.binary.resolve(strict=True)
    output = args.output_directory.resolve(strict=False)
    if output.exists():
        raise SystemExit(f"output directory already exists: {output}")
    raw_directory = output / "raw"
    raw_directory.mkdir(parents=True)

    design = {
        "requests_per_process": REQUESTS,
        "queue_waiting_slots": QUEUE_CAPACITY,
        "servers": 1,
        "target_service_ns": TARGET_SERVICE_NS,
        "nominal_load": 0.9,
        "main_templates": list(MAIN_TEMPLATES),
        "aa_templates": list(AA_TEMPLATES),
        "schedule_seed": SCHEDULE_SEED,
        "treatment_application": "one fresh process",
        "analysis_unit": "one complete four-process block contrast",
        "replacement_policy": "none",
        "taskset_path": taskset_path,
    }
    (output / "design.json").write_text(
        json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    calibration_command = [
        taskset_path,
        "--cpu-list",
        args.cpu_list,
        str(binary),
        "--calibrate",
        str(TARGET_SERVICE_NS),
    ]
    calibration = subprocess.run(
        calibration_command,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    try:
        base_iterations, calibrated_mean_ns, calibration_checksum = map(
            int, calibration.stdout.strip().split(",")
        )
    except ValueError as error:
        raise SystemExit(f"invalid calibration receipt: {calibration.stdout!r}") from error
    if base_iterations <= 0 or base_iterations % 4 or calibrated_mean_ns <= 0:
        raise SystemExit("invalid calibration values")
    # ponytail: +/-25% bound; tighten if hosts calibrate more precisely.
    drift_ok = 0.75 * TARGET_SERVICE_NS <= calibrated_mean_ns <= 1.25 * TARGET_SERVICE_NS
    if not drift_ok:
        raise SystemExit(
            f"calibrated mean {calibrated_mean_ns}ns misses the "
            f"{TARGET_SERVICE_NS}ns target by more than 25%"
        )
    interval_ns = (calibrated_mean_ns * 10 + 8) // 9
    with (output / "calibration.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "target_service_ns",
                "base_iters",
                "calibrated_mean_ns",
                "calibration_checksum",
                "load_target",
                "interval_ns",
            )
        )
        writer.writerow(
            (
                TARGET_SERVICE_NS,
                base_iterations,
                calibrated_mean_ns,
                calibration_checksum,
                "0.9",
                interval_ns,
            )
        )

    schedule = list(assignments())
    with (output / "schedule.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(schedule[0]))
        writer.writeheader()
        writer.writerows(schedule)

    attempts_path = output / "attempts.jsonl"
    summary_path = output / "summaries.csv"
    fields = SUMMARY_FIELDS + ("template", "process_wall_ns", "command")
    completed_attempts = 0
    try:
        with summary_path.open("w", newline="", encoding="utf-8") as summary_handle:
            writer = csv.DictWriter(summary_handle, fieldnames=fields)
            writer.writeheader()
            for assignment in schedule:
                run_id = (
                    f"{assignment['phase']}-b{assignment['block']:02d}-"
                    f"p{assignment['period']}-{assignment['label']}"
                )
                raw_path = raw_directory / f"{run_id}.csv"
                command = [
                    taskset_path,
                    "--cpu-list",
                    args.cpu_list,
                    str(binary),
                    "--mode",
                    assignment["mode"],
                    "--label",
                    assignment["label"],
                    "--phase",
                    assignment["phase"],
                    "--block",
                    str(assignment["block"]),
                    "--period",
                    str(assignment["period"]),
                    "--seed",
                    str(assignment["seed"]),
                    "--requests",
                    str(REQUESTS),
                    "--queue-cap",
                    str(QUEUE_CAPACITY),
                    "--base-iters",
                    str(base_iterations),
                    "--interval-ns",
                    str(interval_ns),
                    "--raw",
                    str(raw_path),
                ]
                started_ns = time.monotonic_ns()
                try:
                    process = subprocess.run(
                        command, capture_output=True, text=True, timeout=300
                    )
                except subprocess.TimeoutExpired as error:
                    process_wall_ns = time.monotonic_ns() - started_ns
                    attempt = {
                        **assignment,
                        "command": command,
                        "process_wall_ns": process_wall_ns,
                        "returncode": None,
                        "stdout": captured_text(error.stdout),
                        "stderr": captured_text(error.stderr),
                        "timeout_seconds": 300,
                    }
                    with attempts_path.open("a", encoding="utf-8") as attempts:
                        attempts.write(json.dumps(attempt, sort_keys=True) + "\n")
                    raise RuntimeError(
                        f"{run_id} timed out; no replacement is permitted"
                    ) from error
                process_wall_ns = time.monotonic_ns() - started_ns
                attempt = {
                    **assignment,
                    "command": command,
                    "process_wall_ns": process_wall_ns,
                    "returncode": process.returncode,
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                }
                with attempts_path.open("a", encoding="utf-8") as attempts:
                    attempts.write(json.dumps(attempt, sort_keys=True) + "\n")
                if process.returncode != 0:
                    raise RuntimeError(f"{run_id} failed; no replacement is permitted")
                row: dict[str, Any] = parse_summary(process.stdout)
                row.update(
                    {
                        "template": assignment["template"],
                        "process_wall_ns": process_wall_ns,
                        "command": " ".join(command),
                    }
                )
                writer.writerow(row)
                summary_handle.flush()
                completed_attempts += 1
                time.sleep(0.1)
    except Exception as error:
        (output / "run-status.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "completed_attempts": completed_attempts,
                    "error": str(error),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise

    (output / "run-status.json").write_text(
        json.dumps(
            {"status": "complete", "completed_attempts": completed_attempts},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
