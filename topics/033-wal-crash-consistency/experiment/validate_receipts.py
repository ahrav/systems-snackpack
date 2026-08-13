#!/usr/bin/env python3
"""Validate Topic 33 raw benchmark rows and recompute paired estimates."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys


BLOCKS = 8
RECORDS = 128
PAYLOAD_BYTES = 256
BATCH_A = 1
BATCH_B = 8
LOG_BYTES = RECORDS * (40 + PAYLOAD_BYTES)
T_CRITICAL_95_DF7 = 2.364624


def fail(message: str) -> None:
    """Raise one receipt-validation failure."""

    raise ValueError(message)


def integer(row: dict[str, str], key: str) -> int:
    """Parse one nonnegative integer field."""

    try:
        value = int(row[key])
    except (KeyError, ValueError) as error:
        fail(f"invalid {key}: {error}")
    if value < 0:
        fail(f"negative {key}: {value}")
    return value


def main() -> int:
    """Validate the CSV and write a machine-readable summary."""

    if len(sys.argv) != 3:
        print("usage: validate_receipts.py INPUT.csv SUMMARY.json", file=sys.stderr)
        return 2

    input_path = Path(sys.argv[1]).resolve(strict=True)
    summary_path = Path(sys.argv[2]).resolve()
    with input_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != BLOCKS * 4:
        fail(f"expected {BLOCKS * 4} rows, found {len(rows)}")

    pids: set[int] = set()
    block_log_ratios: list[float] = []
    templates: list[str] = []
    for block in range(1, BLOCKS + 1):
        current = [row for row in rows if integer(row, "block") == block]
        if len(current) != 4:
            fail(f"block {block} does not have four rows")
        current.sort(key=lambda row: integer(row, "period"))
        if [integer(row, "period") for row in current] != [1, 2, 3, 4]:
            fail(f"block {block} periods are not 1..4")
        template_set = {row["template"] for row in current}
        if len(template_set) != 1:
            fail(f"block {block} mixes templates")
        template = template_set.pop()
        expected_labels = list(template)
        if template not in {"ABBA", "BAAB"}:
            fail(f"block {block} has unknown template {template}")
        if [row["label"] for row in current] != expected_labels:
            fail(f"block {block} labels disagree with {template}")
        templates.append(template)

        logs: dict[str, list[float]] = {"A": [], "B": []}
        for row in current:
            label = row["label"]
            batch = integer(row, "batch")
            syncs = integer(row, "syncs")
            expected_batch = BATCH_A if label == "A" else BATCH_B
            expected_syncs = math.ceil(RECORDS / expected_batch)
            if batch != expected_batch or syncs != expected_syncs:
                fail(f"block {block} {label} has wrong batch or sync count")
            if integer(row, "records") != RECORDS:
                fail(f"block {block} has wrong record count")
            if integer(row, "payload_bytes") != PAYLOAD_BYTES:
                fail(f"block {block} has wrong payload size")
            if integer(row, "log_bytes") != LOG_BYTES:
                fail(f"block {block} has wrong log size")
            pid = integer(row, "pid")
            if pid == 0 or pid in pids:
                fail(f"invalid or reused child pid {pid}")
            pids.add(pid)
            io_ns = integer(row, "io_ns")
            process_ns = integer(row, "process_ns")
            outside_ns = integer(row, "outside_timed_ns")
            recovery_ns = integer(row, "recovery_ns")
            if io_ns == 0 or process_ns < io_ns or recovery_ns == 0:
                fail(f"block {block} has invalid duration")
            if process_ns - io_ns != outside_ns:
                fail(f"block {block} outside duration does not reconcile")
            logs[label].append(math.log(io_ns))
        block_log_ratios.append(
            sum(logs["B"]) / len(logs["B"])
            - sum(logs["A"]) / len(logs["A"])
        )

    if templates.count("ABBA") != BLOCKS // 2 or templates.count("BAAB") != BLOCKS // 2:
        fail("templates are not balanced")

    mean = sum(block_log_ratios) / BLOCKS
    sample_sd = math.sqrt(
        sum((value - mean) ** 2 for value in block_log_ratios) / (BLOCKS - 1)
    )
    half_width = T_CRITICAL_95_DF7 * sample_sd / math.sqrt(BLOCKS)
    summary = {
        "block_log_ratio_sd": sample_sd,
        "blocks": BLOCKS,
        "fresh_process_rows": len(rows),
        "geomean_ratio_b_over_a": math.exp(mean),
        "paired_t_95_high": math.exp(mean + half_width),
        "paired_t_95_low": math.exp(mean - half_width),
        "status": "pass",
        "templates_abba": templates.count("ABBA"),
        "templates_baab": templates.count("BAAB"),
        "variation_boundary": "eight_complete_within_window_block_contrasts",
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "VALIDATION,status=pass,rows=32,blocks=8,"
        f"geomean_ratio_b_over_a={summary['geomean_ratio_b_over_a']:.6f},"
        f"block_log_ratio_sd={sample_sd:.6f},"
        f"paired_t_95=[{summary['paired_t_95_low']:.6f},"
        f"{summary['paired_t_95_high']:.6f}]"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
