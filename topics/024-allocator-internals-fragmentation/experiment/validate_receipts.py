#!/usr/bin/env python3
"""Validate Topic 24 process counts, controls, and summary receipts.

Every check is exact: each receipt row is bound to its expected
``(block, period)`` position in the predeclared schedule rebuilt from the
templates in ``run_processes``, every probe control is checked, and the
complete summary is recomputed from the NDJSON receipts before ``PASS`` is
reported.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_processes import AA_TEMPLATES, AB_TEMPLATES, summarize

# Literal protocol constants, asserted independently of the imported
# templates so a template edit in run_processes cannot silently validate
# itself against a different design.
PROTOCOL_AB_BLOCKS = 12
PROTOCOL_AA_BLOCKS = 4
PROTOCOL_PERIODS = 4


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
    """Bind each receipt to its scheduled position and check probe controls."""
    expected_positions = [
        (block, period, template, template[period - 1])
        for block, template in enumerate(templates, start=1)
        for period in range(1, 5)
    ]
    require(len(rows) == len(expected_positions), f"wrong {phase} process count")
    # pi-lens-ignore: B905
    for number, (row, position) in enumerate(zip(rows, expected_positions), start=1):
        block, period, template, label = position
        pattern = "scattered" if phase == "ab" and label == "B" else "compact"
        require(
            int(row["block"]) == block and int(row["period"]) == period,
            f"{phase} receipt {number} is out of schedule order",
        )
        require(row["phase"] == phase, f"wrong phase in {phase} receipt {number}")
        require(
            row["template"] == template, f"wrong template in {phase} receipt {number}"
        )
        require(row["label"] == label, f"wrong label in {phase} receipt {number}")
        require(row["pattern"] == pattern, f"wrong treatment in {phase} receipt {number}")
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


def require_equal(expected: Any, actual: Any, context: str) -> None:
    """Require deep equality with float tolerance."""
    if isinstance(expected, float) or isinstance(actual, float):
        require(
            isinstance(actual, (int, float))
            and isinstance(expected, (int, float))
            and math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-12),
            f"summary {context} does not match the receipts",
        )
    elif isinstance(expected, dict):
        require(
            isinstance(actual, dict) and set(actual) == set(expected),
            f"summary {context} keys do not match the receipts",
        )
        for key in expected:
            require_equal(expected[key], actual[key], f"{context}.{key}")
    elif isinstance(expected, list):
        require(
            isinstance(actual, list) and len(actual) == len(expected),
            f"summary {context} length does not match the receipts",
        )
        # pi-lens-ignore: B905
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            require_equal(expected_item, actual_item, f"{context}[{index}]")
    else:
        require(actual == expected, f"summary {context} does not match the receipts")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("process_directory", type=Path)
    args = parser.parse_args()

    ab_rows = load_rows(args.process_directory / "ab.ndjson")
    aa_rows = load_rows(args.process_directory / "aa.ndjson")
    require(
        len(AB_TEMPLATES) == PROTOCOL_AB_BLOCKS
        and len(AA_TEMPLATES) == PROTOCOL_AA_BLOCKS
        and all(len(t) == PROTOCOL_PERIODS for t in AB_TEMPLATES + AA_TEMPLATES),
        "run_processes templates deviate from the predeclared protocol",
    )
    require(
        len(ab_rows) == PROTOCOL_AB_BLOCKS * PROTOCOL_PERIODS
        and len(aa_rows) == PROTOCOL_AA_BLOCKS * PROTOCOL_PERIODS,
        "receipt counts deviate from the predeclared protocol",
    )
    validate_rows(ab_rows, "ab", AB_TEMPLATES)
    validate_rows(aa_rows, "aa", AA_TEMPLATES)
    all_rows = ab_rows + aa_rows
    require(len({int(row["pid"]) for row in all_rows}) == 64, "PIDs are not unique")

    summary = json.loads((args.process_directory / "summary.json").read_text())
    # Independent shape checks first: these do not rely on the producer's
    # summarize logic, so an inverted interval cannot validate itself.
    comparisons = {entry["phase"]: entry for entry in summary["comparisons"]}
    require(comparisons["ab"]["blocks"] == PROTOCOL_AB_BLOCKS, "A/B block count changed")
    require(comparisons["aa"]["blocks"] == PROTOCOL_AA_BLOCKS, "A/A block count changed")
    for entry in comparisons.values():
        for key in ("rss_trimmed_kb_ratio", "alloc_ns_ratio"):
            result = entry[key]
            values = (result["ci95_low"], result["estimate"], result["ci95_high"])
            require(
                all(math.isfinite(value) and value > 0 for value in values),
                "invalid ratio",
            )
            require(values[0] <= values[1] <= values[2], "unordered ratio interval")
        result = entry["rss_trimmed_kb_difference"]
        values = (result["ci95_low"], result["estimate"], result["ci95_high"])
        require(all(math.isfinite(value) for value in values), "invalid difference")
        require(values[0] <= values[1] <= values[2], "unordered difference interval")
    # A stale or fabricated summary must not pass: rebuild the complete
    # summary from the validated receipts and require agreement.
    recomputed = summarize(all_rows)
    for section in ("comparisons", "treatment_medians"):
        require_equal(recomputed[section], summary.get(section), section)
    for key, value in recomputed["parameters"].items():
        if key == "probe_environment_blocklist" and key not in summary["parameters"]:
            # Receipts recorded before the blocklist parameter existed.
            continue
        require_equal(value, summary["parameters"].get(key), f"parameters.{key}")

    print("receipt validation: PASS")


if __name__ == "__main__":
    main()
