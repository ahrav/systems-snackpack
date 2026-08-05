#!/usr/bin/env python3
"""Run the predeclared Topic 24 allocator-fragmentation schedule."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

AB_TEMPLATES = (
    "BAAB",
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
)
AA_TEMPLATES = ("BAAB", "ABBA", "BAAB", "ABBA")
T95 = {12: 2.2009851601, 4: 3.1824463053}
COUNT = 262_144
BLOCK_SIZE = 256
# Inherited allocator controls would change probe behavior while the source
# and binary hashes still match; every probe runs without them.
PROBE_ENV_BLOCKLIST = (
    "GLIBC_TUNABLES",
    "LD_AUDIT",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "MALLOC_CHECK_",
    "MALLOC_PERTURB_",
    "MALLOC_ARENA_MAX",
    "MALLOC_ARENA_TEST",
    "MALLOC_MMAP_THRESHOLD_",
    "MALLOC_TRIM_THRESHOLD_",
    "MALLOC_TOP_PAD_",
    "MALLOC_MMAP_MAX_",
)


def run_one(
    binary: Path,
    cpu: str,
    phase: str,
    template: str,
    label: str,
    block: int,
    period: int,
) -> dict[str, Any]:
    """Run one fresh process and add assignment metadata."""
    pattern = "scattered" if phase == "ab" and label == "B" else "compact"
    command = [
        "taskset",
        "--cpu-list",
        cpu,
        str(binary),
        pattern,
        label,
        str(block),
        str(period),
        str(COUNT),
        str(BLOCK_SIZE),
    ]
    started = time.monotonic_ns()
    probe_env = {
        key: value
        for key, value in os.environ.items()
        if key not in PROBE_ENV_BLOCKLIST
    }
    process = subprocess.run(
        command, check=True, capture_output=True, text=True, env=probe_env
    )
    process_wall_ns = time.monotonic_ns() - started
    row = json.loads(process.stdout)
    expected = {
        "pattern": pattern,
        "label": label,
        "block": block,
        "period": period,
        "count": COUNT,
        "block_size": BLOCK_SIZE,
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"child receipt mismatch for {key}: {process.stdout!r}")
    row.update(
        {
            "phase": phase,
            "template": template,
            "process_wall_ns": process_wall_ns,
        }
    )
    return row


def block_contrasts(
    rows: list[dict[str, Any]], phase: str, metric: str, logarithmic: bool
) -> list[float]:
    """Return B minus A contrasts for complete four-period blocks."""
    contrasts = []
    blocks = sorted({int(row["block"]) for row in rows if row["phase"] == phase})
    for block in blocks:
        selected = [
            row for row in rows if row["phase"] == phase and row["block"] == block
        ]
        a_values = [float(row[metric]) for row in selected if row["label"] == "A"]
        b_values = [float(row[metric]) for row in selected if row["label"] == "B"]
        if len(a_values) != 2 or len(b_values) != 2:
            raise ValueError(f"incomplete {phase} block {block}")
        if logarithmic:
            if min(a_values + b_values) <= 0:
                raise ValueError(f"nonpositive {metric} in {phase} block {block}")
            contrasts.append(
                statistics.fmean(map(math.log, b_values))
                - statistics.fmean(map(math.log, a_values))
            )
        else:
            contrasts.append(statistics.fmean(b_values) - statistics.fmean(a_values))
    return contrasts


def interval(contrasts: list[float], logarithmic: bool) -> dict[str, float]:
    """Compute a t interval over block contrasts."""
    mean = statistics.fmean(contrasts)
    deviation = statistics.stdev(contrasts)
    half_width = T95[len(contrasts)] * deviation / math.sqrt(len(contrasts))
    if logarithmic:
        return {
            "estimate": math.exp(mean),
            "ci95_low": math.exp(mean - half_width),
            "ci95_high": math.exp(mean + half_width),
            "block_log_sd": deviation,
        }
    return {
        "estimate": mean,
        "ci95_low": mean - half_width,
        "ci95_high": mean + half_width,
        "block_sd": deviation,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the primary RSS estimand and timing diagnostic."""
    comparisons = []
    for phase in ("ab", "aa"):
        rss_ratio = interval(
            block_contrasts(rows, phase, "rss_trimmed_kb", True), True
        )
        rss_difference = interval(
            block_contrasts(rows, phase, "rss_trimmed_kb", False), False
        )
        alloc_ratio = interval(block_contrasts(rows, phase, "alloc_ns", True), True)
        comparisons.append(
            {
                "phase": phase,
                "estimand": "B/A",
                "blocks": len(AB_TEMPLATES if phase == "ab" else AA_TEMPLATES),
                "processes": 4
                * len(AB_TEMPLATES if phase == "ab" else AA_TEMPLATES),
                "rss_trimmed_kb_ratio": rss_ratio,
                "rss_trimmed_kb_difference": rss_difference,
                "alloc_ns_ratio": alloc_ratio,
            }
        )

    treatment_rows = [row for row in rows if row["phase"] == "ab"]
    medians = {}
    for pattern in ("compact", "scattered"):
        selected = [row for row in treatment_rows if row["pattern"] == pattern]
        medians[pattern] = {
            metric: statistics.median(float(row[metric]) for row in selected)
            for metric in (
                "rss_freed_kb",
                "rss_trimmed_kb",
                "anonymous_trimmed_kb",
                "arena_trimmed",
                "uord_trimmed",
                "live_requested",
                "live_usable",
            )
        }

    return {
        "parameters": {
            "count": COUNT,
            "block_size": BLOCK_SIZE,
            "survivor_spacing": 16,
            "ab_templates": list(AB_TEMPLATES),
            "aa_templates": list(AA_TEMPLATES),
            "probe_environment_blocklist": list(PROBE_ENV_BLOCKLIST),
            "treatment_application": "one fresh process",
            "analysis_unit": "one complete four-process block contrast",
        },
        "comparisons": comparisons,
        "treatment_medians": medians,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("cpu")
    args = parser.parse_args()

    if shutil.which("taskset") is None:
        raise SystemExit("taskset is required; run this harness on Linux")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    if any(args.output_directory.iterdir()):
        raise SystemExit("output directory must be empty")

    rows: list[dict[str, Any]] = []
    for phase, templates in (("ab", AB_TEMPLATES), ("aa", AA_TEMPLATES)):
        output_path = args.output_directory / f"{phase}.ndjson"
        with output_path.open("w", encoding="utf-8") as output:
            for block, template in enumerate(templates, start=1):
                for period, label in enumerate(template, start=1):
                    row = run_one(
                        args.binary,
                        args.cpu,
                        phase,
                        template,
                        label,
                        block,
                        period,
                    )
                    rows.append(row)
                    output.write(json.dumps(row, sort_keys=True) + "\n")
                    output.flush()

    summary = summarize(rows)
    (args.output_directory / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
