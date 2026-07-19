#!/usr/bin/env python3
"""Validate and summarize Topic 9 process-level pairs."""

from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

# RESULT fields that are meaningless at zero: identifiers, sizes, and the
# timed query intervals that feed the paired-ratio math.
RESULT_POSITIVE_FIELDS = (
    "pid",
    "pair",
    "bits",
    "queries",
    "warmup_queries",
    "compact_ns",
    "prefix_ns",
    "compact_bytes",
    "prefix_bytes",
    "main_elapsed_ns",
    "external_wall_ns",
)

# RESULT fields whose producer contract allows zero: stage durations can
# quantize to zero on hosts with coarse monotonic clocks, and `checksum` is
# a value, not a counter of performed work. `ones` (also a zero-allowed
# value) is validated separately because archived 4e855a3 sessions predate
# the field; see `validate_result_record`.
RESULT_NON_NEGATIVE_FIELDS = (
    "dataset_ns",
    "input_clone_ns",
    "compact_build_ns",
    "prefix_build_ns",
    "query_build_ns",
    "warmup_ns",
    "compact_warmup_ns",
    "prefix_warmup_ns",
    "checksum",
)

VALID_ORDERS = ("compact-prefix", "prefix-compact")

# Mirrors `WARMUP_QUERIES` in `benches/succinct_rank.rs`: every process warms
# each variant with `min(queries, WARMUP_QUERIES)` positions.
WARMUP_QUERIES = 262_144


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
        raise ValueError(f"balanced summary requires 12 pairs, got {len(ratios)}")
    geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
    print(
        f"{label}: pairs={len(ratios)} geomean={geometric_mean:.9f} "
        f"median={statistics.median(ratios):.9f} "
        f"mad={median_absolute_deviation(ratios):.9f} "
        f"min={min(ratios):.9f} max={max(ratios):.9f}"
    )


def describe_ratio_stratum(label: str, ratios: list[float]) -> None:
    if len(ratios) != 6:
        raise ValueError(f"order stratum requires 6 pairs, got {len(ratios)}")
    print(
        f"{label}: pairs={len(ratios)} median={statistics.median(ratios):.9f} "
        f"mad={median_absolute_deviation(ratios):.9f} "
        f"exact96.875%_median_interval=[{min(ratios):.9f},{max(ratios):.9f}] "
        "interval_assumptions=iid_continuous_ratios_within_this_order_stratum"
    )


def integer_field(record: dict[str, str], field: str, minimum: int) -> int:
    try:
        value = int(record[field])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid integer field {field!r}: {record}") from error
    if value < minimum:
        raise SystemExit(f"field {field!r} below {minimum}: {record}")
    return value


def positive_integer(record: dict[str, str], field: str) -> int:
    return integer_field(record, field, 1)


def validate_result_record(
    record: dict[str, str],
    *,
    require_ones: bool = True,
) -> tuple[dict[str, int], float, float]:
    """Check one RESULT record against the producer schema.

    Returns the validated integer fields plus the reported per-query rates.
    Session-level cross-checks (bits, queries, bytes, cpu, ones) stay in
    `main`. `require_ones` is False only for archived 4e855a3 sessions,
    whose producer predates the dataset fingerprint; such records must not
    carry the field at all.
    """
    values = {
        field: integer_field(record, field, 1) for field in RESULT_POSITIVE_FIELDS
    }
    values.update(
        {field: integer_field(record, field, 0) for field in RESULT_NON_NEGATIVE_FIELDS}
    )
    if require_ones:
        values["ones"] = integer_field(record, "ones", 0)
    elif "ones" in record:
        raise SystemExit(f"unexpected ones field in archived-schema record: {record}")
    if record.get("order") not in VALID_ORDERS:
        raise SystemExit(f"invalid order field: {record}")
    integer_field(record, "cpu", 0)

    try:
        compact_rate = float(record["compact_ns_per_query"])
        prefix_rate = float(record["prefix_ns_per_query"])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid rate field: {record}") from error
    expected_compact_rate = values["compact_ns"] / values["queries"]
    expected_prefix_rate = values["prefix_ns"] / values["queries"]
    if not math.isclose(compact_rate, expected_compact_rate, rel_tol=2e-9, abs_tol=1e-9):
        raise SystemExit("compact rate is inconsistent with elapsed time")
    if not math.isclose(prefix_rate, expected_prefix_rate, rel_tol=2e-9, abs_tol=1e-9):
        raise SystemExit("prefix rate is inconsistent with elapsed time")

    if values["warmup_queries"] != min(values["queries"], WARMUP_QUERIES):
        raise SystemExit("warmup workload differs from the producer formula")

    # The producer intervals nest: warmup covers both per-variant warmups,
    # `main_elapsed_ns` covers every sequential in-process stage, and the
    # runner's external wall time encloses the whole process.
    if values["warmup_ns"] < values["compact_warmup_ns"] + values["prefix_warmup_ns"]:
        raise SystemExit("warmup interval is shorter than its per-variant warmups")
    stage_total = (
        values["dataset_ns"]
        + values["input_clone_ns"]
        + values["compact_build_ns"]
        + values["prefix_build_ns"]
        + values["query_build_ns"]
        + values["warmup_ns"]
        + values["compact_ns"]
        + values["prefix_ns"]
    )
    if values["main_elapsed_ns"] < stage_total:
        raise SystemExit("main interval is shorter than its sequential stages")
    if values["external_wall_ns"] < values["main_elapsed_ns"]:
        raise SystemExit("external wall time is shorter than the main interval")

    return values, compact_rate, prefix_rate


def expected_compact_byte_count(bits: int) -> int:
    """Mirror `CompactRank::logical_bytes` in `src/lib.rs`.

    The layout is `u64` payload words, one `u32` superblock count per
    `SUPERBLOCK_WORDS = 8` words (rounded up), and one `u16` count per word.
    """
    words = bits // 64
    return words * 8 + ((words + 7) // 8) * 4 + words * 2


def schema_check(path: Path) -> None:
    """Validate a single smoke RESULT line before a session collects pairs."""
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if len(lines) != 1 or not lines[0].startswith("RESULT "):
        raise SystemExit(
            "schema check expects exactly one non-empty RESULT line, found "
            f"{len(lines)} line(s)"
        )
    record = parse_record(lines[0])
    values, _, _ = validate_result_record(record)
    if values["compact_bytes"] != expected_compact_byte_count(values["bits"]):
        raise SystemExit("compact byte count differs from the fixed layout")
    if values["prefix_bytes"] != (values["bits"] + 1) * 4:
        raise SystemExit("prefix byte count differs from the full table")
    print(f"SCHEMA_OK fields={len(record)}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--schema-check":
        schema_check(Path(args[1]))
        return
    if len(args) != 1:
        raise SystemExit(
            "usage: summarize.py processes.txt | summarize.py --schema-check smoke.txt"
        )

    lines = Path(args[0]).read_text(encoding="utf-8").splitlines()
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
    if positive_integer(session, "pairs") != 12:
        raise SystemExit("SESSION_START must declare exactly 12 pairs")
    if len(records) != 12:
        raise SystemExit(f"expected 12 paired process records, found {len(records)}")
    if len({integer_field(record, "pid", 1) for record in records}) != 12:
        raise SystemExit("expected one distinct process ID per pair")

    bit_power = positive_integer(session, "bit_power")
    if not 6 <= bit_power <= 31:
        raise SystemExit("bit_power outside the producer contract [6, 31]")
    expected_bits = 1 << bit_power
    expected_queries = positive_integer(session, "queries")
    expected_compact_bytes = expected_compact_byte_count(expected_bits)
    expected_prefix_bytes = (expected_bits + 1) * 4
    session_cpu = positive_integer(session, "cpu") if session.get("cpu") != "0" else 0
    # Sessions from eddb9f3 onward record the exhaustively verified dataset
    # fingerprint in SESSION_START; archived 4e855a3 sessions predate it.
    # The two schemas must not mix within one session file.
    session_ones = (
        integer_field(session, "ones", 0) if session.get("ones") is not None else None
    )

    compact: list[float] = []
    prefix: list[float] = []
    ratios: list[float] = []
    ratios_by_order: dict[str, list[float]] = {order: [] for order in VALID_ORDERS}
    compact_build: list[float] = []
    prefix_build: list[float] = []
    external: list[float] = []
    checksums: set[str] = set()
    dataset_ones: set[int] = set()

    for record in records:
        values, compact_rate, prefix_rate = validate_result_record(
            record, require_ones=session_ones is not None
        )
        if values["bits"] != expected_bits or values["queries"] != expected_queries:
            raise SystemExit("RESULT input differs from SESSION_START")
        if values["compact_bytes"] != expected_compact_bytes:
            raise SystemExit("compact byte count differs from the fixed layout")
        if values["prefix_bytes"] != expected_prefix_bytes:
            raise SystemExit("prefix byte count differs from the full table")
        if record.get("cpu") != str(session_cpu):
            raise SystemExit("RESULT CPU differs from SESSION_START")

        compact.append(compact_rate)
        prefix.append(prefix_rate)
        ratio = prefix_rate / compact_rate
        ratios.append(ratio)
        ratios_by_order[record["order"]].append(ratio)
        compact_build.append(values["compact_build_ns"] / 1_000_000)
        prefix_build.append(values["prefix_build_ns"] / 1_000_000)
        external.append(values["external_wall_ns"] / 1_000_000)
        checksums.add(record["checksum"])
        if session_ones is not None:
            dataset_ones.add(values["ones"])

    if len(checksums) != 1:
        raise SystemExit("query checksums differ across processes")
    if session_ones is not None:
        if len(dataset_ones) != 1:
            raise SystemExit("dataset fingerprints (ones) differ across processes")
        if dataset_ones != {session_ones}:
            raise SystemExit(
                "RESULT dataset fingerprint differs from the exhaustively "
                "verified session ones"
            )

    print(
        "replication=fresh_process pooled_ratio_summary=descriptive "
        "order_strata=6_compact-prefix_and_6_prefix-compact"
    )
    print(
        f"bits={expected_bits} queries_per_variant={expected_queries} "
        f"compact_bytes={expected_compact_bytes} prefix_bytes={expected_prefix_bytes} "
        f"prefix_over_compact_bytes={expected_prefix_bytes / expected_compact_bytes:.9f}"
    )
    describe("compact ns_per_query", compact)
    describe("prefix ns_per_query", prefix)
    describe_ratios("paired prefix/compact", ratios)
    for order in VALID_ORDERS:
        describe_ratio_stratum(f"paired prefix/compact order={order}", ratios_by_order[order])
    describe("compact build_ms", compact_build)
    describe("prefix build_ms", prefix_build)
    describe("external launch_to_exit_ms", external)


if __name__ == "__main__":
    main()
