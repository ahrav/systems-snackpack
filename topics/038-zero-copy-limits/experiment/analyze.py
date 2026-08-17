#!/usr/bin/env python3
"""Summarize complete-block process-level log contrasts."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path


T_CRITICAL_975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}

FLOAT_FIELDS = (
    "transfer_sec",
    "setup_sec",
    "total_sec",
    "sender_cpu_sec",
    "receiver_cpu_sec",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    """Read only successful, verified timing process records."""

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError("runs table is empty")
    for row in rows:
        if row["rc"] != "0" or row["ok"] != "1":
            raise ValueError(f"failed process in {row['run_id']}")
        for field in FLOAT_FIELDS:
            value = float(row[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid {field} in {row['run_id']}")
        outer_ns = int(row["outer_ns"])
        if outer_ns <= 0:
            raise ValueError(f"invalid outer_ns in {row['run_id']}")
        row["outer_sec"] = str(outer_ns / 1_000_000_000)
    return rows


def interval(log_contrasts: list[float]) -> tuple[float, float, float, float]:
    """Return geometric ratio, low/high interval, and sample dispersion."""

    if len(log_contrasts) < 2:
        raise ValueError("at least two complete blocks are required")
    degrees = len(log_contrasts) - 1
    if degrees not in T_CRITICAL_975:
        raise ValueError("Student-t table supports at most 31 blocks")
    mean = statistics.mean(log_contrasts)
    deviation = statistics.stdev(log_contrasts)
    half_width = T_CRITICAL_975[degrees] * deviation / math.sqrt(len(log_contrasts))
    return math.exp(mean), math.exp(mean - half_width), math.exp(mean + half_width), deviation


def summarize(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Build one contrast row per block and one summary row per method pair."""

    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["pair"], int(row["block"]))].append(row)

    contrast_rows: list[dict[str, str]] = []
    for (pair, block), block_rows in sorted(grouped.items()):
        if len(block_rows) != 4:
            raise ValueError(f"{pair} block {block} has {len(block_rows)} rows")
        labels = "".join(row["label"] for row in sorted(block_rows, key=lambda row: int(row["position"])))
        if labels not in {"ABBA", "BAAB"}:
            raise ValueError(f"{pair} block {block} has invalid order {labels}")
        for field in ("transfer_sec", "setup_sec"):
            a = [math.log(float(row[field])) for row in block_rows if row["label"] == "A"]
            b = [math.log(float(row[field])) for row in block_rows if row["label"] == "B"]
            contrast_rows.append(
                {
                    "pair": pair,
                    "block": str(block),
                    "metric": field,
                    "log_B_over_A": f"{statistics.mean(b) - statistics.mean(a):.12f}",
                }
            )

    summary_rows: list[dict[str, str]] = []
    for pair in sorted({row["pair"] for row in rows}):
        selected = [row for row in rows if row["pair"] == pair]
        for metric in ("transfer_sec", "setup_sec"):
            log_contrasts = [
                float(row["log_B_over_A"])
                for row in contrast_rows
                if row["pair"] == pair and row["metric"] == metric
            ]
            ratio, low, high, deviation = interval(log_contrasts)
            a_values = [float(row[metric]) for row in selected if row["label"] == "A"]
            b_values = [float(row[metric]) for row in selected if row["label"] == "B"]
            summary_rows.append(
                {
                    "pair": pair,
                    "metric": metric,
                    "complete_blocks": str(len(log_contrasts)),
                    "process_runs": str(len(selected)),
                    "ratio_B_over_A": f"{ratio:.9f}",
                    "ci95_low": f"{low:.9f}",
                    "ci95_high": f"{high:.9f}",
                    "sd_log_block_contrast": f"{deviation:.9f}",
                    "median_A_sec": f"{statistics.median(a_values):.9f}",
                    "median_B_sec": f"{statistics.median(b_values):.9f}",
                }
            )
        for metric in ("sender_cpu_sec", "receiver_cpu_sec", "total_sec", "outer_sec"):
            a_values = [float(row[metric]) for row in selected if row["label"] == "A"]
            b_values = [float(row[metric]) for row in selected if row["label"] == "B"]
            summary_rows.append(
                {
                    "pair": pair,
                    "metric": metric,
                    "complete_blocks": str(len({row["block"] for row in selected})),
                    "process_runs": str(len(selected)),
                    "ratio_B_over_A": "not-estimated",
                    "ci95_low": "not-estimated",
                    "ci95_high": "not-estimated",
                    "sd_log_block_contrast": "not-estimated",
                    "median_A_sec": f"{statistics.median(a_values):.9f}",
                    "median_B_sec": f"{statistics.median(b_values):.9f}",
                }
            )
    return contrast_rows, summary_rows


def write_table(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a deterministic tab-separated table."""

    if not rows:
        raise ValueError(f"refusing to write empty table {path}")
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--contrasts", type=Path, required=True)
    arguments = parser.parse_args()
    rows = read_rows(arguments.runs)
    contrasts, summaries = summarize(rows)
    write_table(arguments.contrasts, contrasts)
    write_table(arguments.summary, summaries)
    for row in summaries:
        if row["metric"] == "transfer_sec":
            print(
                f"pair={row['pair']} complete_blocks={row['complete_blocks']} "
                f"process_runs={row['process_runs']} ratio_B_over_A={row['ratio_B_over_A']} "
                f"ci95_B_over_A=[{row['ci95_low']},{row['ci95_high']}] "
                f"sd_log_block_contrast={row['sd_log_block_contrast']} "
                f"median_A_sec={row['median_A_sec']} median_B_sec={row['median_B_sec']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
