#!/usr/bin/env python3
"""Validate and summarize paired Topic 14 process measurements."""

from __future__ import annotations

import csv
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Optional

from run_schedule import (
    CHUNK_BYTES,
    COMPARISONS,
    HEADER,
    INPUT_BYTES,
    PAIRS,
    PASSES,
    schedule,
)


def fail(message: str) -> None:
    raise SystemExit(message)


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError):
        fail(f"{row.get('run_id', '<unknown>')}: {field} is not an integer")


def parse(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if tuple(reader.fieldnames or ()) != HEADER:
            fail("raw TSV header differs from the recorded schema")
        rows = list(reader)
    if len(rows) != len(COMPARISONS) * PAIRS * 2:
        fail(f"expected {len(COMPARISONS) * PAIRS * 2} process rows, observed {len(rows)}")
    if any(None in row for row in rows):
        fail("one or more rows contain fields beyond the recorded schema")
    if any(value is None for row in rows for value in row.values()):
        fail("one or more rows omit a field from the recorded schema")
    return rows


def validate(
    rows: list[dict[str, str]], source_commit: str
) -> dict[str, dict[int, dict[str, dict[str, str]]]]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail("SOURCE_COMMIT must be a 40-character lowercase SHA-1")
    expected_records = schedule()
    observations: dict[str, dict[int, dict[str, dict[str, str]]]] = {
        comparison: {pair: {} for pair in range(1, PAIRS + 1)}
        for comparison, _, _ in COMPARISONS
    }
    fixture: Optional[tuple[int, int]] = None

    for row, (comparison, pair, position, order, mode) in zip(rows, expected_records):
        run_id = f"{comparison.replace('-vs-', '_')}-p{pair:02}-{position}"
        expected_text = {
            "run_id": run_id,
            "comparison": comparison,
            "pair": str(pair),
            "position": str(position),
            "order": order,
            "mode": mode,
            "source_commit": source_commit,
        }
        for field, expected in expected_text.items():
            if row[field] != expected:
                fail(f"{run_id}: {field}={row[field]!r}, expected {expected!r}")
        if mode == "scalar_whole":
            if row["variant"] != "scalar":
                fail(f"{run_id}: scalar mode reported {row['variant']!r}")
        elif row["variant"] not in {"avx2", "neon"}:
            fail(f"{run_id}: selected mode reported {row['variant']!r}")
        expected_config = {
            "input_bytes": INPUT_BYTES,
            "passes": PASSES,
            "chunk_bytes": CHUNK_BYTES,
        }
        for field, expected in expected_config.items():
            if integer(row, field) != expected:
                fail(f"{run_id}: {field} differs from the recorded configuration")
        current_fixture = (
            integer(row, "input_checksum"),
            integer(row, "expected_per_pass"),
        )
        if fixture is None:
            fixture = current_fixture
        elif current_fixture != fixture:
            fail(f"{run_id}: deterministic fixture checksums changed between processes")
        checksum = integer(row, "checksum")
        if checksum != integer(row, "expected_checksum"):
            fail(f"{run_id}: checksum differs from expected_checksum")
        if checksum != current_fixture[1] * PASSES:
            fail(f"{run_id}: checksum differs from scalar oracle times passes")
        setup_ns = integer(row, "setup_ns")
        steady_ns = integer(row, "steady_ns")
        verify_ns = integer(row, "verify_ns")
        external_ns = integer(row, "external_wall_ns")
        if min(setup_ns, steady_ns, external_ns) <= 0 or verify_ns < 0:
            fail(f"{run_id}: timing fields are outside their valid range")
        if external_ns < setup_ns + steady_ns + verify_ns:
            fail(f"{run_id}: external wall time does not cover internal phases")
        observations[comparison][pair][mode] = row

    for comparison, mode_a, mode_b in COMPARISONS:
        for pair in range(1, PAIRS + 1):
            if set(observations[comparison][pair]) != {mode_a, mode_b}:
                fail(f"{comparison} pair {pair}: paired modes are incomplete")
    return observations


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
    observations = validate(parse(path), source_commit)
    print(
        "measurement_boundary=steady-kernel-invocations "
        "replication_unit=fresh-pinned-process pairing_unit=ab-ba-process-pair "
        f"pairs_per_comparison={PAIRS}"
    )
    print(
        "dispersion_boundary=paired-process-ratios "
        "quartiles=statistics.quantiles-inclusive interval=descriptive-IQR"
    )
    print(
        f"configuration input_bytes={INPUT_BYTES} passes={PASSES} "
        f"chunk_bytes={CHUNK_BYTES} source_commit={source_commit}"
    )

    for comparison, mode_a, mode_b in COMPARISONS:
        print(f"COMPARISON {comparison}")
        for mode in (mode_a, mode_b):
            rows = [
                observations[comparison][pair][mode]
                for pair in range(1, PAIRS + 1)
            ]
            steady_ms = [integer(row, "steady_ns") / 1_000_000 for row in rows]
            setup_ms = [integer(row, "setup_ns") / 1_000_000 for row in rows]
            verify_ms = [integer(row, "verify_ns") / 1_000_000 for row in rows]
            throughput_gib_s = [
                (INPUT_BYTES * PASSES)
                / integer(row, "steady_ns")
                * (1_000_000_000 / (1024**3))
                for row in rows
            ]
            external_ms = [
                integer(row, "external_wall_ns") / 1_000_000 for row in rows
            ]
            residual_ms = [
                (
                    integer(row, "external_wall_ns")
                    - integer(row, "setup_ns")
                    - integer(row, "steady_ns")
                    - integer(row, "verify_ns")
                )
                / 1_000_000
                for row in rows
            ]
            print(f"MODE {mode}")
            print("steady_ms " + distribution(steady_ms, "ms"))
            print("throughput_gib_s " + distribution(throughput_gib_s, "GiB/s"))
            print("setup_ms " + distribution(setup_ms, "ms"))
            print("verify_ms " + distribution(verify_ms, "ms"))
            print("external_wall_ms " + distribution(external_ms, "ms"))
            print(
                "process_wrapper_residual_ms "
                + distribution(residual_ms, "ms")
            )

        ratios = [
            integer(observations[comparison][pair][mode_a], "steady_ns")
            / integer(observations[comparison][pair][mode_b], "steady_ns")
            for pair in range(1, PAIRS + 1)
        ]
        geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
        print(
            f"PAIRED {mode_a}_over_{mode_b} geometric_mean={geometric_mean:.6f}x "
            + distribution(ratios, "x")
        )


def main() -> None:
    if len(sys.argv) != 3:
        fail(f"usage: {Path(sys.argv[0]).name} RAW_TSV SOURCE_COMMIT")
    path = Path(sys.argv[1])
    if not path.is_file():
        fail(f"raw TSV does not exist: {path}")
    summarize(path, sys.argv[2])


if __name__ == "__main__":
    main()
