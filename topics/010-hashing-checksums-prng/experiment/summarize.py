#!/usr/bin/env python3
"""Validate and summarize Topic 10 fresh-process CRC32C pairs."""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from pathlib import Path

VALID_MODES = ("table", "hardware")
VALID_ORDERS = ("table-hardware", "hardware-table")
PAIRS = 12
T_975_DF11 = 2.200985160082949
WARMUP_TARGET_BYTES = 64 * 1024 * 1024


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


def integer_field(record: dict[str, str], field: str, minimum: int) -> int:
    try:
        value = int(record[field])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid integer field {field!r}: {record}") from error
    if value < minimum:
        raise SystemExit(f"field {field!r} below {minimum}: {record}")
    return value


def float_field(record: dict[str, str], field: str) -> float:
    try:
        value = float(record[field])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid floating-point field {field!r}: {record}") from error
    if not math.isfinite(value) or value <= 0.0:
        raise SystemExit(f"field {field!r} must be finite and positive: {record}")
    return value


def validate_result(record: dict[str, str]) -> dict[str, int | float | str]:
    mode = record.get("mode")
    if mode not in VALID_MODES:
        raise SystemExit(f"invalid mode: {record}")
    values: dict[str, int | float | str] = {"mode": mode}
    for field in (
        "len",
        "iterations",
        "total_bytes",
        "elapsed_ns",
        "warmup_bytes",
        "pid",
        "pair",
        "position",
        "external_wall_ns",
    ):
        values[field] = integer_field(record, field, 1)
    for field in ("align", "setup_ns", "cpu", "address_mod_64"):
        values[field] = integer_field(record, field, 0)
    ns_per_byte = float_field(record, "ns_per_byte")
    gb_per_s = float_field(record, "gb_per_s")
    values["ns_per_byte"] = ns_per_byte
    values["gb_per_s"] = gb_per_s

    length = int(values["len"])
    iterations = int(values["iterations"])
    total_bytes = int(values["total_bytes"])
    elapsed_ns = int(values["elapsed_ns"])
    if total_bytes != length * iterations:
        raise SystemExit("total_bytes differs from len*iterations")
    expected_ns_per_byte = elapsed_ns / total_bytes
    expected_gb_per_s = total_bytes / elapsed_ns
    if not math.isclose(ns_per_byte, expected_ns_per_byte, rel_tol=2e-6, abs_tol=1e-9):
        raise SystemExit("ns_per_byte is inconsistent with elapsed_ns/total_bytes")
    if not math.isclose(gb_per_s, expected_gb_per_s, rel_tol=2e-6, abs_tol=1e-9):
        raise SystemExit("gb_per_s is inconsistent with total_bytes/elapsed_ns")
    if int(values["external_wall_ns"]) < elapsed_ns:
        raise SystemExit("external wall interval is shorter than the timed interval")
    if int(values["address_mod_64"]) >= 64:
        raise SystemExit("address_mod_64 is outside [0, 63]")
    for field in ("checksum", "digest"):
        value = record.get(field)
        if value is None or not value:
            raise SystemExit(f"missing {field}: {record}")
        values[field] = value
    order = record.get("order")
    if order not in VALID_ORDERS:
        raise SystemExit(f"invalid order: {record}")
    values["order"] = order
    return values


def locate_bench(name: str) -> None:
    matches: list[str] = []
    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        target = message.get("target", {})
        if (
            message.get("reason") == "compiler-artifact"
            and target.get("name") == name
            and "bench" in target.get("kind", [])
            and message.get("executable")
        ):
            matches.append(message["executable"])
    if not matches:
        raise SystemExit(f"Cargo JSON contained no executable bench named {name!r}")
    print(matches[-1])


def schema_check(path: Path) -> None:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(lines) != 2 or not all(line.startswith("RESULT ") for line in lines):
        raise SystemExit("schema check expects exactly two RESULT lines")
    results = [validate_result(parse_record(line)) for line in lines]
    if [result["mode"] for result in results] != ["table", "hardware"]:
        raise SystemExit("schema check must contain table then hardware")
    for result in results:
        if result["pair"] != 1 or result["order"] != "table-hardware":
            raise SystemExit("schema check carries inconsistent pair metadata")
    print(f"SCHEMA_OK records={len(results)}")


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def describe(label: str, values: list[float], unit: str) -> None:
    print(
        f"{label}: n={len(values)} median={statistics.median(values):.9f}{unit} "
        f"mad={median_absolute_deviation(values):.9f}{unit} "
        f"min={min(values):.9f}{unit} max={max(values):.9f}{unit}"
    )


def describe_ratios(ratios: list[float], by_order: dict[str, list[float]]) -> None:
    logs = [math.log(value) for value in ratios]
    log_mean = statistics.fmean(logs)
    half_width = T_975_DF11 * statistics.stdev(logs) / math.sqrt(len(logs))
    print(
        "paired table_elapsed/hardware_elapsed (hardware_speedup): "
        f"pairs={len(ratios)} median={statistics.median(ratios):.9f}x "
        f"mad={median_absolute_deviation(ratios):.9f}x "
        f"min={min(ratios):.9f}x max={max(ratios):.9f}x "
        f"geomean={math.exp(log_mean):.9f}x "
        f"pooled_descriptive_log_ratio_t95_mean_ci=[{math.exp(log_mean - half_width):.9f}x,"
        f"{math.exp(log_mean + half_width):.9f}x] "
        "ci_scope=between_pair_process_variation "
        "ci_assumptions=iid_pairs_and_approximately_normal_log_ratios"
    )
    for order in VALID_ORDERS:
        values = by_order[order]
        print(
            f"paired hardware_speedup order={order}: pairs={len(values)} "
            f"median={statistics.median(values):.9f}x "
            f"mad={median_absolute_deviation(values):.9f}x "
            f"min={min(values):.9f}x max={max(values):.9f}x "
            f"exact96.875%_median_interval=[{min(values):.9f}x,{max(values):.9f}x] "
            "interval_assumptions=iid_continuous_ratios_within_order_stratum"
        )


def summarize(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    session: dict[str, str] | None = None
    current_pair: dict[str, str] | None = None
    records: list[dict[str, int | float | str]] = []
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
            pair = len(records) // 2 + 1
            expected_order = VALID_ORDERS[(pair - 1) % 2]
            if current_pair.get("pair") != str(pair):
                raise SystemExit(f"line {line_number}: expected pair {pair}")
            if current_pair.get("order") != expected_order:
                raise SystemExit(f"pair {pair}: expected order {expected_order}")
        elif line.startswith("RESULT "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: RESULT outside a pair")
            record = validate_result(parse_record(line))
            if str(record["pair"]) != current_pair.get("pair"):
                raise SystemExit(f"line {line_number}: RESULT pair mismatch")
            if record["order"] != current_pair.get("order"):
                raise SystemExit(f"line {line_number}: RESULT order mismatch")
            records.append(record)
        elif line.startswith("PAIR_END "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: PAIR_END outside a pair")
            end = parse_record(line)
            pair = int(current_pair["pair"])
            if end.get("pair") != str(pair) or len(records) != pair * 2:
                raise SystemExit(f"line {line_number}: incomplete or mismatched pair")
            current_pair = None
        elif line.startswith("SESSION_END "):
            if session is None or current_pair is not None or ended:
                raise SystemExit(f"line {line_number}: unexpected SESSION_END")
            ended = True
        elif line.startswith("ARTIFACT "):
            if session is None or current_pair is not None or ended:
                raise SystemExit(f"line {line_number}: unexpected ARTIFACT")
            artifact = parse_record(line)
            if not re.fullmatch(
                r"[0-9a-f]{64}", artifact.get("benchmark_binary_sha256", "")
            ):
                raise SystemExit(f"line {line_number}: invalid benchmark artifact hash")
        elif current_pair is not None:
            raise SystemExit(f"line {line_number}: unexpected line inside pair")
        elif line.strip():
            raise SystemExit(f"line {line_number}: unexpected session record")

    if session is None or not ended:
        raise SystemExit("expected one complete session")
    if integer_field(session, "pairs", 1) != PAIRS:
        raise SystemExit(f"SESSION_START must declare exactly {PAIRS} pairs")
    if not re.fullmatch(r"[0-9a-f]{40}", session.get("source_commit", "")):
        raise SystemExit("SESSION_START has an invalid source_commit")
    if not re.fullmatch(
        r"[0-9a-f]{64}", session.get("source_archive_sha256", "")
    ):
        raise SystemExit("SESSION_START has an invalid source_archive_sha256")
    if len(records) != PAIRS * 2:
        raise SystemExit(f"expected {PAIRS * 2} process records, found {len(records)}")
    if len({int(record["pid"]) for record in records}) != PAIRS * 2:
        raise SystemExit("expected one distinct process ID per measurement")

    expected_len = integer_field(session, "len", 1)
    expected_align = integer_field(session, "align", 0)
    expected_iterations = integer_field(session, "iterations", 1)
    expected_cpu = integer_field(session, "cpu", 0)
    if expected_cpu != 0:
        raise SystemExit("recorded experiment must use CPU 0")

    by_mode: dict[str, list[dict[str, int | float | str]]] = {
        mode: [] for mode in VALID_MODES
    }
    ratios: list[float] = []
    by_order: dict[str, list[float]] = {order: [] for order in VALID_ORDERS}
    checksums: set[str] = set()
    digests: set[str] = set()
    warmup_bytes: set[int] = set()
    address_mod_64_values: set[int] = set()

    for pair in range(1, PAIRS + 1):
        pair_records = records[(pair - 1) * 2 : pair * 2]
        order = VALID_ORDERS[(pair - 1) % 2]
        expected_modes = order.split("-")
        if [record["mode"] for record in pair_records] != expected_modes:
            raise SystemExit(f"pair {pair}: result sequence differs from declared order")
        if [record["position"] for record in pair_records] != [1, 2]:
            raise SystemExit(f"pair {pair}: invalid process positions")
        for record in pair_records:
            if (
                record["len"] != expected_len
                or record["align"] != expected_align
                or record["iterations"] != expected_iterations
                or record["cpu"] != expected_cpu
            ):
                raise SystemExit("RESULT workload differs from SESSION_START")
            by_mode[str(record["mode"])].append(record)
            checksums.add(str(record["checksum"]))
            digests.add(str(record["digest"]))
            warmup_bytes.add(int(record["warmup_bytes"]))
            address_mod_64_values.add(int(record["address_mod_64"]))
        table = next(record for record in pair_records if record["mode"] == "table")
        hardware = next(record for record in pair_records if record["mode"] == "hardware")
        ratio = int(table["elapsed_ns"]) / int(hardware["elapsed_ns"])
        ratios.append(ratio)
        by_order[order].append(ratio)

    if len(checksums) != 1 or len(digests) != 1:
        raise SystemExit("checksum or digest differs across modes/processes")
    if len(warmup_bytes) != 1:
        raise SystemExit("warmup size differs across processes")
    expected_warmup_bytes = (
        (WARMUP_TARGET_BYTES + expected_len - 1) // expected_len
    ) * expected_len
    if warmup_bytes != {expected_warmup_bytes}:
        raise SystemExit("warmup byte count differs from the producer formula")
    if any(len(by_order[order]) != PAIRS // 2 for order in VALID_ORDERS):
        raise SystemExit("order strata are not balanced 6/6")

    print(
        "replication=24_fresh_processes pairing=12_order_balanced_pairs "
        "orders=6_table-hardware_and_6_hardware-table cpu=0"
    )
    print(
        f"len={expected_len} align={expected_align} iterations={expected_iterations} "
        f"bytes_per_process={expected_len * expected_iterations} "
        f"warmup_bytes_per_process={next(iter(warmup_bytes))} "
        "address_mod_64_values="
        + ",".join(str(value) for value in sorted(address_mod_64_values))
    )
    for mode in VALID_MODES:
        mode_records = by_mode[mode]
        describe(
            f"{mode} elapsed",
            [int(record["elapsed_ns"]) / 1_000_000 for record in mode_records],
            "ms",
        )
        describe(
            f"{mode} throughput",
            [float(record["gb_per_s"]) for record in mode_records],
            "GB/s",
        )
        describe(
            f"{mode} setup",
            [int(record["setup_ns"]) / 1_000_000 for record in mode_records],
            "ms",
        )
        describe(
            f"{mode} launch_to_exit",
            [int(record["external_wall_ns"]) / 1_000_000 for record in mode_records],
            "ms",
        )
    describe_ratios(ratios, by_order)


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--locate-bench":
        locate_bench(args[1])
    elif len(args) == 2 and args[0] == "--schema-check":
        schema_check(Path(args[1]))
    elif len(args) == 1:
        summarize(Path(args[0]))
    else:
        raise SystemExit(
            "usage: summarize.py processes.txt | "
            "summarize.py --schema-check smoke.txt | "
            "summarize.py --locate-bench NAME"
        )


if __name__ == "__main__":
    main()
