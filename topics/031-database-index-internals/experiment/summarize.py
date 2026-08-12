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
RESULT_INT_FIELDS = (
    "entries",
    "queries",
    "reps",
    "lookups",
    "setup_ns",
    "nonsteady_ns",
    "steady_ns",
    "checksum",
) + LAYOUT_FIELDS
# `Corpus::layout` reports `size_of` values for the three Rust entry types, and
# `src/lib.rs` asserts the same three sizes.
EXPECTED_ENTRY_BYTES = {
    "rust_narrow_entry": 16,
    "rust_payload": 16,
    "rust_covering_entry": 24,
}
LOGICAL_ENTRY_SOURCE = {
    "logical_narrow_index": "rust_narrow_entry",
    "logical_heap": "rust_payload",
    "logical_covering_index": "rust_covering_entry",
}


def geometric_mean(values: list[float]) -> float:
    """Return the geometric mean of positive values."""

    return math.exp(statistics.fmean(math.log(value) for value in values))


def result_error(record: dict, metadata: dict) -> str | None:
    """Return why a record's result violates the probe contract, or None."""

    result = record.get("result")
    if record.get("exit_code") != 0 or not isinstance(result, dict):
        return "did not complete"
    if result.get("treatment") != record["treatment"]:
        return "treatment mismatch"
    for field in RESULT_INT_FIELDS:
        value = result.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            return f"missing or non-integer {field}"
    ns_per_lookup = result.get("ns_per_lookup")
    if (
        not isinstance(ns_per_lookup, float)
        or not math.isfinite(ns_per_lookup)
        or ns_per_lookup <= 0
    ):
        return "missing or non-finite ns_per_lookup"
    lookups = result["lookups"]
    if lookups <= 0 or lookups != result["queries"] * result["reps"]:
        return "lookups does not equal queries times reps"
    if not math.isclose(
        ns_per_lookup, result["steady_ns"] / lookups, rel_tol=1e-9, abs_tol=1e-6
    ):
        return "ns_per_lookup contradicts steady_ns divided by lookups"
    for field, expected in EXPECTED_ENTRY_BYTES.items():
        if result[field] != expected:
            return f"{field} is {result[field]}, expected {expected}"
    for logical, entry in LOGICAL_ENTRY_SOURCE.items():
        if result[logical] != result["entries"] * result[entry]:
            return f"{logical} does not equal entries times {entry}"
    for name in ("entries", "queries", "reps"):
        if result[name] != metadata.get(name):
            return f"{name} does not match run metadata"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        metadata = json.loads(
            (args.output / "metadata.json").read_text(encoding="utf-8")
        )
        check = json.loads((args.output / "check.json").read_text(encoding="utf-8"))
        records = [
            json.loads(line)
            for line in (args.output / "runs.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: cannot load run evidence: {error}")
        return 1
    if not isinstance(metadata, dict) or not isinstance(check, dict):
        print("ERROR: metadata.json and check.json must hold JSON objects")
        return 1
    blocks = metadata.get("blocks")
    if not isinstance(blocks, int) or isinstance(blocks, bool) or blocks <= 0:
        print("ERROR: metadata blocks must be a positive integer")
        return 1
    errors: list[str] = []
    if check.get("exit_code") != 0 or "CHECK_OK" not in check.get("stdout", ""):
        errors.append("fresh-process correctness check failed")
    if len(records) != blocks * 4:
        errors.append(f"expected {blocks * 4} records, found {len(records)}")

    by_block: dict[int, list[dict]] = defaultdict(list)
    treatments: dict[str, list[dict]] = defaultdict(list)
    seen_slots: set[tuple[int, int]] = set()
    checksum = None
    layout = None
    for index, record in enumerate(records):
        block = record.get("block")
        slot = record.get("slot")
        if (
            not isinstance(block, int)
            or isinstance(block, bool)
            or not isinstance(slot, int)
            or isinstance(slot, bool)
            or record.get("treatment") not in ("narrow", "covering")
        ):
            errors.append(f"record {index}: malformed run record")
            continue
        if not 0 <= block < blocks or not 0 <= slot < 4:
            errors.append(f"record {index}: block {block} slot {slot} out of range")
            continue
        if (block, slot) in seen_slots:
            errors.append(f"record {index}: duplicate block {block} slot {slot}")
            continue
        seen_slots.add((block, slot))
        by_block[block].append(record)
        problem = result_error(record, metadata)
        if problem is not None:
            errors.append(f"block {block} slot {slot} {problem}")
            continue
        record["result_valid"] = True
        result = record["result"]
        value = result["checksum"]
        checksum = value if checksum is None else checksum
        if value != checksum:
            errors.append(f"block {block} slot {slot} checksum mismatch")
        current_layout = tuple(result[field] for field in LAYOUT_FIELDS)
        layout = current_layout if layout is None else layout
        if current_layout != layout:
            errors.append(f"block {block} slot {slot} layout mismatch")
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
        if any(not row.get("result_valid") for row in block_records):
            continue
        narrow = [
            row["result"]["ns_per_lookup"]
            for row in block_records
            if row["treatment"] == "narrow"
        ]
        covering = [
            row["result"]["ns_per_lookup"]
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
    if checksum is None or layout is None:
        errors.append("no valid probe results retained")
    if errors or checksum is None or layout is None:
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
                row["ns_per_lookup"] for row in results
            ),
            "median_setup_ms": statistics.median(
                row["setup_ns"] / 1_000_000 for row in results
            ),
            "median_nonsteady_ms": statistics.median(
                row["nonsteady_ns"] / 1_000_000 for row in results
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
        "layout": {field: layout[i] for i, field in enumerate(LAYOUT_FIELDS)},
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
