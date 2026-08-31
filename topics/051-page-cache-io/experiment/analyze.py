#!/usr/bin/env python3
"""Analyze complete Topic 51 process blocks on the paired log scale."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
from typing import Any, NoReturn


SCENARIOS = {
    "primary": {
        "templates": ("ABBA", "BAAB", "ABBA", "BAAB", "BAAB", "ABBA", "BAAB", "ABBA"),
        "left": "A",
        "right": "B",
        "ratio": "buffered_random_over_buffered_sequential",
        "t975": 2.364624251,
    },
    "aa": {
        "templates": ("XYYX", "YXXY", "XYYX", "YXXY", "YXXY", "XYYX", "YXXY", "XYYX"),
        "left": "X",
        "right": "Y",
        "ratio": "aa_y_over_aa_x",
        "t975": 2.364624251,
    },
    "direct": {
        "templates": ("ABBA", "BAAB", "BAAB", "ABBA"),
        "left": "A",
        "right": "B",
        "ratio": "direct_sequential_over_buffered_sequential",
        "t975": 3.182446305,
    },
}


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    fail(f"non-finite JSON number: {token}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_pairs,
        parse_constant=reject_constant,
    )
    if not isinstance(value, dict):
        fail(f"{path}: expected one JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.endswith("\n") or not line.strip():
                fail(f"{path}:{line_number}: partial or blank JSONL record")
            value = json.loads(
                line,
                object_pairs_hook=reject_pairs,
                parse_constant=reject_constant,
            )
            if not isinstance(value, dict):
                fail(f"{path}:{line_number}: expected one JSON object")
            rows.append(value)
    return rows


def percentile(values: list[int], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def distribution(values: list[int]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "min_ms": min(values) / 1e6,
        "q1_ms": percentile(values, 0.25) / 1e6,
        "median_ms": statistics.median(values) / 1e6,
        "q3_ms": percentile(values, 0.75) / 1e6,
        "max_ms": max(values) / 1e6,
    }


def analyze_scenario(root: Path, name: str) -> dict[str, Any]:
    config = SCENARIOS[name]
    expected_templates = config["templates"]
    left = config["left"]
    right = config["right"]
    t975 = config["t975"]
    assert isinstance(expected_templates, tuple)
    assert isinstance(left, str)
    assert isinstance(right, str)
    assert isinstance(t975, float)

    schedule = read_json(root / name / "schedule.json")
    if schedule.get("scenario") != name or schedule.get("templates") != list(expected_templates):
        fail(f"{name}: schedule differs from the fixed design")
    rows = read_jsonl(root / name / "attempts.jsonl")
    expected_count = len(expected_templates) * 4
    if len(rows) != expected_count:
        fail(f"{name}: expected {expected_count} attempts, found {len(rows)}")
    if any(row.get("valid") is not True for row in rows):
        fail(f"{name}: invalid attempts cannot enter the estimate")

    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        block = row.get("block")
        if type(block) is not int:
            fail(f"{name}: malformed block number")
        grouped.setdefault(block, []).append(row)

    contrasts = []
    all_left: list[int] = []
    all_right: list[int] = []
    startup_left: list[int] = []
    startup_right: list[int] = []
    for block, template in enumerate(expected_templates, 1):
        block_rows = grouped.get(block, [])
        if len(block_rows) != 4:
            fail(f"{name}: block {block} is incomplete")
        block_rows.sort(key=lambda row: row["period"])
        if "".join(str(row["letter"]) for row in block_rows) != template:
            fail(f"{name}: block {block} treatment order changed")
        left_values = []
        right_values = []
        for row in block_rows:
            observed = row.get("observed")
            if not isinstance(observed, dict):
                fail(f"{name}: missing native observation")
            measurement = observed.get("measurement_ns")
            startup = observed.get("startup_to_measure_ns")
            if type(measurement) is not int or measurement <= 0:
                fail(f"{name}: malformed measurement")
            if type(startup) is not int or startup <= 0:
                fail(f"{name}: malformed startup measurement")
            if row["letter"] == left:
                left_values.append(measurement)
                all_left.append(measurement)
                startup_left.append(startup)
            elif row["letter"] == right:
                right_values.append(measurement)
                all_right.append(measurement)
                startup_right.append(startup)
            else:
                fail(f"{name}: unknown treatment label")
        if len(left_values) != 2 or len(right_values) != 2:
            fail(f"{name}: block {block} lacks two observations per label")
        left_geomean = math.exp(statistics.mean(math.log(value) for value in left_values))
        right_geomean = math.exp(statistics.mean(math.log(value) for value in right_values))
        log_ratio = math.log(right_geomean) - math.log(left_geomean)
        contrasts.append(
            {
                "block": block,
                "template": template,
                "left_geomean_ns": left_geomean,
                "right_geomean_ns": right_geomean,
                "log_ratio": log_ratio,
                "right_over_left": math.exp(log_ratio),
            }
        )

    logs = [contrast["log_ratio"] for contrast in contrasts]
    mean_log = statistics.mean(logs)
    log_sd = statistics.stdev(logs)
    standard_error = log_sd / math.sqrt(len(logs))
    return {
        "scenario": name,
        "ratio_name": config["ratio"],
        "attempt_count": len(rows),
        "complete_block_count": len(contrasts),
        "invalid_attempt_count": 0,
        "point_ratio": math.exp(mean_log),
        "ratio_95pct_student_t_interval": [
            math.exp(mean_log - t975 * standard_error),
            math.exp(mean_log + t975 * standard_error),
        ],
        "log_contrast_sd": log_sd,
        "left_measurement": distribution(all_left),
        "right_measurement": distribution(all_right),
        "left_startup_to_measure": distribution(startup_left),
        "right_startup_to_measure": distribution(startup_right),
        "block_contrasts": contrasts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    args = parser.parse_args()
    root = args.campaign_root.resolve(strict=True)
    result = {
        "schema": "topic51-analysis.v1",
        "method": "mean complete-block log ratio with two-sided 95% Student-t interval",
        "interval_scope": (
            "between-block process variation on one host, binary, file, filesystem, device, "
            "and run window; excludes host, build, kernel, and device-population variation"
        ),
        "aa_scope": "mechanical label-path diagnostic, not null calibration or a noise floor",
        "scenarios": {name: analyze_scenario(root, name) for name in SCENARIOS},
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
