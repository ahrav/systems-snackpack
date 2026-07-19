#!/usr/bin/env python3
"""Validate and summarize Topic 9 process-level pairs."""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path


def parse_record(line: str) -> dict[str, str]:
    record: dict[str, str] = {}
    for field in line.split()[1:]:
        key, separator, value = field.partition("=")
        if not separator or not key or not value:
            raise SystemExit(f"malformed field {field!r} in record: {line}")
        if key in record:
            raise SystemExit(f"duplicate field {key!r} in record: {line}")
        record[key] = value
    return record


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def describe(label: str, values: list[float]) -> None:
    print(
        f"{label}: n={len(values)} mean={statistics.fmean(values):.9f} "
        f"sd={statistics.stdev(values):.9f} "
        f"median={statistics.median(values):.9f} "
        f"mad={median_absolute_deviation(values):.9f} "
        f"min={min(values):.9f} max={max(values):.9f}"
    )


def describe_ratios(label: str, ratios: list[float]) -> None:
    if len(ratios) != 12:
        raise ValueError(f"ratio interval requires 12 pairs, got {len(ratios)}")
    ordered = sorted(ratios)
    geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
    print(
        f"{label}: pairs={len(ratios)} geomean={geometric_mean:.9f} "
        f"median={statistics.median(ratios):.9f} "
        f"mad={median_absolute_deviation(ratios):.9f} "
        f"exact96.1%=[{ordered[2]:.9f},{ordered[9]:.9f}]"
    )


def positive_integer(record: dict[str, str], field: str) -> int:
    try:
        value = int(record[field])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid integer field {field!r}: {record}") from error
    if value <= 0:
        raise SystemExit(f"nonpositive {field!r}: {record}")
    return value


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: summarize.py processes.txt")

    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    session: dict[str, str] | None = None
    current_pair: dict[str, str] | None = None
    records: list[dict[str, str]] = []
    ended = False

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("SESSION_START "):
            if session is not None:
                raise SystemExit(f"line {line_number}: duplicate SESSION_START")
            session = parse_record(line)
        elif line.startswith("PAIR_START "):
            if session is None or current_pair is not None or ended:
                raise SystemExit(f"line {line_number}: unexpected PAIR_START")
            current_pair = parse_record(line)
            pair = len(records) + 1
            if current_pair.get("pair") != str(pair):
                raise SystemExit(f"line {line_number}: expected pair {pair}")
            expected_order = "compact-prefix" if pair % 2 else "prefix-compact"
            if current_pair.get("order") != expected_order:
                raise SystemExit(f"pair {pair}: expected order {expected_order}")
        elif line.startswith("RESULT "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: RESULT outside a pair")
            record = parse_record(line)
            if record.get("pair") != current_pair.get("pair"):
                raise SystemExit(f"line {line_number}: RESULT pair mismatch")
            if record.get("order") != current_pair.get("order"):
                raise SystemExit(f"line {line_number}: RESULT order mismatch")
            records.append(record)
        elif line.startswith("PAIR_END "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: PAIR_END outside a pair")
            end = parse_record(line)
            if end.get("pair") != current_pair.get("pair") or len(records) != int(end["pair"]):
                raise SystemExit(f"line {line_number}: incomplete or mismatched pair")
            current_pair = None
        elif line.startswith("SESSION_END "):
            if session is None or current_pair is not None or ended:
                raise SystemExit(f"line {line_number}: unexpected SESSION_END")
            ended = True
        elif current_pair is not None:
            raise SystemExit(f"line {line_number}: unexpected line inside pair")

    if session is None or not ended:
        raise SystemExit("expected one complete session")
    if len(records) != 12:
        raise SystemExit(f"expected 12 paired process records, found {len(records)}")
    if len({record.get("pid") for record in records}) != 12:
        raise SystemExit("expected one distinct process ID per pair")

    expected_bits = 1 << positive_integer(session, "bit_power")
    expected_queries = positive_integer(session, "queries")
    expected_compact_bytes = expected_bits // 8 + expected_bits // 128 + expected_bits // 32
    expected_prefix_bytes = (expected_bits + 1) * 4
    session_cpu = positive_integer(session, "cpu") if session.get("cpu") != "0" else 0

    compact: list[float] = []
    prefix: list[float] = []
    ratios: list[float] = []
    compact_build: list[float] = []
    prefix_build: list[float] = []
    external: list[float] = []
    checksums: set[str] = set()

    required_positive = (
        "pid",
        "pair",
        "bits",
        "queries",
        "warmup_queries",
        "dataset_ns",
        "input_clone_ns",
        "compact_build_ns",
        "prefix_build_ns",
        "query_build_ns",
        "warmup_ns",
        "compact_warmup_ns",
        "prefix_warmup_ns",
        "compact_ns",
        "prefix_ns",
        "checksum",
        "compact_bytes",
        "prefix_bytes",
        "main_elapsed_ns",
        "external_wall_ns",
    )
    for record in records:
        values = {field: positive_integer(record, field) for field in required_positive}
        if values["bits"] != expected_bits or values["queries"] != expected_queries:
            raise SystemExit("RESULT input differs from SESSION_START")
        if values["compact_bytes"] != expected_compact_bytes:
            raise SystemExit("compact byte count differs from the fixed layout")
        if values["prefix_bytes"] != expected_prefix_bytes:
            raise SystemExit("prefix byte count differs from the full table")
        if record.get("cpu") != str(session_cpu):
            raise SystemExit("RESULT CPU differs from SESSION_START")
        if values["external_wall_ns"] < values["compact_ns"] + values["prefix_ns"]:
            raise SystemExit("external wall time is shorter than both timed queries")

        compact_rate = float(record["compact_ns_per_query"])
        prefix_rate = float(record["prefix_ns_per_query"])
        expected_compact_rate = values["compact_ns"] / expected_queries
        expected_prefix_rate = values["prefix_ns"] / expected_queries
        if not math.isclose(compact_rate, expected_compact_rate, rel_tol=2e-9, abs_tol=1e-9):
            raise SystemExit("compact rate is inconsistent with elapsed time")
        if not math.isclose(prefix_rate, expected_prefix_rate, rel_tol=2e-9, abs_tol=1e-9):
            raise SystemExit("prefix rate is inconsistent with elapsed time")

        compact.append(compact_rate)
        prefix.append(prefix_rate)
        ratios.append(prefix_rate / compact_rate)
        compact_build.append(values["compact_build_ns"] / 1_000_000)
        prefix_build.append(values["prefix_build_ns"] / 1_000_000)
        external.append(values["external_wall_ns"] / 1_000_000)
        checksums.add(record["checksum"])

    if len(checksums) != 1:
        raise SystemExit("query checksums differ across processes")

    print(
        "replication=fresh_process paired_interval=exact_96.1_percent_median_order_statistic "
        "interval_assumptions=iid_continuous_pair_ratios"
    )
    print(
        f"bits={expected_bits} queries_per_variant={expected_queries} "
        f"compact_bytes={expected_compact_bytes} prefix_bytes={expected_prefix_bytes} "
        f"prefix_over_compact_bytes={expected_prefix_bytes / expected_compact_bytes:.9f}"
    )
    describe("compact ns_per_query", compact)
    describe("prefix ns_per_query", prefix)
    describe_ratios("paired prefix/compact", ratios)
    describe("compact build_ms", compact_build)
    describe("prefix build_ms", prefix_build)
    describe("external launch_to_exit_ms", external)


if __name__ == "__main__":
    main()
