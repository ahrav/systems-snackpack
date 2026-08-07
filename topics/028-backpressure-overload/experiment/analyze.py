#!/usr/bin/env python3
"""Analyze Topic 28 at the predeclared complete-block process level."""

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

from run_processes import (
    AA_SCHEDULE_SEED,
    AA_TEMPLATES,
    CALLERS,
    KEY_DIGEST,
    MAIN_SCHEDULE_SEED,
    MAIN_TEMPLATES,
    MAX_ATTEMPTS,
    ORIGIN_CAPACITY,
    RETRY_TOKENS,
    WAITER_CAP,
)

T95_N8 = 2.364624251


def load_summaries(process_directory: Path) -> list[dict[str, Any]]:
    """Load scheduled process summaries and convert analysis fields."""
    with (process_directory / "summaries.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows: list[dict[str, Any]] = list(csv.DictReader(handle))
    for row in rows:
        try:
            row["block"] = int(row["block"])
            row["period"] = int(row["period"])
            row["burst_ns"] = int(row["burst_ns"])
            row["setup_ns"] = int(row["setup_ns"])
            for field in (
                "completed",
                "shed",
                "leaders",
                "followers",
                "flights",
                "origin_attempts",
                "retry_attempts",
            ):
                row[field] = int(row[field])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"summaries.csv row has invalid numeric fields: {error}") from error
    return rows


def check_design(rows: list[dict[str, Any]]) -> None:
    """Reject input that does not match the predeclared complete-block design."""
    expected: dict[tuple[str, str, int], int] = {}
    expected_periods: dict[tuple[str, int, int], int] = {}
    for block in range(1, 9):
        expected[("main", "naive", block)] = 2
        expected[("main", "controlled", block)] = 2
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
        group = row["treatment"] if row["phase"] == "main" else row["label"]
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
    seeds = {"main": MAIN_SCHEDULE_SEED, "aa": AA_SCHEDULE_SEED}
    for row in rows:
        expected_label = templates[row["phase"]][row["block"] - 1][row["period"] - 1]
        expected_treatment = (
            "naive" if row["phase"] == "main" and expected_label == "A" else "controlled"
        )
        try:
            settings_match = (
                row["label"] == expected_label
                and row["treatment"] == expected_treatment
                and int(row["seed"]) == seeds[row["phase"]] * 100 + row["block"]
                and int(row["callers"]) == CALLERS
                and int(row["waiter_cap"]) == WAITER_CAP
                and int(row["origin_capacity"]) == ORIGIN_CAPACITY
                and int(row["max_attempts"]) == MAX_ATTEMPTS
                and int(row["retry_tokens"]) == RETRY_TOKENS
                and int(row["key_digest"]) == KEY_DIGEST
            )
        except (KeyError, TypeError, ValueError):
            settings_match = False
        if not settings_match:
            raise ValueError(
                "summaries do not follow the predeclared templates, workload "
                "configuration, or seeds"
            )
    if len({row["work_iters"] for row in rows}) != 1:
        raise ValueError("summaries mix more than one calibration")


def block_group_means(
    rows: list[dict[str, Any]], phase: str, field: str, value: str
) -> dict[int, float]:
    """Return equal-period arithmetic means for one group in each block."""
    selected: dict[int, list[float]] = {}
    for row in rows:
        if row["phase"] == phase and row[field] == value:
            selected.setdefault(row["block"], []).append(float(row["burst_ns"]))
    return {block: statistics.fmean(values) for block, values in selected.items()}


def log_block_contrasts(
    rows: list[dict[str, Any]],
    phase: str,
    numerator_field: str,
    numerator_value: str,
    denominator_field: str,
    denominator_value: str,
) -> list[dict[str, float | int]]:
    """Return block log ratios of equal-period burst means."""
    numerator = block_group_means(rows, phase, numerator_field, numerator_value)
    denominator = block_group_means(rows, phase, denominator_field, denominator_value)
    if set(numerator) != set(denominator):
        raise ValueError(f"incomplete {phase} numerator/denominator block pairing")
    contrasts = []
    for block in sorted(numerator):
        if numerator[block] <= 0 or denominator[block] <= 0:
            raise ValueError("burst_ns must be positive for log-ratio analysis")
        contrast = math.log(numerator[block] / denominator[block])
        contrasts.append(
            {
                "block": block,
                "numerator_mean_burst_ns": numerator[block],
                "denominator_mean_burst_ns": denominator[block],
                "log_ratio": contrast,
                "ratio": math.exp(contrast),
            }
        )
    return contrasts


def primary_interval(contrasts: list[dict[str, float | int]]) -> dict[str, Any]:
    """Return the fixed-horizon n=8 paired-t interval on the log scale."""
    values = [float(item["log_ratio"]) for item in contrasts]
    if len(values) != 8:
        raise ValueError(f"primary analysis requires 8 complete blocks, got {len(values)}")
    mean_log = statistics.fmean(values)
    block_sd_log = statistics.stdev(values)
    half_width = T95_N8 * block_sd_log / math.sqrt(len(values))
    low = mean_log - half_width
    high = mean_log + half_width
    return {
        "estimand": "exp(mean block ln(controlled mean burst_ns / naive mean burst_ns))",
        "analysis_scale": "natural log",
        "n_blocks": len(values),
        "mean_log_ratio": mean_log,
        "block_sd_log_ratio": block_sd_log,
        "t_critical_95_df7": T95_N8,
        "ci95_log_low": low,
        "ci95_log_high": high,
        "geometric_mean_ratio": math.exp(mean_log),
        "ci95_ratio_low": math.exp(low),
        "ci95_ratio_high": math.exp(high),
        "block_contrasts": contrasts,
    }


def aa_descriptive(contrasts: list[dict[str, float | int]]) -> dict[str, Any]:
    """Return the label-B/label-A A/A null diagnostic without an interval."""
    values = [float(item["log_ratio"]) for item in contrasts]
    if len(values) != 4:
        raise ValueError(f"A/A diagnostic requires 4 complete blocks, got {len(values)}")
    mean_log = statistics.fmean(values)
    return {
        "interpretation": "descriptive null diagnostic only; no inferential interval",
        "n_blocks": len(values),
        "mean_log_ratio_b_over_a": mean_log,
        "block_sd_log_ratio": statistics.stdev(values),
        "geometric_mean_ratio_b_over_a": math.exp(mean_log),
        "block_contrasts": contrasts,
    }


def treatment_counts(rows: list[dict[str, Any]], treatment: str) -> dict[str, Any]:
    """Return descriptive per-process count identities for main-phase treatment rows."""
    selected = [
        row
        for row in rows
        if row["phase"] == "main" and row["treatment"] == treatment
    ]
    fields = (
        "completed",
        "shed",
        "leaders",
        "followers",
        "flights",
        "origin_attempts",
        "retry_attempts",
    )
    return {
        "processes": len(selected),
        "per_process_unique_values": {
            field: sorted({int(row[field]) for row in selected}) for field in fields
        },
        "mean_burst_ns": statistics.fmean(float(row["burst_ns"]) for row in selected),
        "mean_setup_ns_descriptive": statistics.fmean(
            float(row["setup_ns"]) for row in selected
        ),
    }


def build_analysis(process_directory: Path) -> dict[str, Any]:
    """Build the predeclared single-host analysis document."""
    rows = load_summaries(process_directory)
    check_design(rows)
    main = log_block_contrasts(
        rows,
        "main",
        "treatment",
        "controlled",
        "treatment",
        "naive",
    )
    aa = log_block_contrasts(rows, "aa", "label", "B", "label", "A")
    return {
        "parameters": {
            "primary_metric": "burst_ns",
            "main_blocks": 8,
            "aa_blocks": 4,
            "experimental_unit": "one fresh process",
            "analysis_unit": "one complete four-process block contrast",
            "within_block_summary": "equal-period arithmetic mean by treatment or label",
            "fixed_horizon": True,
            "failed_period_policy": "invalidate the whole run; no replacement",
            "independence_boundary": (
                "logical callers and physical attempts are dependent receipts, not analysis units"
            ),
            "host_boundary": "analyze each retained host directory separately",
        },
        "primary": primary_interval(main),
        "aa_diagnostic": aa_descriptive(aa),
        "descriptive_counts": {
            treatment: treatment_counts(rows, treatment)
            for treatment in ("naive", "controlled")
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
