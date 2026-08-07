#!/usr/bin/env python3
"""Validate Topic 27 schedule, accounting, raw timestamps, and analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze import build_analysis
from run_processes import (
    AA_TEMPLATES,
    MAIN_TEMPLATES,
    QUEUE_CAPACITY,
    REQUESTS,
    SUMMARY_FIELDS,
    TARGET_SERVICE_NS,
    assignments,
    parse_summary,
)


def require(condition: bool, message: str) -> None:
    """Stop at the first receipt violation."""
    if not condition:
        raise SystemExit(message)


def rows(path: Path) -> list[dict[str, str]]:
    """Load one CSV file."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def mix64(value: int) -> int:
    """Mirror the probe's wrapping seed mixer."""
    mask = (1 << 64) - 1
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & mask
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & mask
    return (value ^ (value >> 31)) & mask


def factor_x4(mode: str, request_id: int, seed: int) -> int:
    """Mirror the offered-work schedule."""
    if mode == "fixed":
        return 4
    position = mix64(seed ^ (request_id // 10)) % 10
    return 31 if request_id % 10 == position else 1


def require_equal(expected: Any, actual: Any, context: str) -> None:
    """Require recursively equal JSON, with tight float tolerance."""
    if isinstance(expected, float) or isinstance(actual, float):
        require(
            isinstance(expected, (int, float))
            and isinstance(actual, (int, float))
            and math.isclose(float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-9),
            f"analysis mismatch at {context}",
        )
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"keys differ at {context}")
        for key in expected:
            require_equal(expected[key], actual[key], f"{context}.{key}")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"length differs at {context}")
        for index, item in enumerate(expected):
            require_equal(item, actual[index], f"{context}[{index}]")
    else:
        require(expected == actual, f"value differs at {context}")


def nearest_rank(values: list[int], quantile: float) -> int:
    """Return the empirical nearest-rank percentile used by the probe."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(quantile * len(ordered))) - 1
    return ordered[rank]


def mean(values: list[int]) -> float:
    """Return the arithmetic mean used by the probe, or zero when empty."""
    if not values:
        return 0.0
    return sum(float(value) for value in values) / len(values)


def require_rounded(
    summary: dict[str, str], field: str, expected: float, places: int
) -> None:
    """Check a decimal summary field at its declared output precision."""
    tolerance = 0.5 * 10 ** (-places) + 1e-12
    require(
        summary[field] == f"{expected:.{places}f}"
        or math.isclose(float(summary[field]), expected, rel_tol=0.0, abs_tol=tolerance),
        f"summary {field} differs from raw receipts",
    )


def main() -> None:
    """Validate one completed process directory and its retained analysis."""
    parser = argparse.ArgumentParser()
    parser.add_argument("process_directory", type=Path)
    args = parser.parse_args()
    directory = args.process_directory

    expected = list(assignments())
    schedule = rows(directory / "schedule.csv")
    summaries = rows(directory / "summaries.csv")
    require(len(MAIN_TEMPLATES) == 8 and len(AA_TEMPLATES) == 4, "protocol block count changed")
    require(len(expected) == len(schedule) == len(summaries) == 48, "process count is not 48")
    require(len({row["pid"] for row in summaries}) == 48, "process PIDs are not unique")

    calibration = rows(directory / "calibration.csv")
    require(len(calibration) == 1, "wrong calibration row count")
    calibration_row = calibration[0]
    base_iterations = int(calibration_row["base_iters"])
    calibrated_mean_ns = int(calibration_row["calibrated_mean_ns"])
    interval_ns = int(calibration_row["interval_ns"])
    require(int(calibration_row["target_service_ns"]) == TARGET_SERVICE_NS, "target service changed")
    require(base_iterations > 0 and base_iterations % 4 == 0, "invalid base iterations")
    require(interval_ns == (calibrated_mean_ns * 10 + 8) // 9, "interval/load mismatch")

    for position, (assignment, scheduled, summary) in enumerate(
        zip(expected, schedule, summaries), start=1
    ):
        for key in ("phase", "template", "label", "mode"):
            require(scheduled[key] == str(assignment[key]), f"schedule {position} wrong {key}")
        for key in ("block", "period", "seed"):
            require(int(scheduled[key]) == assignment[key], f"schedule {position} wrong {key}")
        for key in ("phase", "label", "mode", "template"):
            require(summary[key] == str(assignment[key]), f"summary {position} wrong {key}")
        for key in ("block", "period", "seed"):
            require(int(summary[key]) == assignment[key], f"summary {position} wrong {key}")
        require(int(summary["requests"]) == REQUESTS, "request count changed")
        require(int(summary["queue_cap"]) == QUEUE_CAPACITY, "queue bound changed")
        require(int(summary["base_iters"]) == base_iterations, "calibration identity changed")
        require(int(summary["interval_ns"]) == interval_ns, "arrival interval changed")
        admitted = int(summary["admitted"])
        completed = int(summary["completed"])
        rejected = int(summary["rejected"])
        require(admitted == completed and completed + rejected == REQUESTS, "population accounting failed")

        raw_path = directory / "raw" / Path(summary["raw_path"]).name
        raw = rows(raw_path)
        require(len(raw) == REQUESTS, f"raw request count changed at process {position}")
        statuses = {"completed": 0, "rejected": 0}
        schedule_lags: list[int] = []
        waits: list[int] = []
        services: list[int] = []
        completion_times: list[int] = []
        admitted_times: list[int] = []
        service_start_times: list[int] = []
        rejected_arrivals: list[int] = []
        completed_sequence: list[tuple[int, int, int]] = []
        offered_work_x4 = 0
        checksum = 0
        previous_actual = -1
        for request_id, receipt in enumerate(raw):
            require(int(receipt["id"]) == request_id, "raw id order changed")
            require(receipt["pid"] == summary["pid"], "raw pid differs")
            for key in ("phase", "label", "mode"):
                require(receipt[key] == summary[key], f"raw {key} differs")
            for key in ("block", "period"):
                require(receipt[key] == summary[key], f"raw {key} differs")
            intended = request_id * interval_ns
            actual = int(receipt["actual_arrival_ns"])
            require(int(receipt["intended_ns"]) == intended and actual >= intended, "arrival timestamp invalid")
            require(actual >= previous_actual, "admission attempts are not monotonic")
            previous_actual = actual
            schedule_lags.append(actual - intended)
            expected_factor = factor_x4(summary["mode"], request_id, int(summary["seed"]))
            require(int(receipt["factor_x4"]) == expected_factor, "service factor mismatch")
            offered_work_x4 += expected_factor
            status = receipt["status"]
            require(status in statuses, "unknown raw status")
            statuses[status] += 1
            if status == "completed":
                admitted_ns = int(receipt["admitted_ns"])
                service_start_ns = int(receipt["service_start_ns"])
                completion_ns = int(receipt["completion_ns"])
                require(admitted_ns == actual <= service_start_ns <= completion_ns, "timestamp order invalid")
                require(int(receipt["wait_ns"]) == service_start_ns - admitted_ns, "wait mismatch")
                require(int(receipt["service_ns"]) == completion_ns - service_start_ns, "service mismatch")
                require(
                    int(receipt["sojourn_from_intended_ns"])
                    == completion_ns - intended,
                    "sojourn mismatch",
                )
                waits.append(service_start_ns - admitted_ns)
                services.append(completion_ns - service_start_ns)
                completion_times.append(completion_ns)
                admitted_times.append(admitted_ns)
                service_start_times.append(service_start_ns)
                completed_sequence.append((request_id, service_start_ns, completion_ns))
                checksum ^= int(receipt["checksum"])
            else:
                require(
                    all(
                        not receipt[key]
                        for key in (
                            "admitted_ns",
                            "service_start_ns",
                            "completion_ns",
                            "wait_ns",
                            "service_ns",
                            "sojourn_from_intended_ns",
                            "checksum",
                        )
                    ),
                    "rejected request has completion fields",
                )
                rejected_arrivals.append(actual)
        require(statuses["completed"] == completed and statuses["rejected"] == rejected, "raw status counts differ")
        # A rejection needs all four waiting slots occupied; the job in
        # service does not hold a waiting slot.
        service_starts_in_order = sorted(service_start_times)
        admit_index = 0
        started_index = 0
        for arrival in rejected_arrivals:
            while admit_index < len(admitted_times) and admitted_times[admit_index] <= arrival:
                admit_index += 1
            while started_index < len(service_starts_in_order) and service_starts_in_order[started_index] <= arrival:
                started_index += 1
            require(
                admit_index - started_index >= QUEUE_CAPACITY,
                "rejection recorded without a full queue",
            )
        require(offered_work_x4 == int(summary["offered_work_x4"]) == REQUESTS * 4, "offered work is not matched")
        require(checksum == int(summary["checksum"]), "summary checksum differs from raw receipts")
        require_rounded(summary, "rejection_pct", 100.0 * rejected / REQUESTS, 9)

        last_intended_ns = (REQUESTS - 1) * interval_ns
        duration_ns = max(max(completion_times, default=0), last_intended_ns + 1)
        require(int(summary["duration_ns"]) == duration_ns, "summary duration differs from raw receipts")
        require_rounded(summary, "goodput_rps", completed * 1_000_000_000.0 / duration_ns, 3)
        for prefix, values in (
            ("schedule_lag", schedule_lags),
            ("wait", waits),
            ("service", services),
        ):
            require_rounded(summary, f"mean_{prefix}_ns", mean(values), 3)
            require(
                int(summary[f"p50_{prefix}_ns"]) == nearest_rank(values, 0.50),
                f"summary p50_{prefix}_ns differs from raw receipts",
            )
            require(
                int(summary[f"p99_{prefix}_ns"]) == nearest_rank(values, 0.99),
                f"summary p99_{prefix}_ns differs from raw receipts",
            )
        service_mean = mean(services)
        service_variance = (
            sum((float(value) - service_mean) ** 2 for value in services)
            / len(services)
            if services
            else 0.0
        )
        service_cs2 = (
            service_variance / (service_mean * service_mean)
            if service_mean > 0.0
            else 0.0
        )
        require_rounded(summary, "service_cs2", service_cs2, 6)

        for previous, current in zip(completed_sequence, completed_sequence[1:]):
            require(previous[0] < current[0], "completed requests violate FIFO id order")
            require(
                previous[2] <= current[1],
                "single-worker service intervals overlap",
            )

    attempts = [json.loads(line) for line in (directory / "attempts.jsonl").read_text().splitlines() if line]
    require(len(attempts) == 48 and all(attempt["returncode"] == 0 for attempt in attempts), "attempt ledger is incomplete")
    for position, (assignment, attempt, summary) in enumerate(
        zip(expected, attempts, summaries), start=1
    ):
        for key in ("phase", "block", "template", "period", "label", "mode", "seed"):
            require(attempt[key] == assignment[key], f"attempt {position} wrong {key}")
        require(int(attempt["process_wall_ns"]) > 0, "attempt wall time is not positive")
        attempted_summary = parse_summary(attempt["stdout"].strip())
        for field in SUMMARY_FIELDS:
            require(
                attempted_summary[field] == summary[field],
                f"attempt stdout differs from summary at {position}.{field}",
            )
    status = json.loads((directory / "run-status.json").read_text())
    require(status == {"status": "complete", "completed_attempts": 48}, "run status is not complete")
    retained = json.loads((directory / "analysis.json").read_text())
    require_equal(build_analysis(directory), retained, "analysis")
    print("receipt validation: PASS")


if __name__ == "__main__":
    main()
