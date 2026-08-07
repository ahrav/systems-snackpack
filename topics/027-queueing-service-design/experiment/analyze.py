#!/usr/bin/env python3
"""Analyze Topic 27 receipts at the complete-block level."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_processes import AA_TEMPLATES, MAIN_TEMPLATES

T95 = {8: 2.364624251, 4: 3.182446305}
NUMERIC_FIELDS = (
    "mean_wait_ns",
    "p50_wait_ns",
    "p99_wait_ns",
    "mean_schedule_lag_ns",
    "p99_schedule_lag_ns",
    "goodput_rps",
    "rejection_pct",
)


def load_summaries(process_directory: Path) -> list[dict[str, Any]]:
    """Load summary rows and convert analysis fields to numbers."""
    with (process_directory / "summaries.csv").open(newline="", encoding="utf-8") as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        row["block"] = int(row["block"])
        row["period"] = int(row["period"])
        for field in NUMERIC_FIELDS:
            row[field] = float(row[field])
    return rows


def check_design(rows: list[dict[str, Any]]) -> None:
    """Reject input that does not match the predeclared complete-block design."""
    expected: dict[tuple[str, str, int], int] = {}
    expected_periods: dict[tuple[str, int, int], int] = {}
    for block in range(1, 9):
        expected[("main", "fixed", block)] = 2
        expected[("main", "variable", block)] = 2
        for period in range(1, 5):
            expected_periods[("main", block, period)] = 1
    for block in range(1, 5):
        expected[("aa", "A", block)] = 2
        expected[("aa", "B", block)] = 2
        for period in range(1, 5):
            expected_periods[("aa", block, period)] = 1
    counts: dict[tuple[str, str, int], int] = {}
    period_counts: dict[tuple[str, int, int], int] = {}
    for row in rows:
        group = row["mode"] if row["phase"] == "main" else row["label"]
        key = (row["phase"], group, row["block"])
        counts[key] = counts.get(key, 0) + 1
        period_key = (row["phase"], row["block"], row["period"])
        period_counts[period_key] = period_counts.get(period_key, 0) + 1
    if counts != expected or period_counts != expected_periods:
        raise ValueError(
            "summaries do not match the predeclared complete-block design "
            "of 8 main and 4 A/A blocks with 2 periods per group and "
            "periods 1..4 exactly once per block"
        )
    templates = {"main": MAIN_TEMPLATES, "aa": AA_TEMPLATES}
    for row in rows:
        expected_label = templates[row["phase"]][row["block"] - 1][row["period"] - 1]
        expected_mode = (
            "variable" if row["phase"] == "main" and expected_label == "B" else "fixed"
        )
        if row["label"] != expected_label or row["mode"] != expected_mode:
            raise ValueError(
                "summaries do not follow the predeclared period-to-label templates"
            )


def block_values(
    rows: list[dict[str, Any]], phase: str, group_field: str, group: str, metric: str
) -> dict[int, float]:
    """Return equal-period means for one group in every block."""
    selected: dict[int, list[float]] = {}
    for row in rows:
        if row["phase"] == phase and row[group_field] == group:
            selected.setdefault(row["block"], []).append(float(row[metric]))
    return {block: statistics.fmean(values) for block, values in selected.items()}


def interval(values: list[float]) -> dict[str, float | int]:
    """Return the fixed two-sided paired-t interval."""
    count = len(values)
    center = statistics.fmean(values)
    half_width = T95[count] * statistics.stdev(values) / math.sqrt(count)
    return {
        "estimate": center,
        "ci95_low": center - half_width,
        "ci95_high": center + half_width,
        "blocks": count,
    }


def treatment_difference(rows: list[dict[str, Any]], metric: str) -> dict[str, float | int]:
    """Return variable-minus-fixed block contrasts."""
    fixed = block_values(rows, "main", "mode", "fixed", metric)
    variable = block_values(rows, "main", "mode", "variable", metric)
    return interval([variable[block] - fixed[block] for block in sorted(fixed)])


def goodput_ratio(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    """Return the geometric variable-over-fixed block ratio."""
    fixed = block_values(rows, "main", "mode", "fixed", "goodput_rps")
    variable = block_values(rows, "main", "mode", "variable", "goodput_rps")
    result = interval(
        [math.log(variable[block] / fixed[block]) for block in sorted(fixed)]
    )
    for key in ("estimate", "ci95_low", "ci95_high"):
        result[key] = math.exp(float(result[key]))
    return result


def aa_difference(rows: list[dict[str, Any]], metric: str) -> dict[str, float | int]:
    """Return label-B-minus-label-A A/A block contrasts."""
    a_values = block_values(rows, "aa", "label", "A", metric)
    b_values = block_values(rows, "aa", "label", "B", metric)
    return interval([b_values[block] - a_values[block] for block in sorted(a_values)])


def nearest_rank(values: list[int], quantile: float) -> int:
    """Return a nearest-rank empirical percentile."""
    ordered = sorted(values)
    rank = max(1, math.ceil(quantile * len(ordered))) - 1
    return ordered[rank]


def pooled_treatment(process_directory: Path, rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    """Return descriptive request-level statistics with no request-level interval."""
    waits: list[int] = []
    schedule_lags: list[int] = []
    start_lags: list[int] = []
    offered = 0
    completed = 0
    for summary in rows:
        if summary["phase"] != "main" or summary["mode"] != mode:
            continue
        raw_path = process_directory / "raw" / Path(summary["raw_path"]).name
        with raw_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                offered += 1
                schedule_lags.append(
                    int(row["actual_arrival_ns"]) - int(row["intended_ns"])
                )
                if row["status"] == "completed":
                    completed += 1
                    waits.append(int(row["wait_ns"]))
                    start_lags.append(
                        int(row["service_start_ns"]) - int(row["intended_ns"])
                    )
    goodput = block_values(rows, "main", "mode", mode, "goodput_rps")
    return {
        "offered": offered,
        "completed": completed,
        "rejected": offered - completed,
        "rejection_pct": 100.0 * (offered - completed) / offered,
        "mean_wait_ns": statistics.fmean(waits),
        "p50_wait_ns": nearest_rank(waits, 0.50),
        "p99_wait_ns": nearest_rank(waits, 0.99),
        "mean_schedule_lag_ns": statistics.fmean(schedule_lags),
        "p99_schedule_lag_ns": nearest_rank(schedule_lags, 0.99),
        "mean_intended_to_service_start_ns": statistics.fmean(start_lags),
        "p50_intended_to_service_start_ns": nearest_rank(start_lags, 0.50),
        "p99_intended_to_service_start_ns": nearest_rank(start_lags, 0.99),
        "block_mean_goodput_rps": statistics.fmean(goodput.values()),
    }


def build_analysis(process_directory: Path) -> dict[str, Any]:
    """Build the complete predeclared analysis document."""
    rows = load_summaries(process_directory)
    check_design(rows)
    return {
        "parameters": {
            "main_blocks": 8,
            "aa_blocks": 4,
            "primary_estimand": "variable-minus-fixed invocation mean_wait_ns",
            "analysis_unit": "complete four-process block contrast",
            "request_statistics": "descriptive subsamples conditional on completion",
        },
        "treatments": {
            mode: pooled_treatment(process_directory, rows, mode)
            for mode in ("fixed", "variable")
        },
        "primary": treatment_difference(rows, "mean_wait_ns"),
        "secondary": {
            "p50_wait_ns_difference": treatment_difference(rows, "p50_wait_ns"),
            "p99_wait_ns_difference": treatment_difference(rows, "p99_wait_ns"),
            "mean_schedule_lag_ns_difference": treatment_difference(
                rows, "mean_schedule_lag_ns"
            ),
            "p99_schedule_lag_ns_difference": treatment_difference(
                rows, "p99_schedule_lag_ns"
            ),
            "rejection_percentage_point_difference": treatment_difference(
                rows, "rejection_pct"
            ),
            "goodput_ratio": goodput_ratio(rows),
        },
        "aa_diagnostics": {
            metric: aa_difference(rows, metric)
            for metric in (
                "mean_wait_ns",
                "p50_wait_ns",
                "p99_wait_ns",
                "mean_schedule_lag_ns",
                "p99_schedule_lag_ns",
                "goodput_rps",
                "rejection_pct",
            )
        },
    }


def main() -> None:
    """Print the predeclared complete-block analysis as JSON."""
    parser = argparse.ArgumentParser()
    parser.add_argument("process_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(build_analysis(args.process_directory), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
