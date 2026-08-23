#!/usr/bin/env python3
"""Validate process records and compute fixed paired log-ratio intervals."""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, NoReturn

AA_BLOCKS = 8
TIMING_BLOCKS = 24
MODES = ("plain", "mask", "barrier")
PERMUTATIONS = (
    ("plain", "mask", "barrier"),
    ("plain", "barrier", "mask"),
    ("mask", "plain", "barrier"),
    ("mask", "barrier", "plain"),
    ("barrier", "plain", "mask"),
    ("barrier", "mask", "plain"),
)
PERMUTATION_SET = set(PERMUTATIONS)
T_975 = {7: 2.364624251, 23: 2.06865761}
WARMUP_ITERATIONS = 200_000
WORKLOAD_SEED = 0x243F_6A88_85A3_08D3
SCHEDULE_SEED = 0x43_2026_08_22


def fixed_schedule() -> list[tuple[str, str, str]]:
    """Reconstruct the exact committed 24-block schedule."""

    schedule = list(PERMUTATIONS) * 4
    random.Random(SCHEDULE_SEED).shuffle(schedule)
    return schedule


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                fail(f"{path}:{line_number}: invalid JSON: {error}")
            if not isinstance(row, dict):
                fail(f"{path}:{line_number}: record must be an object")
            rows.append(row)
    return rows


def result(row: dict[str, Any], seed_field: str) -> dict[str, Any]:
    if row.get("exit_code") != 0 or row.get("valid") is not True:
        fail(
            f"block {row.get('block')} ordinal {row.get('ordinal')} retained "
            "a failed process"
        )
    value = row.get("result")
    if not isinstance(value, dict):
        fail("valid record lacks a result object")
    # The retained stdout is the process's original output; the parsed result
    # must re-derive from it so an edited result field cannot contradict the
    # raw evidence the record carries.
    stdout = row.get("stdout")
    if not isinstance(stdout, str):
        fail("process record lacks retained stdout")
    stdout_lines = [line for line in stdout.splitlines() if line.strip()]
    if len(stdout_lines) != 1:
        fail("retained stdout must contain exactly one result line")
    try:
        reparsed = json.loads(stdout_lines[0])
    except json.JSONDecodeError:
        fail("retained stdout is not valid JSON")
    if reparsed != value:
        fail("result differs from the retained process stdout")
    # Checksums are XOR/sum accumulators, so zero is a legitimate value;
    # counts and durations must stay strictly positive. Booleans are excluded
    # everywhere because bool is an int subclass and true would pass as 1.
    for key in (
        "iterations",
        "warmup_iterations",
        "timed_ns",
        "warmup_ns",
    ):
        if not isinstance(value.get(key), int) or isinstance(value.get(key), bool) or value[key] <= 0:
            fail(f"result field {key} must be a positive integer")
    for key in ("warmup_checksum", "checksum"):
        if not isinstance(value.get(key), int) or isinstance(value.get(key), bool) or value[key] < 0:
            fail(f"result field {key} must be a nonnegative integer")
    # Each phase names its seed field; a stray second seed field would let
    # the validated field and the field the checks read disagree.
    other_seed_field = "workload_seed" if seed_field == "seed" else "seed"
    if other_seed_field in row:
        fail(f"record carries a contradictory {other_seed_field} field")
    seed = row.get(seed_field)
    if not isinstance(seed, int) or isinstance(seed, bool):
        fail("process record lacks an integer workload seed")
    if value.get("mode") != row.get("mode"):
        fail("result mode differs from its process record")
    if value.get("iterations") != row.get("iterations"):
        fail("result iteration count differs from its process record")
    if value.get("seed") != seed:
        fail("result seed differs from its process record")
    if value.get("warmup_iterations") != WARMUP_ITERATIONS:
        fail("warmup stopping rule changed")
    command = row.get("command")
    if not isinstance(command, list) or len(command) != 10:
        fail("process command changed shape")
    cpu = row.get("cpu")
    if not isinstance(cpu, int) or isinstance(cpu, bool) or cpu < 0:
        fail("process record must pin a nonnegative integer CPU")
    if command[:2] != ["taskset", "--cpu-list"] or command[2] != str(cpu):
        fail("process command does not pin the recorded CPU")
    expected_flags = [
        "--mode",
        str(row.get("mode")),
        "--iterations",
        str(row.get("iterations")),
        "--seed",
        hex(seed),
    ]
    if command[4:] != expected_flags:
        fail("process command flags differ from the fixed record")
    return value


def interval(log_ratios: list[float]) -> dict[str, float | int | str]:
    count = len(log_ratios)
    mean = statistics.fmean(log_ratios)
    sample_sd = statistics.stdev(log_ratios)
    standard_error = sample_sd / math.sqrt(count)
    critical = T_975[count - 1]
    half_width = critical * standard_error
    return {
        "blocks": count,
        "mean_log_ratio": mean,
        "geometric_mean_ratio": math.exp(mean),
        "sample_sd_log_ratio": sample_sd,
        "standard_error_log_ratio": standard_error,
        "t_critical_975": critical,
        "ci95_low": math.exp(mean - half_width),
        "ci95_high": math.exp(mean + half_width),
        "interval_scope": "between-block variation in paired fresh-process log elapsed-time ratios",
    }


def analyze_aa(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != AA_BLOCKS * 2:
        fail(f"A/A needs {AA_BLOCKS * 2} process records, found {len(rows)}")
    by_block: dict[int, dict[str, float]] = defaultdict(dict)
    checksums: set[int] = set()
    warmup_checksums: set[int] = set()
    iteration_counts: set[int] = set()
    cpus: set[int] = set()
    for row in rows:
        block = row.get("block")
        label = row.get("label")
        ordinal = row.get("ordinal")
        if not isinstance(block, int) or block not in range(1, AA_BLOCKS + 1):
            fail("A/A block is outside the fixed horizon")
        if label not in ("a", "b") or ordinal not in (1, 2):
            fail("A/A label or ordinal is invalid")
        expected = ("a", "b") if block % 2 else ("b", "a")
        if expected[ordinal - 1] != label:
            fail(f"A/A block {block} violates the alternating order")
        if row.get("seed") != WORKLOAD_SEED:
            fail("A/A workload seed changed")
        if label in by_block[block]:
            fail(f"A/A block {block} repeats label {label}")
        value = result(row, "seed")
        if value.get("mode") != "plain":
            fail("A/A labels must both execute plain mode")
        by_block[block][label] = float(value["timed_ns"])
        checksums.add(value["checksum"])
        warmup_checksums.add(value["warmup_checksum"])
        iteration_counts.add(value["iterations"])
        cpus.add(row["cpu"])
    if len(checksums) != 1:
        fail("A/A checksums differ")
    if len(warmup_checksums) != 1:
        fail("A/A warmup checksums differ")
    if len(iteration_counts) != 1:
        fail("A/A iteration counts differ")
    if len(cpus) != 1:
        fail("A/A processes must pin exactly one CPU")
    ratios = []
    for block in range(1, AA_BLOCKS + 1):
        if set(by_block[block]) != {"a", "b"}:
            fail(f"A/A block {block} is incomplete")
        ratios.append(math.log(by_block[block]["b"] / by_block[block]["a"]))
    summary = interval(ratios)
    summary["screen_limit_ratio"] = math.exp(0.10)
    summary["screen_pass"] = abs(float(summary["mean_log_ratio"])) <= 0.10
    return {
        "schema": "topic43-aa-v1",
        "status": "pass" if summary["screen_pass"] else "fail",
        "comparison": "plain-label-b/plain-label-a",
        "summary": summary,
        "security_claim": "none",
    }


def analyze_timing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != TIMING_BLOCKS * len(MODES):
        fail(f"timing needs {TIMING_BLOCKS * len(MODES)} records, found {len(rows)}")
    by_block: dict[int, dict[str, float]] = defaultdict(dict)
    seen_permutations: Counter[tuple[str, ...]] = Counter()
    positions: Counter[tuple[str, int]] = Counter()
    checksums: set[int] = set()
    warmup_checksums: set[int] = set()
    iteration_counts: set[int] = set()
    cpus: set[int] = set()
    schedule = fixed_schedule()
    for row in rows:
        block = row.get("block")
        mode = row.get("mode")
        ordinal = row.get("ordinal")
        permutation_raw = row.get("permutation")
        if not isinstance(block, int) or block not in range(1, TIMING_BLOCKS + 1):
            fail("timing block is outside the fixed horizon")
        if mode not in MODES or ordinal not in (1, 2, 3):
            fail("timing mode or ordinal is invalid")
        if not isinstance(permutation_raw, list):
            fail("timing permutation must be a list")
        permutation = tuple(permutation_raw)
        if permutation not in PERMUTATION_SET or permutation[ordinal - 1] != mode:
            fail(f"timing block {block} has an invalid permutation")
        if row.get("workload_seed") != WORKLOAD_SEED:
            fail("timing workload seed changed")
        if row.get("schedule_seed") != SCHEDULE_SEED:
            fail("timing schedule seed changed")
        if permutation != schedule[block - 1]:
            fail(f"timing block {block} differs from the fixed schedule")
        if mode in by_block[block]:
            fail(f"timing block {block} repeats mode {mode}")
        value = result(row, "workload_seed")
        if value.get("mode") != mode:
            fail("record mode and probe mode differ")
        by_block[block][mode] = float(value["timed_ns"])
        positions[(mode, ordinal)] += 1
        checksums.add(value["checksum"])
        warmup_checksums.add(value["warmup_checksum"])
        iteration_counts.add(value["iterations"])
        cpus.add(row["cpu"])
        if ordinal == 1:
            seen_permutations[permutation] += 1
    if len(checksums) != 1:
        fail("mode checksums differ")
    if len(warmup_checksums) != 1:
        fail("mode warmup checksums differ")
    if len(iteration_counts) != 1:
        fail("mode iteration counts differ")
    if len(cpus) != 1:
        fail("timing processes must pin exactly one CPU")
    if set(seen_permutations) != PERMUTATION_SET or set(seen_permutations.values()) != {4}:
        fail("each of the six permutations must occur four times")
    for mode in MODES:
        for ordinal in (1, 2, 3):
            if positions[(mode, ordinal)] != 8:
                fail(f"{mode} must occupy ordinal {ordinal} eight times")
    comparisons: dict[str, Any] = {}
    for numerator in ("mask", "barrier"):
        ratios = []
        for block in range(1, TIMING_BLOCKS + 1):
            if set(by_block[block]) != set(MODES):
                fail(f"timing block {block} is incomplete")
            ratios.append(math.log(by_block[block][numerator] / by_block[block]["plain"]))
        comparisons[f"{numerator}/plain"] = interval(ratios)
    # Reported per-mode central statistics derive from the same retained rows
    # as the paired ratios, so published tables are recomputable and validated.
    # Durations normalize to nanoseconds per lookup, matching the reports.
    iterations = next(iter(iteration_counts))
    per_mode: dict[str, Any] = {}
    for mode in MODES:
        logs = [
            math.log(by_block[block][mode] / iterations)
            for block in range(1, TIMING_BLOCKS + 1)
        ]
        per_mode[mode] = {
            "processes": len(logs),
            "geometric_mean_ns_per_iteration": math.exp(statistics.fmean(logs)),
            "sample_sd_log_ns_per_iteration": statistics.stdev(logs),
        }
    return {
        "schema": "topic43-timing-v2",
        "status": "pass",
        "blocks": TIMING_BLOCKS,
        "processes": len(rows),
        "permutation_count": 6,
        "permutation_replications": 4,
        "ordinal_count_per_mode": 8,
        "comparisons": comparisons,
        "per_mode": per_mode,
        "security_claim": "none",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("aa", "timing"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = load_rows(args.input)
    summary = analyze_aa(rows) if args.kind == "aa" else analyze_timing(rows)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if summary["status"] != "pass":
        raise SystemExit("screen failed; inspect the retained records and summary")


if __name__ == "__main__":
    main()
