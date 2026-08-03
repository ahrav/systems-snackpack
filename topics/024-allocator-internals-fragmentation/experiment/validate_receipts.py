#!/usr/bin/env python3
"""Validate Topic 24 process counts, controls, and summary receipts."""

from __future__ import annotations

import argparse
import json
import math
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


def load_rows(path: Path) -> list[dict[str, Any]]:
    """Load newline-delimited JSON receipts."""
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def require(condition: bool, message: str) -> None:
    """Stop validation when an invariant fails."""
    if not condition:
        raise SystemExit(message)


def validate_rows(
    rows: list[dict[str, Any]], phase: str, templates: tuple[str, ...]
) -> None:
    """Validate assignments, treatment identity, and probe controls."""
    require(len(rows) == 4 * len(templates), f"wrong {phase} process count")
    for row in rows:
        block = int(row["block"])
        period = int(row["period"])
        require(1 <= block <= len(templates), f"invalid {phase} block")
        require(1 <= period <= 4, f"invalid {phase} period")
        template = templates[block - 1]
        label = template[period - 1]
        pattern = "scattered" if phase == "ab" and label == "B" else "compact"
        require(row["phase"] == phase, f"wrong phase in {phase} receipt")
        require(row["template"] == template, f"wrong template in {phase} receipt")
        require(row["label"] == label, f"wrong label in {phase} receipt")
        require(row["pattern"] == pattern, f"wrong treatment in {phase} receipt")
        require(int(row["count"]) == 262_144, "allocation count changed")
        require(int(row["block_size"]) == 256, "requested size changed")
        require(int(row["survivors"]) == 16_384, "survivor count changed")
        require(int(row["live_requested"]) == 4_194_304, "live bytes changed")
        require(int(row["live_usable"]) == 4_325_376, "usable bytes changed")
        require(row["checksum"] == row["expected_checksum"], "checksum mismatch")
        require(int(row["trim_result"]) == 1, "malloc_trim released no memory")
        require(int(row["uord_trimmed"]) == 6_557_696, "uordblks changed")
        for key in (
            "alloc_ns",
            "free_ns",
            "trim_ns",
            "process_wall_ns",
            "rss_full_kb",
            "rss_freed_kb",
            "rss_trimmed_kb",
            "anonymous_trimmed_kb",
            "arena_trimmed",
        ):
            require(int(row[key]) > 0, f"nonpositive {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("process_directory", type=Path)
    args = parser.parse_args()

    ab_rows = load_rows(args.process_directory / "ab.ndjson")
    aa_rows = load_rows(args.process_directory / "aa.ndjson")
    validate_rows(ab_rows, "ab", AB_TEMPLATES)
    validate_rows(aa_rows, "aa", AA_TEMPLATES)
    all_rows = ab_rows + aa_rows
    require(len({int(row["pid"]) for row in all_rows}) == 64, "PIDs are not unique")

    summary = json.loads((args.process_directory / "summary.json").read_text())
    require(summary["parameters"]["ab_templates"] == list(AB_TEMPLATES), "A/B schedule drift")
    require(summary["parameters"]["aa_templates"] == list(AA_TEMPLATES), "A/A schedule drift")
    comparisons = {entry["phase"]: entry for entry in summary["comparisons"]}
    require(comparisons["ab"]["blocks"] == 12, "A/B block count changed")
    require(comparisons["aa"]["blocks"] == 4, "A/A block count changed")
    for entry in comparisons.values():
        for key in ("rss_trimmed_kb_ratio", "alloc_ns_ratio"):
            result = entry[key]
            values = (result["ci95_low"], result["estimate"], result["ci95_high"])
            require(all(math.isfinite(value) and value > 0 for value in values), "invalid ratio")
            require(values[0] <= values[1] <= values[2], "unordered ratio interval")
        result = entry["rss_trimmed_kb_difference"]
        values = (result["ci95_low"], result["estimate"], result["ci95_high"])
        require(all(math.isfinite(value) for value in values), "invalid difference")
        require(values[0] <= values[1] <= values[2], "unordered difference interval")

    print("receipt validation: PASS")


if __name__ == "__main__":
    main()
