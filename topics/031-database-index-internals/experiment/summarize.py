#!/usr/bin/env python3
"""Validate and summarize retained Topic 31 paired process records."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


EXPECTED_ORDERS = {
    "ABBA": ("narrow", "covering", "covering", "narrow"),
    "BAAB": ("covering", "narrow", "narrow", "covering"),
}
LAYOUT_FIELDS = (
    "logical_narrow_index",
    "logical_heap",
    "logical_covering_index",
    "rust_narrow_entry",
    "rust_payload",
    "rust_covering_entry",
)


def geometric_mean(values: list[float]) -> float:
    """Return the geometric mean of positive values."""

    return math.exp(statistics.fmean(math.log(value) for value in values))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metadata = json.loads((args.output / "metadata.json").read_text(encoding="utf-8"))
    check = json.loads((args.output / "check.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (args.output / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    blocks = int(metadata["blocks"])
    errors: list[str] = []
    if check["exit_code"] != 0 or "CHECK_OK" not in check["stdout"]:
        errors.append("fresh-process correctness check failed")
    if len(records) != blocks * 4:
        errors.append(f"expected {blocks * 4} records, found {len(records)}")

    by_block: dict[int, list[dict]] = defaultdict(list)
    treatments: dict[str, list[dict]] = defaultdict(list)
    checksum = None
    layout = None
    for record in records:
        block = int(record["block"])
        by_block[block].append(record)
        result = record.get("result")
        if record["exit_code"] != 0 or not isinstance(result, dict):
            errors.append(f"block {block} slot {record['slot']} did not complete")
            continue
        if result.get("treatment") != record["treatment"]:
            errors.append(f"block {block} slot {record['slot']} treatment mismatch")
        value = result.get("checksum")
        checksum = value if checksum is None else checksum
        if value != checksum:
            errors.append(f"block {block} slot {record['slot']} checksum mismatch")
        current_layout = tuple(result.get(field) for field in LAYOUT_FIELDS)
        layout = current_layout if layout is None else layout
        if current_layout != layout:
            errors.append(f"block {block} slot {record['slot']} layout mismatch")
        treatments[record["treatment"]].append(result)

    block_ratios: list[float] = []
    strata: dict[str, list[float]] = defaultdict(list)
    for block in range(blocks):
        block_records = sorted(by_block.get(block, []), key=lambda row: row["slot"])
        order_name = "ABBA" if block % 2 == 0 else "BAAB"
        observed = tuple(row["treatment"] for row in block_records)
        if observed != EXPECTED_ORDERS[order_name]:
            errors.append(
                f"block {block}: expected {EXPECTED_ORDERS[order_name]}, found {observed}"
            )
            continue
        if any(not isinstance(row.get("result"), dict) for row in block_records):
            continue
        narrow = [
            float(row["result"]["ns_per_lookup"])
            for row in block_records
            if row["treatment"] == "narrow"
        ]
        covering = [
            float(row["result"]["ns_per_lookup"])
            for row in block_records
            if row["treatment"] == "covering"
        ]
        ratio = geometric_mean(narrow) / geometric_mean(covering)
        block_ratios.append(ratio)
        strata[order_name].append(ratio)

    for treatment in ("narrow", "covering"):
        if len(treatments[treatment]) != blocks * 2:
            errors.append(
                f"expected {blocks * 2} {treatment} results, "
                f"found {len(treatments[treatment])}"
            )
    if len(block_ratios) != blocks:
        errors.append(f"expected {blocks} complete block ratios, found {len(block_ratios)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    ordered = sorted(block_ratios)
    # With twelve blocks, the third and tenth order statistics give an exact
    # distribution-free 96.14% sign interval for the median.
    if len(ordered) >= 5:
        low = ordered[2]
        high = ordered[-3]
        coverage = 1.0 - 2.0 * sum(
            math.comb(len(ordered), index) for index in range(3)
        ) / (2 ** len(ordered))
    else:
        low, high = ordered[0], ordered[-1]
        coverage = 1.0 - 2.0 / (2 ** len(ordered))

    per_treatment = {}
    for treatment, results in treatments.items():
        per_treatment[treatment] = {
            "processes": len(results),
            "median_ns_per_lookup": statistics.median(
                float(row["ns_per_lookup"]) for row in results
            ),
            "median_setup_ms": statistics.median(
                int(row["setup_ns"]) / 1_000_000 for row in results
            ),
            "median_nonsteady_ms": statistics.median(
                int(row["nonsteady_ns"]) / 1_000_000 for row in results
            ),
        }

    contrast = {
        "geometric_mean_complete_block_ratio": geometric_mean(block_ratios),
        "median_complete_block_ratio": statistics.median(block_ratios),
        "minimum_complete_block_ratio": min(block_ratios),
        "maximum_complete_block_ratio": max(block_ratios),
        "abba_median": statistics.median(strata["ABBA"]),
        "baab_median": statistics.median(strata["BAAB"]),
        "sign_interval_nominal_coverage": coverage,
        "sign_interval_assumptions": (
            "independent exchangeable continuous block contrasts"
        ),
        "sign_interval_low": low,
        "sign_interval_high": high,
        "complete_block_ratios": block_ratios,
    }
    summary = {
        "protocol": metadata["protocol"],
        "seed": metadata["seed"],
        "blocks": blocks,
        "fresh_processes": len(records),
        "processes_per_treatment": blocks * 2,
        "checksum": checksum,
        "layout": dict(zip(LAYOUT_FIELDS, layout)),
        "treatments": per_treatment,
        "narrow_over_covering": contrast,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"validated {len(records)} fresh processes; "
        f"narrow/covering geometric block ratio="
        f"{contrast['geometric_mean_complete_block_ratio']:.6f}x; "
        f"median={contrast['median_complete_block_ratio']:.6f}x; "
        f"{100 * coverage:.2f}% nominal sign interval [{low:.6f}, {high:.6f}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
