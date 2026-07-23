#!/usr/bin/env python3
"""Validate and summarize the balanced Topic 13 process measurements."""

from __future__ import annotations

import csv
import math
import re
import statistics
import sys
from pathlib import Path


MODES = (
    "pow2-naive",
    "pow2-tiled",
    "pow2-recursive",
    "padded-naive",
    "padded-tiled",
    "padded-recursive",
)
SCHEDULE = tuple(
    tuple(MODES[(offset + position) % len(MODES)] for position in range(len(MODES)))
    for offset in range(len(MODES))
) + tuple(
    tuple(tuple(reversed(MODES))[(offset + position) % len(MODES)] for position in range(len(MODES)))
    for offset in range(len(MODES))
)
HEADER = (
    "run_id",
    "block",
    "position",
    "mode",
    "variant",
    "n",
    "leading_dimension",
    "tile_edge",
    "recursive_leaf_elements",
    "condition_bytes",
    "source_commit",
    "source_virtual_base",
    "destination_virtual_base",
    "source_mod64",
    "destination_mod64",
    "source_page_offset",
    "destination_page_offset",
    "setup_ns",
    "kernel_ns",
    "verify_ns",
    "checksum",
    "expected_checksum",
    "external_wall_ns",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError):
        fail(f"{row.get('run_id', '<unknown>')}: {field} is not an integer")


def expected_checksum(n: int) -> int:
    axis_sum = n * (n - 1) // 2
    return n * n * 7 + (131 + 17) * n * axis_sum


def print_schedule() -> None:
    for block in SCHEDULE:
        print("SCHEDULE " + " ".join(block))


def parse(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if tuple(reader.fieldnames or ()) != HEADER:
            fail("raw TSV header differs from the recorded schema")
        rows = list(reader)
    if len(rows) != len(SCHEDULE) * len(MODES):
        fail(f"expected 72 process rows, observed {len(rows)}")
    if any(None in row for row in rows):
        fail("one or more rows contain fields beyond the recorded schema")
    if any(value is None for row in rows for value in row.values()):
        fail("one or more rows omit a field from the recorded schema")
    return rows


def validate(
    rows: list[dict[str, str]], source_commit: str
) -> dict[int, dict[str, dict[str, str]]]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail("SOURCE_COMMIT must be a 40-character lowercase SHA-1")
    blocks: dict[int, dict[str, dict[str, str]]] = {
        block: {} for block in range(1, len(SCHEDULE) + 1)
    }
    run_ids: set[str] = set()
    independent_checksum = expected_checksum(2_048)

    for index, row in enumerate(rows):
        expected_block = index // len(MODES) + 1
        expected_position = index % len(MODES) + 1
        expected_mode = SCHEDULE[expected_block - 1][expected_position - 1]
        expected_run_id = f"b{expected_block:02}-p{expected_position}"
        if row["run_id"] != expected_run_id:
            fail(
                f"row {index + 2}: expected run ID {expected_run_id}, "
                f"observed {row['run_id']!r}"
            )
        if expected_run_id in run_ids:
            fail(f"duplicate run ID: {expected_run_id}")
        run_ids.add(expected_run_id)
        if integer(row, "block") != expected_block:
            fail(f"{expected_run_id}: recorded block differs from row order")
        if integer(row, "position") != expected_position:
            fail(f"{expected_run_id}: recorded position differs from row order")
        if row["mode"] != expected_mode:
            fail(
                f"{expected_run_id}: expected mode {expected_mode!r}, "
                f"observed {row['mode']!r}"
            )
        expected_variant = expected_mode.split("-", 1)[1]
        if row["variant"] != expected_variant:
            fail(f"{expected_run_id}: variant differs from mode suffix")
        expected_ld = 2_048 if expected_mode.startswith("pow2-") else 2_049
        expected_config = {
            "n": 2_048,
            "leading_dimension": expected_ld,
            "tile_edge": 32,
            "recursive_leaf_elements": 1_024,
            "condition_bytes": 128 * 1024 * 1024,
            "checksum": independent_checksum,
            "expected_checksum": independent_checksum,
        }
        for field, expected in expected_config.items():
            observed = integer(row, field)
            if observed != expected:
                fail(f"{expected_run_id}: {field}={observed}, expected {expected}")
        if row["source_commit"] != source_commit:
            fail(f"{expected_run_id}: source commit differs from the verified archive")
        source_base = integer(row, "source_virtual_base")
        destination_base = integer(row, "destination_virtual_base")
        if source_base <= 0 or destination_base <= 0 or source_base == destination_base:
            fail(f"{expected_run_id}: virtual bases must be distinct positive addresses")
        storage_bytes = 2_048 * expected_ld * 8
        if (
            source_base < destination_base + storage_bytes
            and destination_base < source_base + storage_bytes
        ):
            fail(f"{expected_run_id}: source and destination virtual ranges overlap")
        expected_placement = {
            "source_mod64": source_base % 64,
            "destination_mod64": destination_base % 64,
            "source_page_offset": source_base % 4_096,
            "destination_page_offset": destination_base % 4_096,
        }
        for field, expected in expected_placement.items():
            observed = integer(row, field)
            if observed != expected:
                fail(f"{expected_run_id}: {field} disagrees with the virtual base")
        setup_ns = integer(row, "setup_ns")
        kernel_ns = integer(row, "kernel_ns")
        verify_ns = integer(row, "verify_ns")
        external_wall_ns = integer(row, "external_wall_ns")
        if min(setup_ns, kernel_ns, verify_ns, external_wall_ns) <= 0:
            fail(f"{expected_run_id}: timing fields must be positive")
        if external_wall_ns < setup_ns + kernel_ns + verify_ns:
            fail(f"{expected_run_id}: external wall time does not cover internal phases")
        if expected_mode in blocks[expected_block]:
            fail(f"block {expected_block} contains mode {expected_mode!r} twice")
        blocks[expected_block][expected_mode] = row

    expected_modes = set(MODES)
    if any(set(block) != expected_modes for block in blocks.values()):
        fail("one or more blocks do not contain all six modes")
    for mode in MODES:
        for position in range(len(MODES)):
            count = sum(order[position] == mode for order in SCHEDULE)
            if count != 2:
                fail(f"schedule does not place {mode!r} twice at position {position + 1}")
    return blocks


def distribution(values: list[float], unit: str) -> str:
    if len(values) < 2:
        fail("dispersion requires at least two process observations")
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return (
        f"n={len(values)} median={statistics.median(values):.6f}{unit} "
        f"q1={q1:.6f}{unit} q3={q3:.6f}{unit} iqr={q3 - q1:.6f}{unit} "
        f"sample_sd={statistics.stdev(values):.6f}{unit} "
        f"range=[{min(values):.6f},{max(values):.6f}]{unit}"
    )


def summarize(path: Path, source_commit: str) -> None:
    rows = parse(path)
    blocks = validate(rows, source_commit)
    print(
        "measurement_boundary=timed-dispatch-and-kernel "
        "replication_unit=fresh-pinned-process "
        "pairing_unit=six-mode-block blocks=12 processes_per_mode=12"
    )
    print(
        "dispersion_boundary=observed_process_runs "
        "quartiles=statistics.quantiles-inclusive interval=descriptive-IQR"
    )
    print(f"source_commit={source_commit}")
    for mode in MODES:
        mode_rows = [blocks[block][mode] for block in sorted(blocks)]
        kernel_ms = [integer(row, "kernel_ns") / 1_000_000 for row in mode_rows]
        setup_ms = [integer(row, "setup_ns") / 1_000_000 for row in mode_rows]
        verify_ms = [integer(row, "verify_ns") / 1_000_000 for row in mode_rows]
        wall_ms = [integer(row, "external_wall_ns") / 1_000_000 for row in mode_rows]
        print(f"MODE {mode}")
        print("kernel_ms " + distribution(kernel_ms, "ms"))
        print("setup_ms " + distribution(setup_ms, "ms"))
        print("verify_ms " + distribution(verify_ms, "ms"))
        print("external_wall_ms " + distribution(wall_ms, "ms"))
        source_bases = {integer(row, "source_virtual_base") for row in mode_rows}
        destination_bases = {
            integer(row, "destination_virtual_base") for row in mode_rows
        }
        source_mod64 = sorted({integer(row, "source_mod64") for row in mode_rows})
        destination_mod64 = sorted(
            {integer(row, "destination_mod64") for row in mode_rows}
        )
        source_page_offsets = sorted(
            {integer(row, "source_page_offset") for row in mode_rows}
        )
        destination_page_offsets = sorted(
            {integer(row, "destination_page_offset") for row in mode_rows}
        )
        print(
            "virtual_placement "
            f"unique_source_bases={len(source_bases)} "
            f"unique_destination_bases={len(destination_bases)} "
            f"source_mod64={source_mod64} destination_mod64={destination_mod64} "
            f"source_page_offsets={source_page_offsets} "
            f"destination_page_offsets={destination_page_offsets}"
        )

    pairs = (
        ("pow2-naive", "pow2-tiled", "pow2_naive_over_tiled"),
        ("pow2-naive", "pow2-recursive", "pow2_naive_over_recursive"),
        ("padded-naive", "padded-tiled", "padded_naive_over_tiled"),
        ("padded-naive", "padded-recursive", "padded_naive_over_recursive"),
        ("pow2-naive", "padded-naive", "naive_pow2_over_padded"),
        ("pow2-tiled", "padded-tiled", "tiled_pow2_over_padded"),
        ("pow2-recursive", "padded-recursive", "recursive_pow2_over_padded"),
    )
    for numerator, denominator, label in pairs:
        ratios = [
            integer(blocks[block][numerator], "kernel_ns")
            / integer(blocks[block][denominator], "kernel_ns")
            for block in sorted(blocks)
        ]
        geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
        print(
            f"PAIRED {label} geometric_mean={geometric_mean:.6f}x "
            + distribution(ratios, "x")
        )


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-schedule":
        print_schedule()
        return
    if len(sys.argv) != 3:
        fail(f"usage: {Path(sys.argv[0]).name} RAW_TSV SOURCE_COMMIT")
    path = Path(sys.argv[1])
    if not path.is_file():
        fail(f"raw TSV does not exist: {path}")
    summarize(path, sys.argv[2])


if __name__ == "__main__":
    main()
