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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def calibration(path: Path) -> dict[tuple[str, str, str], int]:
    with path.open(encoding="utf-8", newline="") as source:
        return {
            (row["method"], row["case"], row["mode"]): int(row["reps"])
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
                blocks = sorted({int(row["block"]) for row in selected})
                contrasts = []
                for block in blocks:
                    cells = sorted(
                        [row for row in selected if int(row["block"]) == block],
                        key=lambda row: int(row["period"]),
                    )
                    if len(cells) != 4:
                        raise ValueError(f"incomplete block {family}/{block}/{case}/{mode}")
                    if [int(row["period"]) for row in cells] != [1, 2, 3, 4]:
                        raise ValueError(f"invalid periods {family}/{block}")
                    labels = "".join(str(row["label"]) for row in cells)
                    if labels not in ("ABBA", "BAAB"):
                        raise ValueError(f"invalid template {labels}")
                    a_logs = [math.log(float(row["ns_per_search"])) for row in cells if row["label"] == "A"]
                    b_logs = [math.log(float(row["ns_per_search"])) for row in cells if row["label"] == "B"]
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


def receipts(
    root: Path,
    processes: list[dict[str, Any]],
    rows_by_sequence: dict[int, list[dict[str, Any]]],
) -> None:
    """Check the per-process receipt files against the aggregate records."""
    attempts_root = root / "attempts"
    attempt_directories = sorted(entry.name for entry in attempts_root.iterdir())
    if attempt_directories != [f"{int(record['sequence']):04d}" for record in processes]:
        raise ValueError("attempt directories do not match the retained processes")
    for record in processes:
        sequence = int(record["sequence"])
        attempt = attempts_root / f"{sequence:04d}"
        stdout_text = (attempt / "stdout.jsonl").read_text(encoding="utf-8")
        stderr_text = (attempt / "stderr.txt").read_text(encoding="utf-8")
        if hashlib.sha256(stdout_text.encode()).hexdigest() != record["stdout_sha256"]:
            raise ValueError(f"stdout digest mismatch for sequence {sequence}")
        if hashlib.sha256(stderr_text.encode()).hexdigest() != record["stderr_sha256"]:
            raise ValueError(f"stderr digest mismatch for sequence {sequence}")
        receipt_rows = [json.loads(line) for line in stdout_text.splitlines() if line.strip()]
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
        if int(record["pid"]) not in {int(row["pid"]) for row in receipt_rows}:
            raise ValueError(f"receipt PID mismatch for sequence {sequence}")


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def validate(root: Path) -> None:
    metadata = json.loads((root / "run_metadata.json").read_text(encoding="utf-8"))
    schedule = json.loads((root / "schedule.json").read_text(encoding="utf-8"))
    processes = load_jsonl(root / "processes.jsonl")
    rows = load_jsonl(root / "raw_rows.jsonl")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    repetitions = calibration(root / "calibration.tsv")

    expected_processes = 2 * int(metadata["blocks"]) * 4 + int(metadata["aa_blocks"]) * 4
    if len(schedule) != expected_processes or len(processes) != expected_processes:
        raise ValueError("schedule/process count mismatch")
    if len(rows) != expected_processes * len(CASES) * len(MODES):
        raise ValueError("raw row count mismatch")
    if [int(item["sequence"]) for item in schedule] != list(range(expected_processes)):
        raise ValueError("schedule sequence is not contiguous")
    schedule_by_sequence = {int(item["sequence"]): item for item in schedule}
    if len(schedule_by_sequence) != expected_processes:
        raise ValueError("duplicate schedule sequence")
    rebuilt = expected_schedule(
        int(metadata["blocks"]), int(metadata["aa_blocks"]), int(metadata["seed"])
    )
    if len(rebuilt) != len(schedule):
        raise ValueError("reconstructed schedule length mismatch")
    for expected_item, recorded_item in zip(rebuilt, schedule):
        if expected_item != recorded_item:
            raise ValueError(
                f"schedule does not match the recorded seed at sequence {expected_item['sequence']}"
            )

    pids = [int(record["pid"]) for record in processes]
    if len(pids) != len(set(pids)):
        raise ValueError("fresh-process PID reuse detected")
    if [int(record["sequence"]) for record in processes] != list(range(expected_processes)):
        raise ValueError("process sequence is not contiguous")
    for process_record in processes:
        if int(process_record["exit_code"]) != 0:
            raise ValueError("a retained process failed")
        scheduled = schedule_by_sequence[int(process_record["sequence"])]
        for field in ("family", "block", "period", "template", "label", "actual_method"):
            if process_record[field] != scheduled[field]:
                raise ValueError(f"process schedule field mismatch: {field}")

    rows_by_sequence: dict[int, list[dict[str, Any]]] = {}
    case_inputs: dict[str, int] = {}
    case_results: dict[str, Any] = {}
    output_checksums: dict[tuple[str, str, str], int] = {}
    for row in rows:
        sequence = int(row["sequence"])
        rows_by_sequence.setdefault(sequence, []).append(row)
        scheduled = schedule_by_sequence[sequence]
        actual = str(scheduled["actual_method"])
        if row["actual_method"] != actual or row["method"] != actual:
            raise ValueError("actual method mismatch")
        for field in ("family", "block", "period", "template", "label", "candidate"):
            if row[field] != scheduled[field]:
                raise ValueError(f"raw schedule field mismatch: {field}")
        key = (actual, str(row["case"]), str(row["mode"]))
        if int(row["reps"]) != repetitions[key]:
            raise ValueError(f"calibration mismatch for {key}")
        if int(row["elapsed_ns"]) <= 0 or float(row["ns_per_search"]) <= 0:
            raise ValueError("non-positive elapsed time")
        computed = int(row["elapsed_ns"]) / int(row["reps"])
        if not math.isclose(float(row["ns_per_search"]), computed, rel_tol=1e-8, abs_tol=1e-6):
            raise ValueError("ns/search does not match elapsed/repetitions")
        logical_gib_per_s = (
            int(row["logical_bytes_per_search"])
            / float(row["ns_per_search"])
            * 1_000_000_000.0
            / (1 << 30)
        )
        if not math.isclose(
            float(row["logical_gib_per_s"]), logical_gib_per_s, rel_tol=1e-8, abs_tol=1e-9
        ):
            raise ValueError("logical throughput does not match bytes and elapsed time")
        case = str(row["case"])
        input_checksum = int(row["input_checksum"])
        if case_inputs.setdefault(case, input_checksum) != input_checksum:
            raise ValueError(f"input checksum mismatch for {case}")
        result = row["result"]
        if case_results.setdefault(case, result) != result:
            raise ValueError(f"result mismatch for {case}")
        checksum_key = (actual, case, str(row["mode"]))
        checksum = int(row["checksum"])
        if output_checksums.setdefault(checksum_key, checksum) != checksum:
            raise ValueError(f"output checksum mismatch for {checksum_key}")

    for sequence, process_rows in rows_by_sequence.items():
        if len(process_rows) != len(CASES) * len(MODES):
            raise ValueError(f"sequence {sequence} has incomplete cells")
        cells = {(row["case"], row["mode"]) for row in process_rows}
        if cells != {(case, mode) for case in CASES for mode in MODES}:
            raise ValueError(f"sequence {sequence} has duplicate or missing cells")
        if {int(row["pid"]) for row in process_rows} != {
            int(processes[sequence]["pid"])
        }:
            raise ValueError(f"sequence {sequence} PID mismatch")

    receipts(root, processes, rows_by_sequence)

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
            if not close(float(left[field]), float(right[field])):
                raise ValueError(f"analysis value mismatch: {field}")
        if len(left["log_contrasts"]) != len(right["log_contrasts"]):
            raise ValueError("contrast count mismatch")
        if not all(
            close(float(a), float(b))
            for a, b in zip(left["log_contrasts"], right["log_contrasts"])
        ):
            raise ValueError("block contrast mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate(args.output.resolve(strict=True))
    metadata = json.loads((args.output / "run_metadata.json").read_text(encoding="utf-8"))
    print(
        "CHECK=PASS "
        f"blocks={metadata['blocks']} aa_blocks={metadata['aa_blocks']} "
        f"seed={metadata['seed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
