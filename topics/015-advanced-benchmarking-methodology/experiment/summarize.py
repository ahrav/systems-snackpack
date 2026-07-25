#!/usr/bin/env python3
"""Validate process records and summarize order-balanced label ratios."""

from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# One row per timed position, prefixed with the runner's block/launch/run
# accounting. Rejecting any other header keeps a drifted producer from
# silently mislabeling columns in retained evidence.
EXPECTED_FIELDS = [
    "block",
    "launch",
    "run",
    "pid",
    "order",
    "position",
    "label",
    "elapsed_ns",
    "checksum",
    "target_bytes",
    "thrash_bytes",
]


@dataclass
class Run:
    """One process's identity plus its per-label and per-position intervals."""

    pid: int
    block: int
    order: str
    labels: dict[str, int] = field(default_factory=dict)
    positions: dict[int, int] = field(default_factory=dict)


def quantile(values: list[float], probability: float) -> float:
    """Return the type-7 quantile used by R and NumPy's default method."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def metric_row(name: str, unit: str, values: list[float]) -> list[str]:
    """Format one validated metric and its process-level dispersion."""
    q1 = quantile(values, 0.25)
    median = quantile(values, 0.5)
    q3 = quantile(values, 0.75)
    return [
        name,
        unit,
        str(len(values)),
        f"{statistics.fmean(values):.6f}",
        f"{statistics.stdev(values):.6f}" if len(values) > 1 else "0.000000",
        f"{median:.6f}",
        f"{q1:.6f}",
        f"{q3:.6f}",
        f"{q3 - q1:.6f}",
        f"{min(values):.6f}",
        f"{max(values):.6f}",
    ]


def main() -> None:
    """Read raw CSV, reject malformed or incomplete records, and write summary CSV."""
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} RAW.csv SUMMARY.csv")

    raw_path = Path(sys.argv[1])
    summary_path = Path(sys.argv[2])
    runs: dict[int, Run] = {}
    block_runs: dict[int, dict[str, int]] = defaultdict(dict)
    checksums: set[int] = set()

    with raw_path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != EXPECTED_FIELDS:
            raise SystemExit(f"unexpected header: {reader.fieldnames}")
        for row in reader:
            run = int(row["run"])
            block = int(row["block"])
            order = row["order"]
            label = row["label"]
            position = int(row["position"])
            elapsed_ns = int(row["elapsed_ns"])
            # Ratios require strictly positive intervals; a zero would turn a
            # label ratio into a division error or a non-finite log.
            if elapsed_ns <= 0:
                raise SystemExit(f"non-positive elapsed_ns for run {run}")
            checksums.add(int(row["checksum"]))

            record = runs.setdefault(
                run,
                Run(pid=int(row["pid"]), block=block, order=order),
            )
            if record.pid != int(row["pid"]) or record.order != order or record.block != block:
                raise SystemExit(f"inconsistent process record for run {run}")
            if label in record.labels or position in record.positions:
                raise SystemExit(f"duplicate row for run {run}")
            record.labels[label] = elapsed_ns
            record.positions[position] = elapsed_ns
            if block_runs[block].get(order, run) != run:
                raise SystemExit(f"block {block} has more than one {order} process")
            block_runs[block][order] = run

    if len(checksums) != 1:
        raise SystemExit(f"expected one checksum, found {len(checksums)}")
    if len({record.pid for record in runs.values()}) != len(runs):
        raise SystemExit("each run must use a fresh process")

    metrics: dict[str, list[float]] = defaultdict(list)
    for run, record in runs.items():
        labels = record.labels
        positions = record.positions
        if set(labels) != {"A", "B"} or set(positions) != {1, 2}:
            raise SystemExit(f"incomplete process record for run {run}")

        label_ratio = labels["A"] / labels["B"]
        metrics["position_1_elapsed"].append(float(positions[1]))
        metrics["position_2_elapsed"].append(float(positions[2]))
        metrics["position_first_over_second"].append(positions[1] / positions[2])
        metrics[f"fixed_{record.order}_label_A_over_B"].append(label_ratio)

    for block, orders in sorted(block_runs.items()):
        if set(orders) != {"AB", "BA"}:
            raise SystemExit(f"block {block} is missing AB or BA")
        ab = runs[orders["AB"]].labels
        ba = runs[orders["BA"]].labels
        # Log-space mean of the two ratios, mirroring the reference
        # `order_cancelled_ratio` in src/lib.rs; both inputs are strictly
        # positive because every elapsed_ns is validated above.
        cancelled = math.exp((math.log(ab["A"] / ab["B"]) + math.log(ba["A"] / ba["B"])) / 2.0)
        metrics["order_cancelled_label_A_over_B"].append(cancelled)

    units = {
        "position_1_elapsed": "ns",
        "position_2_elapsed": "ns",
        "position_first_over_second": "ratio",
        "fixed_AB_label_A_over_B": "ratio",
        "fixed_BA_label_A_over_B": "ratio",
        "order_cancelled_label_A_over_B": "ratio",
    }
    with summary_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(
            ["metric", "unit", "n", "mean", "sd", "median", "q1", "q3", "iqr", "min", "max"]
        )
        for name in units:
            writer.writerow(metric_row(name, units[name], metrics[name]))


if __name__ == "__main__":
    main()
