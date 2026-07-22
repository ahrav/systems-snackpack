#!/usr/bin/env python3
"""Validate the ABBA process log and summarize retained timer samples."""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import sys
from pathlib import Path

BATCHES = (1, 16, 256, 65_536)
ORDERS = ("raw-first", "clock-first")
PROCESS_COUNT = 12
EXPECTED_ORDERS = (
    "raw-first",
    "clock-first",
    "clock-first",
    "raw-first",
    "raw-first",
    "clock-first",
    "clock-first",
    "raw-first",
    "raw-first",
    "clock-first",
    "clock-first",
    "raw-first",
)


def fields(line: str) -> dict[str, str]:
    return dict(token.split("=", 1) for token in line.split()[1:] if "=" in token)


def integer(record: dict[str, str], name: str, minimum: int = 0) -> int:
    try:
        value = int(record[name])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid or missing integer field {name}") from error
    if value < minimum:
        raise SystemExit(f"field {name} must be at least {minimum}")
    return value


def number(record: dict[str, str], name: str) -> float:
    try:
        value = float(record[name])
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid or missing numeric field {name}") from error
    if not math.isfinite(value):
        raise SystemExit(f"field {name} must be finite")
    return value


def series(record: dict[str, str], name: str, expected: int) -> list[int]:
    try:
        values = [int(value) for value in record[name].split(",")]
    except (KeyError, ValueError) as error:
        raise SystemExit(f"invalid or missing integer series {name}") from error
    if len(values) != expected or any(value < 0 for value in values):
        raise SystemExit(f"series {name} has the wrong length or a negative value")
    return values


def integer_median_x2(values: list[int]) -> int:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return 2 * ordered[middle]
    return ordered[middle - 1] + ordered[middle]


def median_absolute_deviation(values: list[float]) -> float:
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def describe(name: str, values: list[float], unit: str) -> str:
    return (
        f"{name}_median={statistics.median(values):.9f}{unit} "
        f"{name}_mad={median_absolute_deviation(values):.9f}{unit} "
        f"{name}_range=[{min(values):.9f},{max(values):.9f}]{unit}"
    )


def locate_bench(name: str, package: str) -> None:
    executables: list[str] = []
    for line in sys.stdin:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        target = record.get("target", {})
        executable = record.get("executable")
        package_id = str(record.get("package_id", ""))
        if (
            record.get("reason") == "compiler-artifact"
            and target.get("name") == name
            and "bench" in target.get("kind", [])
            and package in package_id
            and executable
        ):
            executables.append(executable)
    unique = sorted(set(executables))
    if len(unique) != 1:
        raise SystemExit(f"cargo JSON contained {len(unique)} executables for {package}/{name}")
    executable_path = Path(unique[0])
    if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
        raise SystemExit(f"Cargo-selected benchmark is not an executable file: {executable_path}")
    print(executable_path)


def require_prefix(lines: list[str], cursor: int, prefix: str) -> tuple[dict[str, str], int]:
    if cursor >= len(lines) or not lines[cursor].startswith(prefix):
        observed = "end of file" if cursor >= len(lines) else lines[cursor]
        raise SystemExit(f"expected {prefix.strip()} at record {cursor + 1}, observed {observed!r}")
    return fields(lines[cursor]), cursor + 1


def validate_sequence(
    lines: list[str],
) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, str],
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    cursor = 0
    session, cursor = require_prefix(lines, cursor, "SESSION_START ")
    artifact, cursor = require_prefix(lines, cursor, "ARTIFACT ")
    counter_probe, cursor = require_prefix(lines, cursor, "PROBE_COUNTER ")
    clock_probe, cursor = require_prefix(lines, cursor, "PROBE_CLOCK ")
    runs: list[dict[str, str]] = []
    ends: list[dict[str, str]] = []
    batches: list[dict[str, str]] = []
    sample_records: list[dict[str, str]] = []

    for expected_index, expected_order in enumerate(EXPECTED_ORDERS, start=1):
        process_start, cursor = require_prefix(lines, cursor, "PROCESS_START ")
        if integer(process_start, "index", 1) != expected_index:
            raise SystemExit("PROCESS_START index differs from the recorded schedule")
        if process_start.get("order") != expected_order:
            raise SystemExit("PROCESS_START order differs from the ABBA schedule")

        run, cursor = require_prefix(lines, cursor, "RUN ")
        if run.get("order") != expected_order:
            raise SystemExit("RUN order differs from PROCESS_START")
        pid = integer(run, "pid", 1)
        runs.append(run)

        for expected_batch in BATCHES:
            batch, cursor = require_prefix(lines, cursor, "BATCH ")
            if integer(batch, "pid", 1) != pid:
                raise SystemExit("BATCH PID differs from RUN")
            if integer(batch, "batch", 1) != expected_batch:
                raise SystemExit("BATCH sizes are missing or out of order")
            batches.append(batch)
            sample_record, cursor = require_prefix(lines, cursor, "SAMPLES ")
            if integer(sample_record, "pid", 1) != pid:
                raise SystemExit("SAMPLES PID differs from RUN")
            if integer(sample_record, "batch", 1) != expected_batch:
                raise SystemExit("SAMPLES batch differs from BATCH")
            if sample_record.get("order") != expected_order:
                raise SystemExit("SAMPLES order differs from RUN")
            sample_records.append(sample_record)

        end, cursor = require_prefix(lines, cursor, "END ")
        if integer(end, "pid", 1) != pid:
            raise SystemExit("END PID differs from RUN")
        ends.append(end)

        process_end, cursor = require_prefix(lines, cursor, "PROCESS_END ")
        if integer(process_end, "index", 1) != expected_index:
            raise SystemExit("PROCESS_END index differs from PROCESS_START")
        if process_end.get("order") != expected_order:
            raise SystemExit("PROCESS_END order differs from PROCESS_START")
        # `integer(..., minimum=1)` rejects zero and negative wall times.
        integer(process_end, "external_wall_ns", 1)

    session_end, cursor = require_prefix(lines, cursor, "SESSION_END ")
    if integer(session_end, "processes", 1) != PROCESS_COUNT:
        raise SystemExit("SESSION_END process count differs from the design")
    if cursor != len(lines):
        raise SystemExit("unexpected records follow SESSION_END")
    return session, artifact, counter_probe, clock_probe, runs, ends, batches, sample_records


def summarize(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    (
        session,
        artifact,
        counter_probe,
        clock_probe,
        runs,
        ends,
        batches,
        sample_records,
    ) = validate_sequence(lines)
    if integer(session, "processes", 1) != PROCESS_COUNT:
        raise SystemExit(f"recorded experiment requires {PROCESS_COUNT} processes")
    if integer(session, "cpu") != 0:
        raise SystemExit("recorded experiment requires CPU 0")
    session_samples = integer(session, "samples", 1)
    if session_samples != 500:
        raise SystemExit("recorded experiment requires 500 samples")
    if not re.fullmatch(r"[0-9a-f]{40}", session.get("source_commit", "")):
        raise SystemExit("invalid source commit")
    if not re.fullmatch(r"[0-9a-f]{64}", session.get("source_archive_sha256", "")):
        raise SystemExit("invalid source archive SHA-256")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact.get("benchmark_binary_sha256", "")):
        raise SystemExit("invalid benchmark binary SHA-256")
    for name, probe, minimum_field in (
        ("counter", counter_probe, "min_nonzero_ticks"),
        ("clock", clock_probe, "min_nonzero_ns"),
    ):
        if integer(probe, "start_cpu") != 0 or integer(probe, "end_cpu") != 0:
            raise SystemExit(f"{name} probe did not remain on CPU 0")
        if integer(probe, "backward") != 0:
            raise SystemExit(f"{name} probe observed backward values")
        integer(probe, minimum_field, 1)

    counter_arch = counter_probe.get("arch")
    if counter_arch == "x86_64":
        if counter_probe.get("bracket") != "rdtscp-cpuid":
            raise SystemExit("x86 counter probe did not use the RDTSCP/CPUID boundary")
        if "rdtscp=true" not in counter_probe.get("features", ""):
            raise SystemExit("x86 counter probe omitted RDTSCP feature evidence")
        if integer(counter_probe, "aux_changes") != 0:
            raise SystemExit("x86 counter probe observed a TSC_AUX change")
        if integer(counter_probe, "start_aux") != integer(counter_probe, "end_aux"):
            raise SystemExit("x86 counter probe TSC_AUX endpoints differ")
    elif counter_arch == "aarch64":
        if counter_probe.get("bracket") != "isb-mrs-cntvct-isb":
            raise SystemExit("Arm counter probe did not use the ISB/CNTVCT boundary")
    else:
        raise SystemExit("counter probe reported an unsupported architecture")

    pids = [integer(run, "pid", 1) for run in runs]
    if len(set(pids)) != PROCESS_COUNT:
        raise SystemExit("each process must have a distinct PID")
    if any(integer(run, "samples", 1) != session_samples for run in runs):
        raise SystemExit("RUN sample count differs from SESSION_START")
    if [run.get("order") for run in runs].count(ORDERS[0]) != PROCESS_COUNT // 2:
        raise SystemExit("raw-first stratum is not 6/6 balanced")
    if [run.get("order") for run in runs].count(ORDERS[1]) != PROCESS_COUNT // 2:
        raise SystemExit("clock-first stratum is not 6/6 balanced")

    run_by_pid = {integer(run, "pid", 1): run for run in runs}
    end_by_pid = {integer(end, "pid", 1): end for end in ends}
    for pid, run in run_by_pid.items():
        end = end_by_pid.get(pid)
        if end is None:
            raise SystemExit(f"PID {pid} has no END record")
        if run.get("arch") != counter_arch:
            raise SystemExit(f"PID {pid} architecture differs from the counter probe")
        if run.get("bracket") != counter_probe.get("bracket"):
            raise SystemExit(f"PID {pid} bracket differs from the counter probe")
        if integer(run, "start_cpu") != 0 or integer(end, "end_cpu") != 0:
            raise SystemExit(f"PID {pid} did not start and end on CPU 0")
        if counter_arch == "x86_64":
            if integer(run, "start_aux") != integer(end, "end_aux"):
                raise SystemExit(f"PID {pid} TSC_AUX endpoints differ")
        if integer(end, "rejected_counter") != 0 or integer(end, "rejected_clock") != 0:
            raise SystemExit(f"PID {pid} rejected one or more samples")
        if not re.fullmatch(r"[0-9a-f]{16}", end.get("checksum", "")):
            raise SystemExit(f"PID {pid} has an invalid checksum")
    if len({end["checksum"] for end in ends}) != 1:
        raise SystemExit("process checksums differ")

    by_pid_batch: dict[tuple[int, int], dict[str, str]] = {}
    for record in batches:
        pid = integer(record, "pid", 1)
        batch = integer(record, "batch", 1)
        if pid not in run_by_pid or batch not in BATCHES:
            raise SystemExit("BATCH record has unknown PID or size")
        if record.get("order") != run_by_pid[pid].get("order"):
            raise SystemExit("BATCH order differs from RUN order")
        requested = integer(record, "requested_samples", 1)
        if requested != session_samples:
            raise SystemExit("BATCH sample count differs from SESSION_START")
        if integer(record, "valid_counter") != requested:
            raise SystemExit("counter sample count differs from request")
        if integer(record, "valid_clock") != requested:
            raise SystemExit("clock sample count differs from request")
        if integer(record, "rejected_counter") != 0 or integer(record, "rejected_clock") != 0:
            raise SystemExit("BATCH record contains rejected samples")
        key = (pid, batch)
        if key in by_pid_batch:
            raise SystemExit("duplicate PID/batch record")
        by_pid_batch[key] = record

    by_pid_samples: dict[tuple[int, int], dict[str, str]] = {}
    for record in sample_records:
        key = (integer(record, "pid", 1), integer(record, "batch", 1))
        if key in by_pid_samples or key not in by_pid_batch:
            raise SystemExit("duplicate or unmatched SAMPLES record")
        batch_record = by_pid_batch[key]
        requested = integer(batch_record, "requested_samples", 1)
        counter_values = series(record, "counter_ticks", requested)
        clock_values = series(record, "clock_ns", requested)
        if min(counter_values) != integer(batch_record, "min_ticks"):
            raise SystemExit("raw counter minimum differs from BATCH")
        if integer_median_x2(counter_values) != integer(batch_record, "median_ticks_x2"):
            raise SystemExit("raw counter median differs from BATCH")
        if min(clock_values) != integer(batch_record, "min_ns"):
            raise SystemExit("raw clock minimum differs from BATCH")
        if integer_median_x2(clock_values) != integer(batch_record, "median_ns_x2"):
            raise SystemExit("raw clock median differs from BATCH")
        by_pid_samples[key] = record

    counter_empirical_bound = 200 * integer(counter_probe, "min_nonzero_ticks", 1)
    clock_empirical_bound = 200 * integer(clock_probe, "min_nonzero_ns", 1)
    for run in runs:
        pid = integer(run, "pid", 1)
        largest = by_pid_batch[(pid, BATCHES[-1])]
        if integer(largest, "median_ticks_x2", 1) < 2 * counter_empirical_bound:
            raise SystemExit("largest counter batch misses the empirical granularity guard")
        if integer(largest, "median_ns_x2", 1) < 2 * clock_empirical_bound:
            raise SystemExit("largest clock batch misses the empirical granularity guard")

    print(
        "replication=12_fresh_processes "
        "orders=6_raw-first_and_6_clock-first cpu=0 "
        f"samples_per_timer_per_batch={session_samples}"
    )
    print(f"benchmark_binary_sha256={artifact['benchmark_binary_sha256']}")
    print(
        "empirical_granularity_guard=largest_batch_at_least_200x_minimum_observed_read_delta "
        f"counter_threshold_ticks={counter_empirical_bound} "
        f"clock_threshold_ns={clock_empirical_bound}"
    )
    frequencies = [integer(run, "frequency_hz", 1) for run in runs]
    print(describe("frequency_hz", [float(value) for value in frequencies], "Hz"))

    for batch in BATCHES:
        reference_ns: list[float] = []
        clock_ns: list[float] = []
        ratios: list[float] = []
        order_reference: dict[str, list[float]] = {order: [] for order in ORDERS}
        order_clock: dict[str, list[float]] = {order: [] for order in ORDERS}
        for run in runs:
            pid = integer(run, "pid", 1)
            record = by_pid_batch[(pid, batch)]
            frequency = integer(run, "frequency_hz", 1)
            median_ticks_x2 = integer(record, "median_ticks_x2", 1)
            median_ns_x2 = integer(record, "median_ns_x2", 1)
            min_ticks = integer(record, "min_ticks")
            min_ns = integer(record, "min_ns")
            reported_min_ticks_per_op = number(record, "min_ticks_per_op")
            reported_min_ns_per_op = number(record, "min_ns_per_op")
            reported_ticks_per_op = number(record, "median_ticks_per_op")
            reported_ns_per_op = number(record, "median_ns_per_op")
            derived_min_ticks_per_op = min_ticks / batch
            derived_min_ns_per_op = min_ns / batch
            derived_ticks_per_op = median_ticks_x2 / (2 * batch)
            derived_ns_per_op = median_ns_x2 / (2 * batch)
            if not math.isclose(
                reported_min_ticks_per_op,
                derived_min_ticks_per_op,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise SystemExit("reported min_ticks_per_op differs from integer fields")
            if not math.isclose(
                reported_min_ns_per_op,
                derived_min_ns_per_op,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise SystemExit("reported min_ns_per_op differs from integer fields")
            if not math.isclose(
                reported_ticks_per_op,
                derived_ticks_per_op,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise SystemExit("reported median_ticks_per_op differs from integer fields")
            if not math.isclose(
                reported_ns_per_op,
                derived_ns_per_op,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise SystemExit("reported median_ns_per_op differs from integer fields")
            ref_value = derived_ticks_per_op * 1_000_000_000 / frequency
            clock_value = derived_ns_per_op
            reference_ns.append(ref_value)
            clock_ns.append(clock_value)
            ratios.append(ref_value / clock_value)
            order = run["order"]
            order_reference[order].append(ref_value)
            order_clock[order].append(clock_value)
        print(f"batch={batch}")
        print(describe("reference", reference_ns, "ns/op"))
        print(describe("clock", clock_ns, "ns/op"))
        print(describe("reference_clock_ratio", ratios, "x"))
        for order in ORDERS:
            print(
                f"order={order} "
                f"reference_median={statistics.median(order_reference[order]):.9f}ns/op "
                f"clock_median={statistics.median(order_clock[order]):.9f}ns/op"
            )


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "--locate-bench":
        locate_bench(args[1], args[2])
    elif len(args) == 1:
        summarize(Path(args[0]))
    else:
        raise SystemExit(
            "usage: summarize.py --locate-bench NAME PACKAGE | summarize.py PROCESSES"
        )


if __name__ == "__main__":
    main()
