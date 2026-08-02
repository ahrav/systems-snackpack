#!/usr/bin/env python3
"""Run fixed-order fresh-process comparisons for the Topic 23 CAS kernels."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import statistics
import subprocess
import time
from pathlib import Path

AB_TEMPLATES = (
    "ABBA",
    "ABBA",
    "ABBA",
    "BAAB",
    "ABBA",
    "ABBA",
    "BAAB",
    "BAAB",
    "ABBA",
    "BAAB",
    "BAAB",
    "BAAB",
)
AA_TEMPLATES = ("LRRL", "RLLR", "LRRL", "RLLR", "RLLR", "LRRL")
T95 = {6: 2.5705818366, 12: 2.2009851601}


def parse_line(line: str) -> dict[str, str]:
    fields = line.strip().split(",")
    if not fields or fields[0] != "bench":
        raise ValueError(f"unexpected benchmark output: {line!r}")
    return dict(field.split("=", 1) for field in fields[1:])


def run_one(binary: Path, cpu: str, mode: str, iterations: int) -> dict[str, object]:
    started = time.monotonic_ns()
    process = subprocess.run(
        ["taskset", "--cpu-list", cpu, str(binary), "bench", mode, str(iterations)],
        check=True,
        capture_output=True,
        text=True,
    )
    process_wall_ns = time.monotonic_ns() - started
    parsed = parse_line(process.stdout)
    if parsed["mode"] != mode or int(parsed["iters"]) != iterations:
        raise ValueError(f"child reported a different treatment: {process.stdout!r}")
    return {
        "mode": mode,
        "elapsed_ns": int(parsed["elapsed_ns"]),
        "ns_per_iter": float(parsed["ns_per_iter"]),
        "iterations": int(parsed["iters"]),
        "checksum": int(parsed["checksum"]),
        "final_word": int(parsed["final_word"]),
        "process_wall_ns": process_wall_ns,
    }


def summarize(rows: list[dict[str, object]], phase: str, numerator: str, denominator: str) -> dict[str, object]:
    blocks = sorted({int(row["block"]) for row in rows if row["phase"] == phase})
    contrasts: list[float] = []
    for block in blocks:
        selected = [
            row
            for row in rows
            if row["phase"] == phase and int(row["block"]) == block
        ]
        n_values = [
            math.log(int(row["elapsed_ns"]))
            for row in selected
            if row["label"] == numerator
        ]
        d_values = [
            math.log(int(row["elapsed_ns"]))
            for row in selected
            if row["label"] == denominator
        ]
        if len(n_values) != 2 or len(d_values) != 2:
            raise ValueError(f"incomplete {phase} block {block}")
        contrasts.append(statistics.fmean(n_values) - statistics.fmean(d_values))

    mean = statistics.fmean(contrasts)
    deviation = statistics.stdev(contrasts)
    half_width = T95[len(contrasts)] * deviation / math.sqrt(len(contrasts))
    block_ratios = [math.exp(value) for value in contrasts]
    return {
        "phase": phase,
        "estimand": f"{numerator}/{denominator}",
        "blocks": len(contrasts),
        "processes": len(contrasts) * 4,
        "geometric_mean_ratio": math.exp(mean),
        "ci95_low": math.exp(mean - half_width),
        "ci95_high": math.exp(mean + half_width),
        "block_log_sd": deviation,
        "min_block_ratio": min(block_ratios),
        "max_block_ratio": max(block_ratios),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("cpu")
    parser.add_argument("--iterations", type=int, default=5_000_000)
    args = parser.parse_args()

    if shutil.which("taskset") is None:
        raise SystemExit("taskset is required; run this process harness on Linux")

    args.output_directory.mkdir(parents=True, exist_ok=True)
    if any(args.output_directory.iterdir()):
        raise SystemExit("output directory must be empty")
    rows: list[dict[str, object]] = []

    for phase, templates in (("ab", AB_TEMPLATES), ("aa", AA_TEMPLATES)):
        for block, template in enumerate(templates, start=1):
            for period, label in enumerate(template, start=1):
                mode = "tagged" if phase == "ab" and label == "B" else "raw"
                row = run_one(args.binary, args.cpu, mode, args.iterations)
                row.update(
                    {
                        "phase": phase,
                        "block": block,
                        "period": period,
                        "template": template,
                        "label": label,
                    }
                )
                rows.append(row)

    fieldnames = [
        "phase",
        "block",
        "period",
        "template",
        "label",
        "mode",
        "elapsed_ns",
        "ns_per_iter",
        "iterations",
        "checksum",
        "final_word",
        "process_wall_ns",
    ]
    with (args.output_directory / "raw.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "parameters": {
            "cpu": args.cpu,
            "iterations_per_process": args.iterations,
            "ab_templates": list(AB_TEMPLATES),
            "aa_templates": list(AA_TEMPLATES),
            "timed_region": "one in-process kernel call after warmup",
        },
        "comparisons": [
            summarize(rows, "ab", "B", "A"),
            summarize(rows, "aa", "R", "L"),
        ],
    }
    (args.output_directory / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
