#!/usr/bin/env python3
"""Independently validate Topic 34 process receipts and block contrasts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any

CASES = (
    "uniform_absent_32",
    "text_late_16",
    "prefix_trap_32",
    "suffix_trap_32",
    "tiny_late_4",
)
MODES = ("reuse", "one_shot")


def as_int(value: Any, label: str = "integer field") -> int:
    """Coerce a recorded value, naming the field when the evidence is malformed."""
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {label}: {value!r}") from error


def as_float(value: Any, label: str = "numeric field") -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {label}: {value!r}") from error


def parse_json(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except ValueError as error:
        raise ValueError(f"invalid JSON in {label}: {error}") from error


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"unreadable evidence file {path}: {error}") from error


def read_json(path: Path) -> Any:
    return parse_json(read_text_file(path), str(path))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [parse_json(line, str(path)) for line in read_text_file(path).splitlines() if line]


def calibration(path: Path) -> dict[tuple[str, str, str], int]:
    with path.open(encoding="utf-8", newline="") as source:
        return {
            (row["method"], row["case"], row["mode"]): as_int(row["reps"])
            for row in csv.DictReader(source, delimiter="\t")
        }


def recompute(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for family in sorted({str(row["family"]) for row in rows}):
        for case in CASES:
            for mode in MODES:
                selected = [
                    row
                    for row in rows
                    if row["family"] == family and row["case"] == case and row["mode"] == mode
                ]
                blocks = sorted({as_int(row["block"]) for row in selected})
                contrasts = []
                for block in blocks:
                    cells = sorted(
                        [row for row in selected if as_int(row["block"]) == block],
                        key=lambda row: as_int(row["period"]),
                    )
                    if len(cells) != 4:
                        raise ValueError(f"incomplete block {family}/{block}/{case}/{mode}")
                    if [as_int(row["period"]) for row in cells] != [1, 2, 3, 4]:
                        raise ValueError(f"invalid periods {family}/{block}")
                    labels = "".join(str(row["label"]) for row in cells)
                    if labels not in ("ABBA", "BAAB"):
                        raise ValueError(f"invalid template {labels}")
                    a_logs = [math.log(as_float(row["ns_per_search"])) for row in cells if row["label"] == "A"]
                    b_logs = [math.log(as_float(row["ns_per_search"])) for row in cells if row["label"] == "B"]
                    contrasts.append(statistics.fmean(b_logs) - statistics.fmean(a_logs))
                mean_log = statistics.fmean(contrasts)
                result.append(
                    {
                        "family": family,
                        "case": case,
                        "mode": mode,
                        "n_complete_blocks": len(contrasts),
                        "log_contrasts": contrasts,
                        "mean_log_ratio": mean_log,
                        "geometric_mean_ratio": math.exp(mean_log),
                        "sample_sd_log_ratio": statistics.stdev(contrasts),
                    }
                )
    return result


def expected_schedule(blocks: int, aa_blocks: int, seed: int) -> list[dict[str, Any]]:
    """Rebuild the deterministic schedule from the recorded design and seed."""

    def balanced(count: int, rng: random.Random) -> list[str]:
        templates = ["ABBA"] * (count // 2) + ["BAAB"] * (count // 2)
        rng.shuffle(templates)
        return templates

    cell_count = len(CASES) * len(MODES)
    rng = random.Random(seed)
    families = (
        ("left-to-right_vs_kmp", "kmp"),
        ("left-to-right_vs_horspool", "horspool"),
    )
    family_templates = {name: balanced(blocks, rng) for name, _ in families}
    first_family = rng.randrange(2)
    schedule: list[dict[str, Any]] = []

    def emit(family: str, candidate: str, block: int, template: str, baseline: str) -> None:
        for period, label in enumerate(template, start=1):
            schedule.append(
                {
                    "sequence": len(schedule),
                    "family": family,
                    "candidate": candidate,
                    "block": block,
                    "period": period,
                    "template": template,
                    "label": label,
                    "actual_method": baseline if label == "A" else candidate,
                    "cell_rotation": block % cell_count,
                }
            )

    for block in range(blocks):
        order = list(families)
        if (block + first_family) % 2:
            order.reverse()
        for family, candidate in order:
            emit(family, candidate, block, family_templates[family][block], "left-to-right")
    for block, template in enumerate(balanced(aa_blocks, rng)):
        emit("left-to-right_AA", "left-to-right", block, template, "left-to-right")
    return schedule


ENRICHED_FIELDS = (
    "block",
    "candidate",
    "family",
    "label",
    "period",
    "sequence",
    "template",
)


MASK64 = (1 << 64) - 1
METHODS = ("left-to-right", "kmp", "horspool")


def fnv1a(data: bytes) -> int:
    digest = 0xCBF29CE484222325
    for byte in data:
        digest = ((digest ^ byte) * 0x00000100000001B3) & MASK64
    return digest


def rotate_left(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (64 - bits))) & MASK64


def benchmark_cases() -> dict[str, tuple[bytes, bytes]]:
    """Rebuild the probe's deterministic corpora from their source definitions."""
    state = 0x9E3779B97F4A7C15
    uniform = bytearray(1 << 20)
    for index in range(len(uniform)):
        state = (state ^ (state << 13)) & MASK64
        state ^= state >> 7
        state = (state ^ (state << 17)) & MASK64
        uniform[index] = (state % 255) & 0xFF

    phrase = b"the quick brown fox moves through a small systems workload. "
    text = bytearray()
    while len(text) + len(phrase) <= (1 << 20) - 16:
        text += phrase
    text += b" " * ((1 << 20) - 16 - len(text))
    text_needle = b"the ~late match!"
    text += text_needle

    prefix_needle = bytearray(b"a" * 32)
    prefix_needle[31] = ord("b")
    suffix_needle = bytearray(b"a" * 32)
    suffix_needle[0] = ord("b")
    tiny = bytearray(b"x" * 4096)
    tiny_needle = b"q7!z"
    tiny[4092:] = tiny_needle

    return {
        "uniform_absent_32": (bytes(uniform), b"\xff" * 32),
        "text_late_16": (bytes(text), text_needle),
        "prefix_trap_32": (b"a" * (128 << 10), bytes(prefix_needle)),
        "suffix_trap_32": (b"a" * (128 << 10), bytes(suffix_needle)),
        "tiny_late_4": (bytes(tiny), tiny_needle),
    }


def folded_checksum(result: int | None, repetitions: int) -> int:
    value = MASK64 if result is None else result
    folded = 0
    for iteration in range(repetitions):
        folded = rotate_left(folded, 7) ^ ((value + iteration * 0x9E3779B9) & MASK64)
    return folded


def calibration_attempts(
    path: Path, binary: str, target_ms: int, repetitions: dict[tuple[str, str, str], int]
) -> None:
    """Check that every frozen repetition count came from a recorded calibration."""
    attempts = read_json(path)
    expected_keys = [
        (method, case, mode) for method in METHODS for case in CASES for mode in MODES
    ]
    if [(a["method"], a["case"], a["mode"]) for a in attempts] != expected_keys:
        raise ValueError("calibration attempts do not cover the method/case/mode grid")
    for attempt in attempts:
        key = (attempt["method"], attempt["case"], attempt["mode"])
        if as_int(attempt["exit_code"]) != 0:
            raise ValueError(f"calibration attempt failed for {key}")
        if attempt["command"] != [binary, "calibrate", *key, str(target_ms)]:
            raise ValueError(f"unexpected calibration command for {key}")
        if as_int(attempt["external_wall_ns"]) <= 0:
            raise ValueError(f"non-positive calibration wall time for {key}")
        reported = [
            line for line in str(attempt["stdout"]).splitlines() if line.startswith("reps=")
        ]
        if len(reported) != 1:
            raise ValueError(f"calibration attempt lacks a single reps line for {key}")
        if as_int(reported[0].split("=", 1)[1]) != repetitions[key]:
            raise ValueError(f"calibration attempt disagrees with calibration.tsv for {key}")


def rotated_cells(block: int) -> list[tuple[str, str]]:
    cells = [(case, mode) for case in CASES for mode in MODES]
    offset = block % len(cells)
    return cells[offset:] + cells[:offset]


def receipts(
    root: Path,
    processes: list[dict[str, Any]],
    rows_by_sequence: dict[int, list[dict[str, Any]]],
    repetitions: dict[tuple[str, str, str], int],
) -> None:
    """Check the per-process receipt files against the aggregate records."""
    attempts_root = root / "attempts"
    attempt_directories = sorted(entry.name for entry in attempts_root.iterdir())
    if attempt_directories != [f"{as_int(record['sequence']):04d}" for record in processes]:
        raise ValueError("attempt directories do not match the retained processes")
    for record in processes:
        sequence = as_int(record["sequence"])
        attempt = attempts_root / f"{sequence:04d}"
        stdout_text = read_text_file(attempt / "stdout.jsonl")
        actual_method = str(record["actual_method"])
        expected_calibration = "\n".join(
            ["method\tcase\tmode\treps"]
            + [
                f"{actual_method}\t{case}\t{mode}\t{repetitions[(actual_method, case, mode)]}"
                for case, mode in rotated_cells(as_int(record["block"]))
            ]
        )
        if read_text_file(attempt / "calibration.tsv") != expected_calibration + "\n":
            raise ValueError(f"calibration receipt mismatch for sequence {sequence}")
        stderr_text = read_text_file(attempt / "stderr.txt")
        if hashlib.sha256(stdout_text.encode()).hexdigest() != record["stdout_sha256"]:
            raise ValueError(f"stdout digest mismatch for sequence {sequence}")
        if hashlib.sha256(stderr_text.encode()).hexdigest() != record["stderr_sha256"]:
            raise ValueError(f"stderr digest mismatch for sequence {sequence}")
        receipt_rows = [parse_json(line, "stdout.jsonl") for line in stdout_text.splitlines() if line.strip()]
        aggregate_rows = rows_by_sequence[sequence]
        if len(receipt_rows) != len(aggregate_rows):
            raise ValueError(f"receipt row count mismatch for sequence {sequence}")
        aggregate_by_cell = {
            (str(row["case"]), str(row["mode"])): row for row in aggregate_rows
        }
        for receipt_row in receipt_rows:
            key = (str(receipt_row["case"]), str(receipt_row["mode"]))
            aggregate_row = aggregate_by_cell.get(key)
            if aggregate_row is None:
                raise ValueError(f"receipt cell absent from aggregate rows: {key}")
            if set(aggregate_row) != set(receipt_row) | set(ENRICHED_FIELDS):
                raise ValueError(f"receipt field set mismatch for sequence {sequence}")
            for field, value in receipt_row.items():
                if aggregate_row[field] != value:
                    raise ValueError(
                        f"receipt value mismatch for sequence {sequence} field {field}"
                    )
        if as_int(record["pid"]) not in {as_int(row["pid"]) for row in receipt_rows}:
            raise ValueError(f"receipt PID mismatch for sequence {sequence}")
        interval_total = sum(as_int(row["elapsed_ns"]) for row in aggregate_rows)
        if as_int(record["external_wall_ns"]) < interval_total or interval_total <= 0:
            raise ValueError(f"external wall time is impossible for sequence {sequence}")


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def validate(root: Path) -> None:
    metadata = read_json(root / "run_metadata.json")
    schedule = read_json(root / "schedule.json")
    processes = load_jsonl(root / "processes.jsonl")
    rows = load_jsonl(root / "raw_rows.jsonl")
    summary = read_json(root / "summary.json")
    repetitions = calibration(root / "calibration.tsv")
    calibration_attempts(
        root / "calibration_attempts.json",
        str(metadata["binary"]),
        as_int(metadata["target_ms"]),
        repetitions,
    )
    corpora = benchmark_cases()
    oracle_results = {
        case: (haystack.find(needle) if needle in haystack else None)
        for case, (haystack, needle) in corpora.items()
    }
    oracle_inputs = {
        case: fnv1a(haystack) ^ rotate_left(fnv1a(needle), 17)
        for case, (haystack, needle) in corpora.items()
    }

    expected_processes = 2 * as_int(metadata["blocks"]) * 4 + as_int(metadata["aa_blocks"]) * 4
    if len(schedule) != expected_processes or len(processes) != expected_processes:
        raise ValueError("schedule/process count mismatch")
    if len(rows) != expected_processes * len(CASES) * len(MODES):
        raise ValueError("raw row count mismatch")
    if [as_int(item["sequence"]) for item in schedule] != list(range(expected_processes)):
        raise ValueError("schedule sequence is not contiguous")
    schedule_by_sequence = {as_int(item["sequence"]): item for item in schedule}
    if len(schedule_by_sequence) != expected_processes:
        raise ValueError("duplicate schedule sequence")
    rebuilt = expected_schedule(
        as_int(metadata["blocks"]), as_int(metadata["aa_blocks"]), as_int(metadata["seed"])
    )
    if len(rebuilt) != len(schedule):
        raise ValueError("reconstructed schedule length mismatch")
    for expected_item, recorded_item in zip(rebuilt, schedule):
        if expected_item != recorded_item:
            raise ValueError(
                f"schedule does not match the recorded seed at sequence {expected_item['sequence']}"
            )

    pids = [as_int(record["pid"]) for record in processes]
    if len(pids) != len(set(pids)):
        raise ValueError("fresh-process PID reuse detected")
    if [as_int(record["sequence"]) for record in processes] != list(range(expected_processes)):
        raise ValueError("process sequence is not contiguous")
    for process_record in processes:
        if as_int(process_record["exit_code"]) != 0:
            raise ValueError("a retained process failed")
        scheduled = schedule_by_sequence[as_int(process_record["sequence"])]
        for field in ("family", "block", "period", "template", "label", "actual_method"):
            if process_record[field] != scheduled[field]:
                raise ValueError(f"process schedule field mismatch: {field}")

    rows_by_sequence: dict[int, list[dict[str, Any]]] = {}
    case_inputs: dict[str, int] = {}
    case_results: dict[str, Any] = {}
    output_checksums: dict[tuple[str, str, str], int] = {}
    for row in rows:
        sequence = as_int(row["sequence"])
        rows_by_sequence.setdefault(sequence, []).append(row)
        scheduled = schedule_by_sequence[sequence]
        actual = str(scheduled["actual_method"])
        if row["actual_method"] != actual or row["method"] != actual:
            raise ValueError("actual method mismatch")
        for field in ("family", "block", "period", "template", "label", "candidate"):
            if row[field] != scheduled[field]:
                raise ValueError(f"raw schedule field mismatch: {field}")
        key = (actual, str(row["case"]), str(row["mode"]))
        if as_int(row["reps"]) != repetitions[key]:
            raise ValueError(f"calibration mismatch for {key}")
        if as_int(row["elapsed_ns"]) <= 0 or as_float(row["ns_per_search"]) <= 0:
            raise ValueError("non-positive elapsed time")
        computed = as_int(row["elapsed_ns"]) / as_int(row["reps"])
        if not math.isclose(as_float(row["ns_per_search"]), computed, rel_tol=1e-8, abs_tol=1e-6):
            raise ValueError("ns/search does not match elapsed/repetitions")
        logical_gib_per_s = (
            as_int(row["logical_bytes_per_search"])
            / as_float(row["ns_per_search"])
            * 1_000_000_000.0
            / (1 << 30)
        )
        if not math.isclose(
            as_float(row["logical_gib_per_s"]), logical_gib_per_s, rel_tol=1e-8, abs_tol=1e-9
        ):
            raise ValueError("logical throughput does not match bytes and elapsed time")
        case = str(row["case"])
        input_checksum = as_int(row["input_checksum"])
        if input_checksum != oracle_inputs[case]:
            raise ValueError(f"input checksum does not match the source corpus for {case}")
        if case_inputs.setdefault(case, input_checksum) != input_checksum:
            raise ValueError(f"input checksum mismatch for {case}")
        result = row["result"]
        if result != oracle_results[case]:
            raise ValueError(f"result does not match the oracle for {case}")
        if case_results.setdefault(case, result) != result:
            raise ValueError(f"result mismatch for {case}")
        checksum_key = (actual, case, str(row["mode"]))
        checksum = as_int(row["checksum"])
        if checksum not in output_checksums.values() or output_checksums.get(checksum_key) is None:
            if checksum != folded_checksum(oracle_results[case], as_int(row["reps"])):
                raise ValueError(f"output checksum does not fold the oracle result for {checksum_key}")
        if output_checksums.setdefault(checksum_key, checksum) != checksum:
            raise ValueError(f"output checksum mismatch for {checksum_key}")

    for sequence, process_rows in rows_by_sequence.items():
        if len(process_rows) != len(CASES) * len(MODES):
            raise ValueError(f"sequence {sequence} has incomplete cells")
        cells = {(row["case"], row["mode"]) for row in process_rows}
        if cells != {(case, mode) for case in CASES for mode in MODES}:
            raise ValueError(f"sequence {sequence} has duplicate or missing cells")
        if {as_int(row["pid"]) for row in process_rows} != {
            as_int(processes[sequence]["pid"])
        }:
            raise ValueError(f"sequence {sequence} PID mismatch")

    receipts(root, processes, rows_by_sequence, repetitions)

    if summary.get("run_metadata") != metadata:
        raise ValueError("summary run_metadata does not match run_metadata.json")

    expected = recompute(rows)
    observed = summary["analyses"]
    if len(expected) != len(observed):
        raise ValueError("analysis row count mismatch")
    for left, right in zip(expected, observed):
        for field in ("family", "case", "mode", "n_complete_blocks"):
            if left[field] != right[field]:
                raise ValueError(f"analysis identity mismatch: {field}")
        for field in (
            "mean_log_ratio",
            "geometric_mean_ratio",
            "sample_sd_log_ratio",
        ):
            if not close(as_float(left[field]), as_float(right[field])):
                raise ValueError(f"analysis value mismatch: {field}")
        if len(left["log_contrasts"]) != len(right["log_contrasts"]):
            raise ValueError("contrast count mismatch")
        if not all(
            close(as_float(a), as_float(b))
            for a, b in zip(left["log_contrasts"], right["log_contrasts"])
        ):
            raise ValueError("block contrast mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.output.resolve(strict=True))
    metadata = read_json(args.output / "run_metadata.json")
    print(
        "CHECK=PASS "
        f"blocks={metadata['blocks']} aa_blocks={metadata['aa_blocks']} "
        f"seed={metadata['seed']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:  # name the rejected evidence before failing closed
        print(f"ERROR={type(error).__name__}: {error}", file=sys.stderr)
        raise
