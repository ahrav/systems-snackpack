#!/usr/bin/env python3
"""Validate and summarize Topic 8 process-level pairs."""

from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict
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
        raise ValueError(f"describe_ratios requires exactly 12 pairs, got {len(ratios)}")
    ordered = sorted(ratios)
    geometric_mean = math.exp(statistics.fmean(math.log(value) for value in ratios))
    print(
        f"{label}: pairs={len(ratios)} geomean={geometric_mean:.9f} "
        f"median={statistics.median(ratios):.9f} "
        f"mad={median_absolute_deviation(ratios):.9f} "
        f"exact96.1%=[{ordered[2]:.9f},{ordered[9]:.9f}]"
    )


def require_positive_int(record: dict[str, str], fields: tuple[str, ...]) -> None:
    for field in fields:
        try:
            value = int(record[field])
        except (KeyError, ValueError) as error:
            raise SystemExit(f"invalid integer field {field!r}: {record}") from error
        if value <= 0:
            raise SystemExit(f"nonpositive {field} in pid {record.get('pid')}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: summarize.py processes.txt")

    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    session: dict[str, str] | None = None
    session_ended = False
    current_pair: dict[str, object] | None = None
    completed_pairs = 0
    records: list[dict[str, str]] = []

    for line_number, line in enumerate(lines, start=1):
        if line.startswith("SESSION_START "):
            if session is not None:
                raise SystemExit(f"line {line_number}: duplicate SESSION_START")
            session = parse_record(line)
        elif line.startswith("SESSION_END "):
            if session is None or session_ended or current_pair is not None:
                raise SystemExit(f"line {line_number}: unexpected SESSION_END")
            session_ended = True
        elif line.startswith("PAIR_START "):
            if session is None or session_ended or current_pair is not None:
                raise SystemExit(f"line {line_number}: unexpected PAIR_START")
            declaration = parse_record(line)
            pair = int(declaration.get("pair", "0"))
            if pair != completed_pairs + 1:
                raise SystemExit(f"line {line_number}: expected pair {completed_pairs + 1}")
            expected_reach = "base,thp" if pair % 2 else "thp,base"
            expected_shootdown = "1,16" if pair % 2 else "16,1"
            if declaration.get("reach_order") != expected_reach:
                raise SystemExit(f"pair {pair} has invalid reach order")
            if declaration.get("shootdown_order") != expected_shootdown:
                raise SystemExit(f"pair {pair} has invalid shootdown order")
            current_pair = {
                "pair": pair,
                "reach": expected_reach.split(","),
                "shootdown": expected_shootdown.split(","),
                "records": [],
            }
        elif line.startswith("RESULT "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: RESULT outside pair")
            record = parse_record(line)
            pair_records = current_pair["records"]
            assert isinstance(pair_records, list)
            index = len(pair_records)
            if index >= 4:
                raise SystemExit(f"line {line_number}: too many results in pair")
            expected_workload = "reach" if index < 2 else "shootdown"
            if record.get("workload") != expected_workload:
                raise SystemExit(f"line {line_number}: unexpected workload order")
            expected_order = str(index % 2 + 1)
            if record.get("pair") != str(current_pair["pair"]):
                raise SystemExit(f"line {line_number}: RESULT pair mismatch")
            if record.get("order") != expected_order:
                raise SystemExit(f"line {line_number}: RESULT order mismatch")
            if expected_workload == "reach":
                reach_order = current_pair["reach"]
                assert isinstance(reach_order, list)
                if record.get("variant") != reach_order[index]:
                    raise SystemExit(f"line {line_number}: reach variant mismatch")
            else:
                shootdown_order = current_pair["shootdown"]
                assert isinstance(shootdown_order, list)
                if record.get("readers") != shootdown_order[index - 2]:
                    raise SystemExit(f"line {line_number}: reader-count mismatch")
            pair_records.append(record)
            records.append(record)
        elif line.startswith("PAIR_END "):
            if current_pair is None:
                raise SystemExit(f"line {line_number}: PAIR_END outside pair")
            end = parse_record(line)
            pair_records = current_pair["records"]
            assert isinstance(pair_records, list)
            if end.get("pair") != str(current_pair["pair"]) or len(pair_records) != 4:
                raise SystemExit(f"line {line_number}: incomplete or mismatched pair")
            completed_pairs += 1
            current_pair = None
        elif current_pair is not None:
            raise SystemExit(f"line {line_number}: unexpected record inside pair")

    if session is None or not session_ended:
        raise SystemExit("expected one complete session")
    if completed_pairs != 12 or len(records) != 48:
        raise SystemExit(
            f"expected 12 pairs and 48 results, found {completed_pairs} and {len(records)}"
        )
    if len({record.get("pid") for record in records}) != 48:
        raise SystemExit("expected one distinct process id per RESULT")
    session_cpu = session.get("cpu")
    if session_cpu is None or not session_cpu.isdigit():
        raise SystemExit("SESSION_START must declare one pinned cpu")
    if {record.get("cpu") for record in records} != {session_cpu}:
        raise SystemExit("RESULT cpu fields do not match the session cpu")

    reach_values: dict[str, list[float]] = defaultdict(list)
    shootdown_values: dict[str, list[float]] = defaultdict(list)
    reach_pairs: dict[int, dict[str, float]] = defaultdict(dict)
    shootdown_pairs: dict[int, dict[str, float]] = defaultdict(dict)

    for record in records:
        require_positive_int(
            record,
            (
                "pid",
                "pair",
                "order",
                "setup_ns",
                "warmup_ns",
                "timed_ns",
                "run_to_pre_emit_ns",
                "external_wall_ns",
            ),
        )
        if int(record["run_to_pre_emit_ns"]) < int(record["timed_ns"]):
            raise SystemExit(
                f"run_to_pre_emit_ns is shorter than timed_ns in pid {record['pid']}"
            )
        if int(record["external_wall_ns"]) < int(record["timed_ns"]):
            raise SystemExit(f"external wall is shorter than timed_ns in pid {record['pid']}")

        pair = int(record["pair"])
        if record["workload"] == "reach":
            required = {
                "variant", "mib", "pages", "passes", "accesses", "ns_per_access",
                "anon_huge_kib_before", "anon_huge_kib_after", "kernel_page_kib",
                "mmu_page_kib", "vm_flags",
            }
            missing = required - set(record)
            if missing:
                raise SystemExit(f"reach RESULT missing fields: {sorted(missing)}")
            require_positive_int(record, ("mib", "pages", "passes", "accesses", "kernel_page_kib", "mmu_page_kib"))
            mib = int(record["mib"])
            pages = int(record["pages"])
            passes = int(record["passes"])
            accesses = int(record["accesses"])
            if mib != int(session["mib"]) or passes != int(session["passes"]):
                raise SystemExit("reach input differs from SESSION_START")
            if pages != mib * 1024 * 1024 // 4096 or accesses != pages * passes:
                raise SystemExit("reach pages or accesses do not match the fixed input")
            variant = record["variant"]
            expected_huge_kib = mib * 1024 if variant == "thp" else 0
            if int(record["anon_huge_kib_before"]) != expected_huge_kib:
                raise SystemExit(f"{variant} mapping was not materialized before timing")
            if int(record["anon_huge_kib_after"]) != expected_huge_kib:
                raise SystemExit(f"{variant} mapping changed during timing")
            required_flag = "hg" if variant == "thp" else "nh"
            if required_flag not in record["vm_flags"].split(","):
                raise SystemExit(f"{variant} mapping lacks VmFlags {required_flag}")
            rate = float(record["ns_per_access"])
            expected_rate = int(record["timed_ns"]) / accesses
            if not math.isfinite(rate) or not math.isclose(rate, expected_rate, rel_tol=2e-9, abs_tol=1e-9):
                raise SystemExit(f"inconsistent ns_per_access in pid {record['pid']}")
            reach_values[variant].append(rate)
            reach_pairs[pair][variant] = rate
        elif record["workload"] == "shootdown":
            required = {
                "readers", "mprotect_pairs", "first_cpu", "warmup_pairs",
                "ns_per_pair", "reader_loads", "reader_checksum",
            }
            missing = required - set(record)
            if missing:
                raise SystemExit(f"shootdown RESULT missing fields: {sorted(missing)}")
            require_positive_int(record, ("readers", "mprotect_pairs", "warmup_pairs", "reader_loads", "reader_checksum"))
            if int(record["reader_checksum"]) != int(record["reader_loads"]):
                raise SystemExit(f"reader checksum differs from load count in pid {record['pid']}")
            readers = record["readers"]
            if readers not in {"1", "16"}:
                raise SystemExit(f"unexpected reader count {readers}")
            if int(record["mprotect_pairs"]) != int(session["mprotect_pairs"]):
                raise SystemExit("shootdown input differs from SESSION_START")
            if record["first_cpu"] != session_cpu:
                raise SystemExit("shootdown controller CPU differs from SESSION_START")
            rate = float(record["ns_per_pair"])
            expected_rate = int(record["timed_ns"]) / int(record["mprotect_pairs"])
            if not math.isfinite(rate) or not math.isclose(rate, expected_rate, rel_tol=2e-9, abs_tol=1e-9):
                raise SystemExit(f"inconsistent ns_per_pair in pid {record['pid']}")
            shootdown_values[readers].append(rate)
            shootdown_pairs[pair][readers] = rate
        else:
            raise SystemExit(f"unknown workload {record['workload']}")

    if set(reach_values) != {"base", "thp"} or any(len(values) != 12 for values in reach_values.values()):
        raise SystemExit("expected 12 reach observations per mapping")
    if set(shootdown_values) != {"1", "16"} or any(len(values) != 12 for values in shootdown_values.values()):
        raise SystemExit("expected 12 shootdown observations per reader count")

    reach_ratios = [reach_pairs[pair]["base"] / reach_pairs[pair]["thp"] for pair in range(1, 13)]
    shootdown_ratios = [shootdown_pairs[pair]["16"] / shootdown_pairs[pair]["1"] for pair in range(1, 13)]
    print(
        "replication=fresh_process paired_interval=exact_96.1_percent_median_order_statistic "
        "interval_assumptions=iid_continuous_pair_ratios"
    )
    describe("reach base ns_per_access", reach_values["base"])
    describe("reach thp ns_per_access", reach_values["thp"])
    describe_ratios("reach paired base/thp", reach_ratios)
    describe("shootdown readers=1 ns_per_pair", shootdown_values["1"])
    describe("shootdown readers=16 ns_per_pair", shootdown_values["16"])
    describe_ratios("shootdown paired readers16/readers1", shootdown_ratios)


if __name__ == "__main__":
    main()
