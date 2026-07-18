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

    pattern_orders = (
        "zeros,alternating,random",
        "zeros,random,alternating",
        "alternating,zeros,random",
        "alternating,random,zeros",
        "random,zeros,alternating",
        "random,alternating,zeros",
    )

    # Walk the log sequentially so the accepted protocol is the recorded
    # protocol: one session, pairs 1..12 in order, and each pair's six RESULT
    # records inside its PAIR_START/PAIR_END block in the declared
    # pattern-by-variant order. Provenance lines (checksums, VERIFY) are
    # allowed only outside pair blocks.
    session: dict[str, str] | None = None
    session_ended = False
    current_pair: dict[str, object] | None = None
    completed_pairs = 0
    records: list[dict[str, str]] = []

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("SESSION_START "):
            if session is not None:
                raise SystemExit(f"line {line_number}: duplicate SESSION_START")
            session = parse_result(line)
        elif line.startswith("SESSION_END "):
            if session is None or session_ended:
                raise SystemExit(f"line {line_number}: unexpected SESSION_END")
            if current_pair is not None:
                raise SystemExit(f"line {line_number}: SESSION_END inside a pair")
            session_ended = True
        elif line.startswith("PAIR_START "):
            if session is None or session_ended:
                raise SystemExit(f"line {line_number}: PAIR_START outside a session")
            if current_pair is not None:
                raise SystemExit(f"line {line_number}: nested PAIR_START")
            record = parse_result(line)
            pair = int(record["pair"])
            if pair != completed_pairs + 1:
                raise SystemExit(
                    f"line {line_number}: PAIR_START pair={pair}, "
                    f"expected pair={completed_pairs + 1}"
                )
            pattern_index = (pair - 1 + (pair - 1) // 6) % 6
            expected_variant_order = "branch,select" if pair % 2 == 1 else "select,branch"
            if record.get("pattern_order") != pattern_orders[pattern_index]:
                raise SystemExit(f"pair {pair} has invalid pattern order")
            if record.get("variant_order") != expected_variant_order:
                raise SystemExit(f"pair {pair} has invalid declared variant order")
            current_pair = {
                "pair": pair,
                "patterns": pattern_orders[pattern_index].split(","),
                "variants": expected_variant_order.split(","),
                "results": [],
            }
        elif line.startswith("PAIR_END "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: PAIR_END outside a pair")
            record = parse_result(line)
            if int(record["pair"]) != current_pair["pair"]:
                raise SystemExit(f"line {line_number}: PAIR_END pair mismatch")
            results = current_pair["results"]
            assert isinstance(results, list)
            if len(results) != 6:
                raise SystemExit(
                    f"pair {current_pair['pair']} has {len(results)} RESULT "
                    "records, expected 6"
                )
            completed_pairs += 1
            current_pair = None
        elif line.startswith("RESULT "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: RESULT outside a pair")
            record = parse_result(line)
            results = current_pair["results"]
            assert isinstance(results, list)
            index = len(results)
            if index >= 6:
                raise SystemExit(
                    f"line {line_number}: more than six RESULT records in "
                    f"pair {current_pair['pair']}"
                )
            patterns = current_pair["patterns"]
            variants = current_pair["variants"]
            assert isinstance(patterns, list) and isinstance(variants, list)
            expected_pattern = patterns[index // 2]
            expected_variant = variants[index % 2]
            expected_order = str(index % 2 + 1)
            if record.get("pair") != str(current_pair["pair"]):
                raise SystemExit(f"line {line_number}: RESULT pair mismatch")
            if record.get("pattern") != expected_pattern:
                raise SystemExit(
                    f"line {line_number}: RESULT pattern "
                    f"{record.get('pattern')!r}, expected {expected_pattern!r}"
                )
            if record.get("variant") != expected_variant:
                raise SystemExit(
                    f"line {line_number}: RESULT variant "
                    f"{record.get('variant')!r}, expected {expected_variant!r}"
                )
            if record.get("order") != expected_order:
                raise SystemExit(
                    f"line {line_number}: RESULT order "
                    f"{record.get('order')!r}, expected {expected_order!r}"
                )
            results.append(record)
            records.append(record)
        elif current_pair is not None:
            raise SystemExit(
                f"line {line_number}: unexpected record inside "
                f"pair {current_pair['pair']}"
            )

    if session is None:
        raise SystemExit("expected exactly one SESSION_START record")
    if not session_ended:
        raise SystemExit("expected exactly one SESSION_END record")
    if completed_pairs != 12:
        raise SystemExit(f"expected 12 completed pairs, found {completed_pairs}")
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
        "cpu",
    }
    for index, record in enumerate(records, start=1):
        missing = required_fields - set(record)
        if missing:
            raise SystemExit(f"RESULT {index} missing fields: {sorted(missing)}")

    session_cpu = session.get("cpu")
    if session_cpu is None or not session_cpu.isdigit():
        raise SystemExit("SESSION_START must declare the pinned cpu")
    cpus = {record["cpu"] for record in records}
    if cpus != {session_cpu}:
        raise SystemExit(
            f"expected every RESULT on cpu {session_cpu}, found {sorted(cpus)}"
        )

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
