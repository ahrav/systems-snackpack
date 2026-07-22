#!/usr/bin/env python3
"""Validate Topic 12 process rows and summarize process-level variation."""

from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

MODES = ("anon-first", "anon-refault", "file-warm", "file-cold")
SCHEDULE = (
    ("anon-first", "anon-refault", "file-warm", "file-cold"),
    ("anon-refault", "file-warm", "file-cold", "anon-first"),
    ("file-warm", "file-cold", "anon-first", "anon-refault"),
    ("file-cold", "anon-first", "anon-refault", "file-warm"),
    ("file-cold", "file-warm", "anon-refault", "anon-first"),
    ("anon-first", "file-cold", "file-warm", "anon-refault"),
    ("anon-refault", "anon-first", "file-cold", "file-warm"),
    ("file-warm", "anon-refault", "anon-first", "file-cold"),
)
FIELDS = (
    "run_id",
    "mode",
    "mib",
    "page_size",
    "pages",
    "setup_ns",
    "touch_ns",
    "minflt",
    "majflt",
    "resident_before",
    "resident_after",
    "checksum",
    "fadvise_rc",
    "cold_verified",
    "external_wall_ns",
)
INTEGER_FIELDS = FIELDS[2:]


def fail(message: str) -> None:
    raise SystemExit(message)


def parse(path: Path) -> list[dict[str, int | str]]:
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != FIELDS:
            fail("raw CSV header differs from the recorded schema")
        rows: list[dict[str, int | str]] = []
        for line_number, raw in enumerate(reader, start=2):
            if None in raw or any(raw.get(field) is None for field in FIELDS):
                fail(f"line {line_number}: row does not contain exactly {len(FIELDS)} fields")
            row: dict[str, int | str] = {
                "run_id": raw["run_id"],
                "mode": raw["mode"],
            }
            for field in INTEGER_FIELDS:
                try:
                    value = int(raw[field])
                except (TypeError, ValueError) as error:
                    fail(f"line {line_number}: {field} is not an integer: {error}")
                if value < 0:
                    fail(f"line {line_number}: {field} is negative")
                row[field] = value
            rows.append(row)
    return rows


def integer(row: dict[str, int | str], field: str) -> int:
    value = row[field]
    if not isinstance(value, int):
        fail(f"internal schema error: {field} is not an integer")
    return value


def validate(rows: list[dict[str, int | str]]) -> dict[int, dict[str, dict[str, int | str]]]:
    if len(rows) != 32:
        fail(f"expected 32 process rows, observed {len(rows)}")
    blocks: dict[int, dict[str, dict[str, int | str]]] = defaultdict(dict)
    page_sizes: set[int] = set()
    page_counts: set[int] = set()
    run_ids: set[str] = set()

    for index, row in enumerate(rows):
        block = index // 4 + 1
        position = index % 4 + 1
        expected_id = f"b{block:02d}-p{position}"
        expected_mode = SCHEDULE[block - 1][position - 1]
        if row["run_id"] != expected_id or row["mode"] != expected_mode:
            fail(
                f"row {index + 2}: expected {expected_id},{expected_mode}; "
                f"observed {row['run_id']},{row['mode']}"
            )
        if expected_id in run_ids:
            fail(f"duplicate run ID: {expected_id}")
        run_ids.add(expected_id)
        page_size = integer(row, "page_size")
        pages = integer(row, "pages")
        mib = integer(row, "mib")
        if mib != 32:
            fail(f"{expected_id}: recorded mapping size must be 32 MiB")
        if page_size == 0 or pages == 0:
            fail(f"{expected_id}: page size and page count must be nonzero")
        if pages * page_size != mib * 1024 * 1024:
            fail(f"{expected_id}: bytes differ from pages times page size")
        if (
            integer(row, "setup_ns") == 0
            or integer(row, "touch_ns") == 0
            or integer(row, "external_wall_ns") == 0
        ):
            fail(f"{expected_id}: timing fields must be nonzero")
        if integer(row, "external_wall_ns") < integer(row, "setup_ns") + integer(
            row, "touch_ns"
        ):
            fail(f"{expected_id}: external wall time does not cover setup and touch")
        page_sizes.add(page_size)
        page_counts.add(pages)

        mode = str(row["mode"])
        if integer(row, "resident_after") != pages:
            fail(f"{expected_id}: mapping was not fully resident after touch")
        if mode == "file-cold":
            if integer(row, "resident_before") != 0:
                fail(f"{expected_id}: cold mapping had resident pages before touch")
            if integer(row, "majflt") == 0:
                fail(f"{expected_id}: cold mapping reported no major fault")
            if integer(row, "cold_verified") != 1 or integer(row, "fadvise_rc") != 0:
                fail(f"{expected_id}: cold-state controls failed")
        elif mode == "file-warm":
            if integer(row, "resident_before") != pages:
                fail(f"{expected_id}: warm mapping was not resident before touch")
            if integer(row, "majflt") != 0:
                fail(f"{expected_id}: warm mapping reported a major fault")
            if integer(row, "cold_verified") != 0 or integer(row, "fadvise_rc") != 0:
                fail(f"{expected_id}: warm mode has invalid cold-control fields")
        else:
            if integer(row, "resident_before") != 0:
                fail(f"{expected_id}: anonymous mapping had resident pages before touch")
            if integer(row, "majflt") != 0:
                fail(f"{expected_id}: anonymous mode reported a major fault")
            if integer(row, "cold_verified") != 0 or integer(row, "fadvise_rc") != 0:
                fail(f"{expected_id}: anonymous mode has invalid file-control fields")
            if mode == "anon-refault" and integer(row, "checksum") != 0:
                fail(f"{expected_id}: discarded anonymous pages did not read as zero")
        blocks[block][mode] = row

    if len(page_sizes) != 1 or len(page_counts) != 1:
        fail("page size or page count changed between processes")
    if any(set(block_rows) != set(MODES) for block_rows in blocks.values()):
        fail("one or more blocks do not contain all four modes")
    anon_first_checksums = {
        integer(blocks[block]["anon-first"], "checksum") for block in blocks
    }
    file_checksums = {
        integer(blocks[block][mode], "checksum")
        for block in blocks
        for mode in ("file-warm", "file-cold")
    }
    if len(anon_first_checksums) != 1 or anon_first_checksums == {0}:
        fail("anonymous first-write checksums differ or are zero")
    if len(file_checksums) != 1 or file_checksums == {0}:
        fail("file checksums differ or are zero")
    for mode in MODES:
        for position in range(4):
            if sum(order[position] == mode for order in SCHEDULE) != 2:
                fail("schedule does not balance each mode across positions")
    return blocks


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def describe(name: str, values: list[float], unit: str) -> str:
    return (
        f"{name}_median={statistics.median(values):.9f}{unit} "
        f"{name}_mean={statistics.fmean(values):.9f}{unit} "
        f"{name}_sample_sd={statistics.stdev(values):.9f}{unit} "
        f"{name}_mad={median_absolute_deviation(values):.9f}{unit} "
        f"{name}_range=[{min(values):.9f},{max(values):.9f}]{unit}"
    )


def summarize(path: Path) -> None:
    rows = parse(path)
    blocks = validate(rows)
    print("replication_unit=fresh-process processes_per_mode=8 blocks=8")
    print(f"page_size={integer(rows[0], 'page_size')} pages={integer(rows[0], 'pages')}")
    for mode in MODES:
        mode_rows = [blocks[block][mode] for block in sorted(blocks)]
        touch_ms = [integer(row, "touch_ns") / 1_000_000 for row in mode_rows]
        setup_ms = [integer(row, "setup_ns") / 1_000_000 for row in mode_rows]
        wall_ms = [integer(row, "external_wall_ns") / 1_000_000 for row in mode_rows]
        minflt = [integer(row, "minflt") for row in mode_rows]
        majflt = [integer(row, "majflt") for row in mode_rows]
        print(f"MODE {mode}")
        print(describe("touch", touch_ms, "ms"))
        print(describe("setup", setup_ms, "ms"))
        print(describe("external_wall", wall_ms, "ms"))
        print(f"minflt_range=[{min(minflt)},{max(minflt)}] majflt_range=[{min(majflt)},{max(majflt)}]")

    for numerator, denominator, label in (
        ("anon-first", "anon-refault", "anon_first_over_refault_read"),
        ("file-cold", "file-warm", "cold_over_warm_file"),
    ):
        ratios = [
            integer(blocks[block][numerator], "touch_ns")
            / integer(blocks[block][denominator], "touch_ns")
            for block in sorted(blocks)
        ]
        geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
        print(
            f"PAIRED {label} geometric_mean={geometric_mean:.9f}x "
            f"median={statistics.median(ratios):.9f}x "
            f"sample_sd={statistics.stdev(ratios):.9f}x "
            f"range=[{min(ratios):.9f},{max(ratios):.9f}]x"
        )


def main() -> None:
    if len(sys.argv) != 2:
        fail(f"usage: {Path(sys.argv[0]).name} RAW_CSV")
    path = Path(sys.argv[1])
    if not path.is_file():
        fail(f"raw CSV does not exist: {path}")
    summarize(path)


if __name__ == "__main__":
    main()
