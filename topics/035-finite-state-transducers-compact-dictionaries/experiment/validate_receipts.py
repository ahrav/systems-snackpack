#!/usr/bin/env python3
"""Independently validate Topic 35 process receipts and block contrasts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any

METHODS = ("flat-trie", "minimal-dafsa")
DATASETS = ("shared", "opaque")
TREATMENT_FAMILY = "flat-trie_vs_minimal-dafsa"
AA_FAMILY = "flat-trie_AA"
EXPECTED_BLOCKS = 12
EXPECTED_AA_BLOCKS = 4
EXPECTED_SEED = 350035
EXPECTED_TARGET_MS = 200
EXPECTED_TOPOLOGY = {
    ("flat-trie", "shared"): {
        "key_count": 65_536,
        "key_bytes": 983_040,
        "query_count": 16_384,
        "hit_count": 8_192,
        "state_count": 790_801,
        "arc_count": 790_800,
        "topology_bytes": 12_652_808,
    },
    ("minimal-dafsa", "shared"): {
        "key_count": 65_536,
        "key_bytes": 983_040,
        "query_count": 16_384,
        "hit_count": 8_192,
        "state_count": 16,
        "arc_count": 75,
        "topology_bytes": 728,
    },
    ("flat-trie", "opaque"): {
        "key_count": 65_536,
        "key_bytes": 1_048_576,
        "query_count": 16_384,
        "hit_count": 8_192,
        "state_count": 959_061,
        "arc_count": 959_060,
        "topology_bytes": 15_344_968,
    },
    ("minimal-dafsa", "opaque"): {
        "key_count": 65_536,
        "key_bytes": 1_048_576,
        "query_count": 16_384,
        "hit_count": 8_192,
        "state_count": 804_065,
        "arc_count": 869_599,
        "topology_bytes": 13_389_312,
    },
}
CORE_FIELDS = (
    "pid",
    "method",
    "actual_method",
    "dataset",
    "reps",
    "elapsed_ns",
    "ns_per_lookup",
    "key_count",
    "key_bytes",
    "query_count",
    "hit_count",
    "state_count",
    "arc_count",
    "topology_bytes",
    "input_checksum",
    "query_checksum",
    "result_checksum",
)
SCHEDULE_FIELDS = (
    "family",
    "candidate",
    "block",
    "period",
    "template",
    "label",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_calibration(path: Path) -> dict[tuple[str, str], int]:
    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    if source_fields := ({"method", "dataset", "reps"} - set(rows[0] if rows else ())):
        raise ValueError(f"calibration is missing columns: {sorted(source_fields)}")
    result: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["method"], row["dataset"])
        if key in result:
            raise ValueError(f"duplicate calibration cell: {key}")
        repetitions = int(row["reps"])
        if repetitions < 1:
            raise ValueError(f"non-positive calibration cell: {key}")
        result[key] = repetitions
    expected = {(method, dataset) for method in METHODS for dataset in DATASETS}
    if set(result) != expected:
        raise ValueError("calibration does not contain the four frozen method/dataset cells")
    return result


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def validate_block_schedule(
    schedule: list[dict[str, Any]], family: str, blocks: int, candidate: str
) -> None:
    selected = [item for item in schedule if item["family"] == family]
    if len(selected) != blocks * 4:
        raise ValueError(f"invalid schedule count for {family}")
    templates: list[str] = []
    for block in range(blocks):
        cells = sorted(
            [item for item in selected if int(item["block"]) == block],
            key=lambda item: int(item["period"]),
        )
        if len(cells) != 4 or [int(item["period"]) for item in cells] != [1, 2, 3, 4]:
            raise ValueError(f"incomplete periods for {family}/{block}")
        template = str(cells[0]["template"])
        labels = "".join(str(item["label"]) for item in cells)
        if template not in ("ABBA", "BAAB") or labels != template:
            raise ValueError(f"invalid block template for {family}/{block}")
        if {str(item["template"]) for item in cells} != {template}:
            raise ValueError(f"template changed inside {family}/{block}")
        if {str(item["candidate"]) for item in cells} != {candidate}:
            raise ValueError(f"candidate changed inside {family}/{block}")
        for item in cells:
            expected_method = (
                "flat-trie" if item["label"] == "A" or family == AA_FAMILY else candidate
            )
            if item["actual_method"] != expected_method:
                raise ValueError(f"label/method mismatch for {family}/{block}")
        templates.append(template)
    if templates.count("ABBA") != blocks // 2 or templates.count("BAAB") != blocks // 2:
        raise ValueError(f"templates are not balanced for {family}")


def recompute(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for family in (TREATMENT_FAMILY, AA_FAMILY):
        for dataset in DATASETS:
            selected = [
                row for row in rows if row["family"] == family and row["dataset"] == dataset
            ]
            blocks = sorted({int(row["block"]) for row in selected})
            contrasts = []
            for block in blocks:
                cells = sorted(
                    [row for row in selected if int(row["block"]) == block],
                    key=lambda row: int(row["period"]),
                )
                if len(cells) != 4:
                    raise ValueError(f"incomplete block {family}/{block}/{dataset}")
                if [int(row["period"]) for row in cells] != [1, 2, 3, 4]:
                    raise ValueError(f"invalid periods {family}/{block}")
                labels = "".join(str(row["label"]) for row in cells)
                if labels not in ("ABBA", "BAAB"):
                    raise ValueError(f"invalid template {labels}")
                a_logs = [
                    math.log(float(row["ns_per_lookup"])) for row in cells if row["label"] == "A"
                ]
                b_logs = [
                    math.log(float(row["ns_per_lookup"])) for row in cells if row["label"] == "B"
                ]
                if len(a_logs) != 2 or len(b_logs) != 2:
                    raise ValueError(f"invalid treatment labels in {family}/{block}")
                contrasts.append(statistics.fmean(b_logs) - statistics.fmean(a_logs))
            expected_blocks = EXPECTED_BLOCKS if family == TREATMENT_FAMILY else EXPECTED_AA_BLOCKS
            if len(contrasts) != expected_blocks:
                raise ValueError(f"wrong complete-block count for {family}/{dataset}")
            mean_log = statistics.fmean(contrasts)
            result.append(
                {
                    "family": family,
                    "dataset": dataset,
                    "n_complete_blocks": len(contrasts),
                    "log_contrasts": contrasts,
                    "mean_log_ratio": mean_log,
                    "geometric_mean_ratio": math.exp(mean_log),
                    "sample_sd_log_ratio": statistics.stdev(contrasts),
                }
            )
    return result


def validate_calibration_attempts(root: Path, repetitions: dict[tuple[str, str], int]) -> None:
    attempts = json.loads((root / "calibration_attempts.json").read_text(encoding="utf-8"))
    if len(attempts) != len(METHODS) * len(DATASETS):
        raise ValueError("calibration attempt count mismatch")
    seen: set[tuple[str, str]] = set()
    for record in attempts:
        key = (str(record["method"]), str(record["dataset"]))
        if key in seen or key not in repetitions:
            raise ValueError(f"invalid calibration attempt: {key}")
        seen.add(key)
        if int(record["exit_code"]) != 0 or int(record["external_wall_ns"]) <= 0:
            raise ValueError(f"failed calibration attempt: {key}")
        if record["timed_out"] or str(record["stderr"]):
            raise ValueError(f"calibration timed out or produced stderr: {key}")
        if int(record["stdout_bytes"]) != len(str(record["stdout"]).encode("utf-8")):
            raise ValueError(f"calibration stdout length mismatch: {key}")
        if record["stdout_sha256"] != sha256_bytes(str(record["stdout"]).encode("utf-8")):
            raise ValueError(f"calibration stdout checksum mismatch: {key}")
        if int(record["stderr_bytes"]) != 0 or record["stderr_sha256"] != sha256_bytes(b""):
            raise ValueError(f"calibration stderr receipt mismatch: {key}")
        lines = [line for line in str(record["stdout"]).splitlines() if line.startswith("reps=")]
        if len(lines) != 1 or int(lines[0].split("=", 1)[1]) != repetitions[key]:
            raise ValueError(f"calibration attempt/TSV mismatch: {key}")
    if seen != set(repetitions):
        raise ValueError("calibration attempts omitted a method/dataset cell")


def validate_attempt(
    root: Path,
    sequence: int,
    process_record: dict[str, Any],
    process_rows: list[dict[str, Any]],
    repetitions: dict[tuple[str, str], int],
) -> None:
    attempt = root / "attempts" / f"{sequence:04d}"
    expected_files = {"calibration.tsv", "stdout.jsonl", "stderr.txt"}
    if not attempt.is_dir() or {path.name for path in attempt.iterdir()} != expected_files:
        raise ValueError(f"attempt {sequence} has an unexpected file structure")
    stdout_bytes = (attempt / "stdout.jsonl").read_bytes()
    stderr_bytes = (attempt / "stderr.txt").read_bytes()
    if process_record["stdout_sha256"] != sha256_bytes(stdout_bytes):
        raise ValueError(f"attempt {sequence} stdout checksum mismatch")
    if process_record["stderr_sha256"] != sha256_bytes(stderr_bytes):
        raise ValueError(f"attempt {sequence} stderr checksum mismatch")
    if int(process_record["stdout_bytes"]) != len(stdout_bytes):
        raise ValueError(f"attempt {sequence} stdout length mismatch")
    if int(process_record["stderr_bytes"]) != len(stderr_bytes) or stderr_bytes:
        raise ValueError(f"attempt {sequence} produced stderr")
    if process_record["timed_out"]:
        raise ValueError(f"attempt {sequence} timed out")
    if int(process_record["child_pid"]) != int(process_record["pid"]):
        raise ValueError(f"attempt {sequence} child PID mismatch")
    emitted = load_jsonl(attempt / "stdout.jsonl")
    if len(emitted) != len(DATASETS):
        raise ValueError(f"attempt {sequence} emitted the wrong row count")
    emitted_by_dataset = {str(row["dataset"]): row for row in emitted}
    if set(emitted_by_dataset) != set(DATASETS):
        raise ValueError(f"attempt {sequence} emitted duplicate or missing datasets")
    raw_by_dataset = {str(row["dataset"]): row for row in process_rows}
    for dataset in DATASETS:
        for field in CORE_FIELDS:
            if emitted_by_dataset[dataset][field] != raw_by_dataset[dataset][field]:
                raise ValueError(f"attempt {sequence} row changed at {field}")

    with (attempt / "calibration.tsv").open(encoding="utf-8", newline="") as source:
        cells = list(csv.DictReader(source, delimiter="\t"))
    if (attempt / "calibration.tsv").read_bytes() != (root / "calibration.tsv").read_bytes():
        raise ValueError(f"attempt {sequence} calibration file differs from the frozen map")
    expected_cells = {
        (method, dataset, repetitions[(method, dataset)])
        for method in METHODS
        for dataset in DATASETS
    }
    actual_cells = {
        (row["method"], row["dataset"], int(row["reps"])) for row in cells
    }
    if actual_cells != expected_cells or len(cells) != len(METHODS) * len(DATASETS):
        raise ValueError(f"attempt {sequence} did not use the frozen repetition map")


def validate(root: Path) -> None:
    required_files = {
        "calibration.tsv",
        "calibration_attempts.json",
        "processes.jsonl",
        "raw_rows.jsonl",
        "run_metadata.json",
        "schedule.json",
        "summary.json",
    }
    if not required_files.issubset({path.name for path in root.iterdir()}):
        raise ValueError("benchmark output is missing a required receipt")

    metadata = json.loads((root / "run_metadata.json").read_text(encoding="utf-8"))
    if (
        int(metadata["blocks"]) != EXPECTED_BLOCKS
        or int(metadata["aa_blocks"]) != EXPECTED_AA_BLOCKS
        or int(metadata["seed"]) != EXPECTED_SEED
        or int(metadata["target_ms"]) != EXPECTED_TARGET_MS
    ):
        raise ValueError("run metadata does not match the frozen experiment contract")
    if len(str(metadata["binary_sha256"])) != 64 or int(metadata["pinned_cpu"]) < 0:
        raise ValueError("invalid binary identity or pinned processor metadata")
    binary = Path(str(metadata["binary"]))
    if binary.is_file() and sha256_file(binary) != metadata["binary_sha256"]:
        raise ValueError("timing binary no longer matches its recorded checksum")

    schedule = json.loads((root / "schedule.json").read_text(encoding="utf-8"))
    processes = load_jsonl(root / "processes.jsonl")
    rows = load_jsonl(root / "raw_rows.jsonl")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    repetitions = read_calibration(root / "calibration.tsv")
    validate_calibration_attempts(root, repetitions)

    expected_processes = (EXPECTED_BLOCKS + EXPECTED_AA_BLOCKS) * 4
    if len(schedule) != expected_processes or len(processes) != expected_processes:
        raise ValueError("schedule/process count mismatch")
    if len(rows) != expected_processes * len(DATASETS):
        raise ValueError("raw row count mismatch")
    if [int(item["sequence"]) for item in schedule] != list(range(expected_processes)):
        raise ValueError("schedule sequence is not contiguous")
    schedule_by_sequence = {int(item["sequence"]): item for item in schedule}
    if len(schedule_by_sequence) != expected_processes:
        raise ValueError("duplicate schedule sequence")
    if {str(item["family"]) for item in schedule} != {TREATMENT_FAMILY, AA_FAMILY}:
        raise ValueError("unexpected benchmark family")
    validate_block_schedule(
        schedule, TREATMENT_FAMILY, EXPECTED_BLOCKS, "minimal-dafsa"
    )
    validate_block_schedule(schedule, AA_FAMILY, EXPECTED_AA_BLOCKS, "flat-trie")

    pids = [int(record["pid"]) for record in processes]
    if len(pids) != len(set(pids)):
        raise ValueError("fresh-process PID reuse detected")
    if [int(record["sequence"]) for record in processes] != list(range(expected_processes)):
        raise ValueError("process sequence is not contiguous")

    process_by_sequence = {int(record["sequence"]): record for record in processes}
    for process_record in processes:
        if int(process_record["exit_code"]) != 0 or int(process_record["external_wall_ns"]) <= 0:
            raise ValueError("a retained process failed or has invalid wall time")
        scheduled = schedule_by_sequence[int(process_record["sequence"])]
        for field in SCHEDULE_FIELDS + ("actual_method",):
            if process_record[field] != scheduled[field]:
                raise ValueError(f"process schedule field mismatch: {field}")
        if int(process_record["pinned_cpu"]) != int(metadata["pinned_cpu"]):
            raise ValueError("a timed process used the wrong pinned processor")

    rows_by_sequence: dict[int, list[dict[str, Any]]] = {}
    stable_cells: dict[tuple[str, str], tuple[Any, ...]] = {}
    dataset_identity: dict[str, tuple[Any, ...]] = {}
    for row in rows:
        missing = set(CORE_FIELDS + SCHEDULE_FIELDS + ("sequence",)) - set(row)
        if missing:
            raise ValueError(f"raw row is missing fields: {sorted(missing)}")
        sequence = int(row["sequence"])
        if sequence not in schedule_by_sequence:
            raise ValueError("raw row has an unknown sequence")
        rows_by_sequence.setdefault(sequence, []).append(row)
        scheduled = schedule_by_sequence[sequence]
        actual = str(scheduled["actual_method"])
        if row["actual_method"] != actual or row["method"] != actual:
            raise ValueError("actual method mismatch")
        for field in SCHEDULE_FIELDS:
            if row[field] != scheduled[field]:
                raise ValueError(f"raw schedule field mismatch: {field}")
        dataset = str(row["dataset"])
        if dataset not in DATASETS:
            raise ValueError(f"unknown dataset: {dataset}")
        key = (actual, dataset)
        if int(row["reps"]) != repetitions[key]:
            raise ValueError(f"calibration mismatch for {key}")
        elapsed_ns = int(row["elapsed_ns"])
        query_count = int(row["query_count"])
        if elapsed_ns <= 0 or query_count <= 0 or float(row["ns_per_lookup"]) <= 0:
            raise ValueError("non-positive timing value")
        computed = elapsed_ns / (int(row["reps"]) * query_count)
        if not math.isclose(float(row["ns_per_lookup"]), computed, rel_tol=1e-8, abs_tol=1e-9):
            raise ValueError("ns/lookup does not match elapsed/(repetitions*queries)")

        for field, value in EXPECTED_TOPOLOGY[key].items():
            if int(row[field]) != value:
                raise ValueError(f"unexpected {field} for {key}")
        if int(row["topology_bytes"]) != 8 * (
            int(row["state_count"]) + int(row["arc_count"])
        ):
            raise ValueError(f"topology byte arithmetic mismatch for {key}")

        stable_fields = (
            "key_count",
            "key_bytes",
            "query_count",
            "hit_count",
            "state_count",
            "arc_count",
            "topology_bytes",
            "input_checksum",
            "query_checksum",
            "result_checksum",
        )
        signature = tuple(row[field] for field in stable_fields)
        if stable_cells.setdefault(key, signature) != signature:
            raise ValueError(f"unstable metadata or checksum for {key}")
        common_fields = (
            "key_count",
            "key_bytes",
            "query_count",
            "hit_count",
            "input_checksum",
            "query_checksum",
            "result_checksum",
        )
        common = tuple(row[field] for field in common_fields)
        if dataset_identity.setdefault(dataset, common) != common:
            raise ValueError(f"methods disagree on data or results for {dataset}")

    if set(rows_by_sequence) != set(range(expected_processes)):
        raise ValueError("raw rows omit a scheduled process")
    for sequence, process_rows in rows_by_sequence.items():
        if len(process_rows) != len(DATASETS):
            raise ValueError(f"sequence {sequence} has an incomplete dataset pair")
        if {str(row["dataset"]) for row in process_rows} != set(DATASETS):
            raise ValueError(f"sequence {sequence} has duplicate or missing datasets")
        if {int(row["pid"]) for row in process_rows} != {
            int(process_by_sequence[sequence]["pid"])
        }:
            raise ValueError(f"sequence {sequence} PID mismatch")
        validate_attempt(root, sequence, process_by_sequence[sequence], process_rows, repetitions)

    expected = {
        (str(item["family"]), str(item["dataset"])): item for item in recompute(rows)
    }
    if summary.get("run_metadata") != metadata:
        raise ValueError("summary metadata differs from the primary receipt")
    expected_structure = []
    for dataset in DATASETS:
        flat = {
            field: EXPECTED_TOPOLOGY[("flat-trie", dataset)][field]
            for field in ("state_count", "arc_count", "topology_bytes")
        }
        minimal = {
            field: EXPECTED_TOPOLOGY[("minimal-dafsa", dataset)][field]
            for field in ("state_count", "arc_count", "topology_bytes")
        }
        expected_structure.append(
            {
                "dataset": dataset,
                "flat_trie": flat,
                "minimal_dafsa": minimal,
                "minimal_dafsa_to_flat_trie": {
                    field: minimal[field] / flat[field]
                    for field in ("state_count", "arc_count", "topology_bytes")
                },
            }
        )
    if summary.get("structure") != expected_structure:
        raise ValueError("structural summary differs from the expected topology")
    observed_items = summary.get("analyses", [])
    observed = {
        (str(item["family"]), str(item["dataset"])): item for item in observed_items
    }
    if len(observed) != len(observed_items) or set(expected) != set(observed):
        raise ValueError("analysis identity or count mismatch")
    for identity, left in expected.items():
        right = observed[identity]
        if right.get("ratio_direction") != "label-B/label-A":
            raise ValueError(f"analysis ratio direction mismatch: {identity}")
        if int(left["n_complete_blocks"]) != int(right["n_complete_blocks"]):
            raise ValueError(f"analysis block count mismatch: {identity}")
        for field in ("mean_log_ratio", "geometric_mean_ratio", "sample_sd_log_ratio"):
            if not close(float(left[field]), float(right[field])):
                raise ValueError(f"analysis value mismatch: {identity}/{field}")
        if len(left["log_contrasts"]) != len(right["log_contrasts"]):
            raise ValueError(f"contrast count mismatch: {identity}")
        if not all(
            close(float(a), float(b))
            for a, b in zip(left["log_contrasts"], right["log_contrasts"])
        ):
            raise ValueError(f"block contrast mismatch: {identity}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.output.resolve(strict=True)
    validate(root)
    metadata = json.loads((root / "run_metadata.json").read_text(encoding="utf-8"))
    print(
        "CHECK=PASS "
        f"blocks={metadata['blocks']} aa_blocks={metadata['aa_blocks']} "
        f"seed={metadata['seed']} processes={(EXPECTED_BLOCKS + EXPECTED_AA_BLOCKS) * 4}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
