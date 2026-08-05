#!/usr/bin/env python3
"""Run order-balanced atomic cost comparisons as fresh Linux processes."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
from pathlib import Path

COMPARISONS = (
    ("store_release_relaxed", "store_relaxed", "store_release", "store"),
    ("store_seqcst_release", "store_release", "store_seqcst", "store"),
    ("fetch_add_seqcst_relaxed", "fetch_add_relaxed", "fetch_add_seqcst", "rmw"),
)


def parse_result(output: str) -> dict[str, str]:
    """Parse one benchmark result line.

    Args:
        output: Whitespace-separated key-value fields from the probe.

    Returns:
        The fields keyed by their names.
    """
    return dict(field.split("=", 1) for field in output.strip().split())


def run(binary: Path, cpu: str, operation: str, iterations: int) -> dict[str, str]:
    """Run one CPU-pinned fresh process.

    Args:
        binary: Atomic-cost probe to execute.
        cpu: Linux CPU-list expression for taskset.
        operation: Operation name accepted by the probe.
        iterations: Number of timed loop iterations.

    Returns:
        The reported fields plus the executed command.

    Raises:
        SystemExit: If the probe output is missing required fields or does
            not echo the requested operation and iteration count.
    """
    command = [
        "taskset",
        "--cpu-list",
        cpu,
        str(binary),
        operation,
        str(iterations),
    ]
    completed = subprocess.run(
        command, check=True, text=True, capture_output=True, timeout=300
    )
    result = parse_result(completed.stdout)
    required = {"operation", "iterations", "elapsed_ns", "ns_per_operation", "checksum"}
    missing = required - result.keys()
    if missing:
        raise SystemExit(f"probe output missing fields {sorted(missing)}: {command}")
    if result["operation"] != operation or result["iterations"] != str(iterations):
        raise SystemExit(f"probe echoed a different request: {command} -> {result}")
    result["command"] = " ".join(command)
    return result


def quartiles(values: list[float]) -> tuple[float, float]:
    """Calculate inclusive sample quartiles.

    Args:
        values: Finite observations containing at least two values.

    Returns:
        The first and third quartiles.
    """
    cuts = statistics.quantiles(values, n=4, method="inclusive")
    return cuts[0], cuts[2]


def main() -> None:
    """Execute balanced process blocks and retain their receipts.

    Args:
        Command-line arguments are read from the process environment.

    Returns:
        None.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cpu", default="3")
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--store-iterations", type=int, default=50_000_000)
    parser.add_argument("--rmw-iterations", type=int, default=10_000_000)
    args = parser.parse_args()
    if args.blocks < 2:
        raise SystemExit("--blocks must be at least 2 for quartile aggregation")
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)

    rows: list[dict[str, str | int]] = []
    for block in range(args.blocks):
        for comparison, left, right, iteration_kind in COMPARISONS:
            iterations = (
                args.store_iterations if iteration_kind == "store" else args.rmw_iterations
            )
            order = [left, right, right, left] if block % 2 == 0 else [right, left, left, right]
            for slot, operation in enumerate(order):
                row: dict[str, str | int] = {
                    "comparison": comparison,
                    "block": block,
                    "slot": slot,
                }
                row.update(run(args.binary, args.cpu, operation, iterations))
                rows.append(row)

        for slot in range(4):
            arm = "A" if slot in (0, 3) else "B"
            row = {
                "comparison": "store_relaxed_aa",
                "block": block,
                "slot": slot,
                "arm": arm,
            }
            row.update(
                run(args.binary, args.cpu, "store_relaxed", args.store_iterations)
            )
            rows.append(row)

    raw_path = args.output / "raw.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)

    summaries = []
    for comparison, left, right, _ in COMPARISONS:
        ratios = []
        for block in range(args.blocks):
            group = [
                row
                for row in rows
                if row["comparison"] == comparison and row["block"] == block
            ]
            left_logs = [
                math.log(float(row["ns_per_operation"]))
                for row in group
                if row["operation"] == left
            ]
            right_logs = [
                math.log(float(row["ns_per_operation"]))
                for row in group
                if row["operation"] == right
            ]
            ratios.append(math.exp(statistics.mean(right_logs) - statistics.mean(left_logs)))
        q1, q3 = quartiles(ratios)
        summaries.append(
            {
                "comparison": comparison,
                "ratio": f"{right}/{left}",
                "blocks": args.blocks,
                "processes": args.blocks * 4,
                "median_paired_ratio": statistics.median(ratios),
                "ratio_iqr": [q1, q3],
                "ratio_range": [min(ratios), max(ratios)],
            }
        )

    aa_ratios = []
    for block in range(args.blocks):
        group = [
            row
            for row in rows
            if row["comparison"] == "store_relaxed_aa" and row["block"] == block
        ]
        # The A/A control uses the same order-balanced four-slot schedule and
        # the same log-ratio estimator as the treatment comparisons.
        a_logs = [
            math.log(float(row["ns_per_operation"])) for row in group if row["arm"] == "A"
        ]
        b_logs = [
            math.log(float(row["ns_per_operation"])) for row in group if row["arm"] == "B"
        ]
        aa_ratios.append(math.exp(statistics.mean(b_logs) - statistics.mean(a_logs)))
    q1, q3 = quartiles(aa_ratios)
    summaries.append(
        {
            "comparison": "store_relaxed_aa",
            "ratio": "B/A",
            "blocks": args.blocks,
            "processes": args.blocks * 4,
            "median_paired_ratio": statistics.median(aa_ratios),
            "ratio_iqr": [q1, q3],
            "ratio_range": [min(aa_ratios), max(aa_ratios)],
        }
    )
    (args.output / "summary.json").write_text(
        json.dumps(summaries, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
