#!/usr/bin/env python3
"""Summarize process-level branch/select pairs without third-party packages."""

from __future__ import annotations

import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parse_result(line: str) -> dict[str, str]:
    fields = line.split()
    return dict(field.split("=", 1) for field in fields[1:])


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: summarize.py processes.txt")

    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    if sum(line.startswith("SESSION_START ") for line in lines) != 1:
        raise SystemExit("expected exactly one SESSION_START record")
    if sum(line.startswith("SESSION_END ") for line in lines) != 1:
        raise SystemExit("expected exactly one SESSION_END record")
    pair_starts = [parse_result(line) for line in lines if line.startswith("PAIR_START ")]
    pair_ends = [parse_result(line) for line in lines if line.startswith("PAIR_END ")]
    if len(pair_starts) != 12:
        raise SystemExit("expected 12 PAIR_START records")
    if len(pair_ends) != 12:
        raise SystemExit("expected 12 PAIR_END records")

    pattern_orders = (
        "zeros,alternating,random",
        "zeros,random,alternating",
        "alternating,zeros,random",
        "alternating,random,zeros",
        "random,zeros,alternating",
        "random,alternating,zeros",
    )
    starts_by_pair = {int(record["pair"]): record for record in pair_starts}
    ends_by_pair = {int(record["pair"]): record for record in pair_ends}
    if set(starts_by_pair) != set(range(1, 13)) or len(starts_by_pair) != 12:
        raise SystemExit("PAIR_START identifiers must be exactly 1..12")
    if set(ends_by_pair) != set(range(1, 13)) or len(ends_by_pair) != 12:
        raise SystemExit("PAIR_END identifiers must be exactly 1..12")
    for pair, record in starts_by_pair.items():
        pattern_index = (pair - 1 + (pair - 1) // 6) % 6
        expected_variant_order = "branch,select" if pair % 2 == 1 else "select,branch"
        if record.get("pattern_order") != pattern_orders[pattern_index]:
            raise SystemExit(f"pair {pair} has invalid pattern order")
        if record.get("variant_order") != expected_variant_order:
            raise SystemExit(f"pair {pair} has invalid declared variant order")

    records = [
        parse_result(line)
        for line in lines
        if line.startswith("RESULT ")
    ]
    if len(records) != 72:
        raise SystemExit(f"expected 72 RESULT records, found {len(records)}")

    required_fields = {
        "pid",
        "variant",
        "pattern",
        "length",
        "repetitions",
        "warmup_repetitions",
        "pair",
        "order",
        "ones",
        "timed_ns",
        "main_ns",
        "ns_per_decision",
        "external_wall_ns",
        "checksum",
    }
    for index, record in enumerate(records, start=1):
        missing = required_fields - set(record)
        if missing:
            raise SystemExit(f"RESULT {index} missing fields: {sorted(missing)}")

    pairs = {int(record["pair"]) for record in records}
    if pairs != set(range(1, 13)):
        raise SystemExit(f"expected pair identifiers 1..12, found {sorted(pairs)}")
    if len({record["pid"] for record in records}) != 72:
        raise SystemExit("expected one distinct process id per RESULT record")
    for field in ("length", "repetitions", "warmup_repetitions"):
        values = {record[field] for record in records}
        if len(values) != 1:
            raise SystemExit(f"inconsistent {field} values: {sorted(values)}")
        if int(next(iter(values))) <= 0:
            raise SystemExit(f"{field} must be positive")

    combinations = Counter(
        (record["pattern"], record["variant"], int(record["pair"]))
        for record in records
    )
    expected_combinations = {
        (pattern, variant, pair)
        for pattern in ("zeros", "alternating", "random")
        for variant in ("branch", "select")
        for pair in range(1, 13)
    }
    if set(combinations) != expected_combinations or set(combinations.values()) != {1}:
        raise SystemExit("expected exactly one result per pattern, variant, and pair")

    for pair in range(1, 13):
        expected_orders = {"branch": 1, "select": 2}
        if pair % 2 == 0:
            expected_orders = {"branch": 2, "select": 1}
        for pattern in ("zeros", "alternating", "random"):
            observed = {
                record["variant"]: int(record["order"])
                for record in records
                if int(record["pair"]) == pair and record["pattern"] == pattern
            }
            if observed != expected_orders:
                raise SystemExit(
                    f"pair {pair} pattern {pattern} has invalid variant order: {observed}"
                )

    for pattern in ("zeros", "alternating", "random"):
        ones = {record["ones"] for record in records if record["pattern"] == pattern}
        checksums = {
            record["checksum"] for record in records if record["pattern"] == pattern
        }
        if len(ones) != 1 or len(checksums) != 1:
            raise SystemExit(f"pattern {pattern} did not use one fixed input and result")

    for record in records:
        for field in ("timed_ns", "main_ns", "external_wall_ns"):
            if int(record[field]) <= 0:
                raise SystemExit(f"nonpositive {field} in pid {record['pid']}")
        decisions = int(record["length"]) * int(record["repetitions"])
        observed_rate = float(record["ns_per_decision"])
        expected_rate = int(record["timed_ns"]) / decisions
        if not math.isfinite(observed_rate) or observed_rate <= 0:
            raise SystemExit(f"invalid ns_per_decision in pid {record['pid']}")
        if not math.isclose(observed_rate, expected_rate, rel_tol=2e-9, abs_tol=1e-9):
            raise SystemExit(f"inconsistent ns_per_decision in pid {record['pid']}")

    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    paired: dict[tuple[str, int], dict[str, float]] = defaultdict(dict)
    for record in records:
        pattern = record["pattern"]
        variant = record["variant"]
        value = float(record["ns_per_decision"])
        grouped[(pattern, variant)].append(value)
        paired[(pattern, int(record["pair"]))][variant] = value

    print(
        "replication=fresh_process "
        "paired_interval=exact_96.1_percent_median_order_statistic "
        "interval_assumptions=iid_continuous_pair_ratios"
    )
    for pattern in ("zeros", "alternating", "random"):
        for variant in ("branch", "select"):
            values = grouped[(pattern, variant)]
            print(
                f"{pattern} {variant}: n={len(values)} "
                f"mean={statistics.fmean(values):.9f} "
                f"sd={statistics.stdev(values):.9f} "
                f"median={statistics.median(values):.9f} "
                f"mad={median_absolute_deviation(values):.9f} "
                f"min={min(values):.9f} max={max(values):.9f}"
            )

        ratios = sorted(
            pair["branch"] / pair["select"]
            for (paired_pattern, _), pair in paired.items()
            if paired_pattern == pattern and set(pair) == {"branch", "select"}
        )
        if len(ratios) != 12:
            raise SystemExit(f"expected 12 complete {pattern} pairs, found {len(ratios)}")
        geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
        print(
            f"{pattern} paired branch/select: pairs=12 "
            f"geomean={geometric_mean:.9f} median={statistics.median(ratios):.9f} "
            f"mad={median_absolute_deviation(ratios):.9f} "
            f"exact96.1%=[{ratios[2]:.9f},{ratios[9]:.9f}]"
        )


if __name__ == "__main__":
    main()
