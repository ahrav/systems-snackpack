#!/usr/bin/env python3
"""Run calibrated fresh-process flat-trie versus minimal-DAFSA comparisons."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time


METHODS = ("flat-trie", "minimal-dafsa")
DATASETS = ("shared", "opaque")
CANDIDATE_FAMILY = "flat-trie_vs_minimal-dafsa"
AA_FAMILY = "flat-trie_AA"
PROCESS_TIMEOUT_SECONDS = 1_800


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--aa-blocks", type=int, default=4)
    parser.add_argument("--seed", type=int, default=350035)
    parser.add_argument("--target-ms", type=int, default=200)
    args = parser.parse_args()
    if args.blocks != 12:
        parser.error("--blocks must be 12 for the predeclared design")
    if args.aa_blocks != 4:
        parser.error("--aa-blocks must be 4 for the predeclared design")
    if args.target_ms != 200:
        parser.error("--target-ms must be 200 for the predeclared design")
    if args.seed != 350035:
        parser.error("--seed must be 350035 for the predeclared design")
    return args


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path: Path, value: object) -> None:
    write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def replace_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with temporary.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def first_allowed_cpu() -> tuple[int, list[int]]:
    if not hasattr(os, "sched_getaffinity") or not hasattr(os, "sched_setaffinity"):
        raise RuntimeError("CPU-affinity APIs are required")
    allowed = sorted(os.sched_getaffinity(0))
    if not allowed:
        raise RuntimeError("the process affinity mask is empty")
    return allowed[0], allowed


def child_affinity(cpu: int):
    def pin() -> None:
        os.sched_setaffinity(0, {cpu})

    return pin


def run_command(command: list[str], cpu: int) -> dict[str, object]:
    started = time.monotonic_ns()
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=child_affinity(cpu),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=PROCESS_TIMEOUT_SECONDS)
        exit_code = process.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
        exit_code = 124
    return {
        "child_pid": process.pid,
        "exit_code": exit_code,
        "external_wall_ns": time.monotonic_ns() - started,
        "pinned_cpu": cpu,
        "stderr": stderr,
        "stdout": stdout,
        "timed_out": timed_out,
    }


def public_receipt(result: dict[str, object]) -> dict[str, object]:
    stdout = bytes(result["stdout"])
    stderr = bytes(result["stderr"])
    return {
        "child_pid": result["child_pid"],
        "exit_code": result["exit_code"],
        "external_wall_ns": result["external_wall_ns"],
        "pinned_cpu": result["pinned_cpu"],
        "stderr_bytes": len(stderr),
        "stderr_sha256": sha256_bytes(stderr),
        "stdout_bytes": len(stdout),
        "stdout_sha256": sha256_bytes(stdout),
        "timed_out": result["timed_out"],
    }


def calibrate(
    binary: Path, output: Path, target_ms: int, cpu: int
) -> dict[tuple[str, str], int]:
    repetitions: dict[tuple[str, str], int] = {}
    attempts: list[dict[str, object]] = []
    for method in METHODS:
        for dataset in DATASETS:
            command = [str(binary), "calibrate", method, dataset, str(target_ms)]
            result = run_command(command, cpu)
            stdout = bytes(result["stdout"])
            stderr = bytes(result["stderr"])
            receipt = {
                "command": command,
                "dataset": dataset,
                "method": method,
                **public_receipt(result),
                "stderr": stderr.decode("utf-8", errors="backslashreplace"),
                "stdout": stdout.decode("utf-8", errors="backslashreplace"),
            }
            attempts.append(receipt)
            replace_json(output / "calibration_attempts.json", attempts)
            if result["exit_code"] != 0 or result["timed_out"] or stderr:
                raise RuntimeError(f"calibration failed for {method}/{dataset}")
            text = stdout.decode("utf-8")
            lines = [line for line in text.splitlines() if line.startswith("reps=")]
            if len(lines) != 1 or len(text.splitlines()) != 1:
                raise RuntimeError(f"invalid calibration output for {method}/{dataset}")
            reps = int(lines[0].split("=", 1)[1])
            if reps < 1:
                raise RuntimeError(f"non-positive calibration for {method}/{dataset}")
            repetitions[(method, dataset)] = reps
            receipt["reps"] = reps
            replace_json(output / "calibration_attempts.json", attempts)

    calibration_path = output / "calibration.tsv"
    with calibration_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(("method", "dataset", "reps"))
        for method in METHODS:
            for dataset in DATASETS:
                writer.writerow((method, dataset, repetitions[(method, dataset)]))
        stream.flush()
        os.fsync(stream.fileno())
    return repetitions


def balanced_templates(count: int, rng: random.Random) -> list[str]:
    templates = ["ABBA"] * (count // 2) + ["BAAB"] * (count // 2)
    rng.shuffle(templates)
    return templates


def make_schedule(blocks: int, aa_blocks: int, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    schedule: list[dict[str, object]] = []
    sequence = 0
    for block, template in enumerate(balanced_templates(blocks, rng)):
        for period, label in enumerate(template, start=1):
            actual = "flat-trie" if label == "A" else "minimal-dafsa"
            schedule.append(
                {
                    "actual_method": actual,
                    "block": block,
                    "candidate": "minimal-dafsa",
                    "family": CANDIDATE_FAMILY,
                    "label": label,
                    "period": period,
                    "sequence": sequence,
                    "template": template,
                }
            )
            sequence += 1
    for block, template in enumerate(balanced_templates(aa_blocks, rng)):
        for period, label in enumerate(template, start=1):
            schedule.append(
                {
                    "actual_method": "flat-trie",
                    "block": block,
                    "candidate": "flat-trie",
                    "family": AA_FAMILY,
                    "label": label,
                    "period": period,
                    "sequence": sequence,
                    "template": template,
                }
            )
            sequence += 1
    return schedule


def execute_schedule(
    binary: Path,
    output: Path,
    schedule: list[dict[str, object]],
    repetitions: dict[tuple[str, str], int],
    cpu: int,
) -> list[dict[str, object]]:
    attempts_dir = output / "attempts"
    attempts_dir.mkdir()
    frozen_calibration = output / "calibration.tsv"
    rows_path = output / "raw_rows.jsonl"
    processes_path = output / "processes.jsonl"
    all_rows: list[dict[str, object]] = []
    seen_pids: set[int] = set()
    with rows_path.open("x", encoding="utf-8") as rows_stream, processes_path.open(
        "x", encoding="utf-8"
    ) as processes_stream:
        for item in schedule:
            sequence = int(item["sequence"])
            attempt = attempts_dir / f"{sequence:04d}"
            attempt.mkdir()
            calibration_path = attempt / "calibration.tsv"
            shutil.copyfile(frozen_calibration, calibration_path)
            actual_method = str(item["actual_method"])
            command = [str(binary), "process", actual_method, str(calibration_path)]
            result = run_command(command, cpu)
            stdout = bytes(result["stdout"])
            stderr = bytes(result["stderr"])
            write_bytes(attempt / "stdout.jsonl", stdout)
            write_bytes(attempt / "stderr.txt", stderr)
            process_record = {
                **item,
                "command": command,
                "pid": result["child_pid"],
                **public_receipt(result),
            }
            processes_stream.write(json.dumps(process_record, sort_keys=True) + "\n")
            processes_stream.flush()
            os.fsync(processes_stream.fileno())
            if result["exit_code"] != 0 or result["timed_out"]:
                raise RuntimeError(f"process {sequence} failed; retained under {attempt}")
            if stderr:
                raise RuntimeError(f"process {sequence} wrote stderr; retained under {attempt}")
            parsed = [json.loads(line) for line in stdout.decode("utf-8").splitlines() if line]
            if [row.get("dataset") for row in parsed] != list(DATASETS):
                raise RuntimeError(f"process {sequence} did not emit shared,opaque rows")
            pids = {int(row["pid"]) for row in parsed}
            pid = int(result["child_pid"])
            if pids != {pid}:
                raise RuntimeError(f"process {sequence} reported the wrong PID")
            if pid in seen_pids:
                raise RuntimeError(f"PID {pid} was reused inside the run window")
            seen_pids.add(pid)
            for row in parsed:
                dataset = str(row["dataset"])
                if row.get("method") != actual_method or row.get("actual_method") != actual_method:
                    raise RuntimeError(f"process {sequence} reported the wrong method")
                if int(row["reps"]) != repetitions[(actual_method, dataset)]:
                    raise RuntimeError(f"process {sequence} did not use frozen calibration")
                enriched = {**row, **{key: item[key] for key in (
                    "sequence", "family", "candidate", "block", "period", "template", "label"
                )}}
                all_rows.append(enriched)
                rows_stream.write(json.dumps(enriched, sort_keys=True) + "\n")
            rows_stream.flush()
            os.fsync(rows_stream.fileno())
    return all_rows


def analyse(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    analyses: list[dict[str, object]] = []
    for family in (CANDIDATE_FAMILY, AA_FAMILY):
        for dataset in DATASETS:
            selected = [
                row for row in rows if row["family"] == family and row["dataset"] == dataset
            ]
            contrasts: list[float] = []
            for block in sorted({int(row["block"]) for row in selected}):
                cells = sorted(
                    [row for row in selected if int(row["block"]) == block],
                    key=lambda row: int(row["period"]),
                )
                if len(cells) != 4:
                    raise RuntimeError(f"incomplete block {family}/{block}/{dataset}")
                a = [math.log(float(row["ns_per_lookup"])) for row in cells if row["label"] == "A"]
                b = [math.log(float(row["ns_per_lookup"])) for row in cells if row["label"] == "B"]
                if len(a) != 2 or len(b) != 2:
                    raise RuntimeError(f"invalid treatment labels in {family}/{block}")
                contrasts.append(statistics.fmean(b) - statistics.fmean(a))
            mean_log = statistics.fmean(contrasts)
            analyses.append(
                {
                    "dataset": dataset,
                    "family": family,
                    "geometric_mean_ratio": math.exp(mean_log),
                    "log_contrasts": contrasts,
                    "mean_log_ratio": mean_log,
                    "n_complete_blocks": len(contrasts),
                    "ratio_direction": "label-B/label-A",
                    "sample_sd_log_ratio": statistics.stdev(contrasts),
                }
            )
    return analyses


def structural_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for dataset in DATASETS:
        methods: dict[str, dict[str, int]] = {}
        for method in METHODS:
            selected = [row for row in rows if row["dataset"] == dataset and row["actual_method"] == method]
            values: dict[str, int] = {}
            for field in ("state_count", "arc_count", "topology_bytes"):
                observed = {int(row[field]) for row in selected}
                if len(observed) != 1:
                    raise RuntimeError(f"unstable {field} for {method}/{dataset}")
                values[field] = observed.pop()
            methods[method] = values
        flat = methods["flat-trie"]
        minimal = methods["minimal-dafsa"]
        result.append(
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
    return result


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"output already exists: {output}")
    output.mkdir(parents=True)
    cpu, allowed_cpus = first_allowed_cpu()
    metadata = {
        "aa_blocks": args.aa_blocks,
        "allowed_cpus": allowed_cpus,
        "binary": str(binary),
        "binary_sha256": sha256_file(binary),
        "blocks": args.blocks,
        "pid": os.getpid(),
        "pinned_cpu": cpu,
        "python": sys.version,
        "seed": args.seed,
        "target_ms": args.target_ms,
    }
    write_json(output / "run_metadata.json", metadata)
    repetitions = calibrate(binary, output, args.target_ms, cpu)
    schedule = make_schedule(args.blocks, args.aa_blocks, args.seed)
    write_json(output / "schedule.json", schedule)
    rows = execute_schedule(binary, output, schedule, repetitions, cpu)
    write_json(
        output / "summary.json",
        {
            "analyses": analyse(rows),
            "run_metadata": metadata,
            "structure": structural_summary(rows),
        },
    )
    print(f"CHECK=PASS processes={len(schedule)} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR={error}", file=sys.stderr)
        raise
