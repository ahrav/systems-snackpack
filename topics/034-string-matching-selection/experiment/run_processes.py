#!/usr/bin/env python3
"""Run calibrated, order-balanced fresh-process string-search comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

METHODS = ("left-to-right", "kmp", "horspool")
CASES = (
    "uniform_absent_32",
    "text_late_16",
    "prefix_trap_32",
    "suffix_trap_32",
    "tiny_late_4",
)
MODES = ("reuse", "one_shot")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--aa-blocks", type=int, default=4)
    parser.add_argument("--seed", type=int, default=340034)
    parser.add_argument("--target-ms", type=int, default=200)
    args = parser.parse_args()
    if args.blocks < 2 or args.blocks % 2:
        parser.error("--blocks must be a positive even number of at least 2")
    if args.aa_blocks < 2 or args.aa_blocks % 2:
        parser.error("--aa-blocks must be a positive even number of at least 2")
    if args.target_ms < 1:
        parser.error("--target-ms must be positive")
    return args


def first_allowed_cpu() -> int | None:
    if hasattr(os, "sched_getaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        if not allowed:
            raise RuntimeError("the process affinity mask is empty")
        return allowed[0]
    return None


def child_affinity(cpu: int | None):
    if cpu is None or not hasattr(os, "sched_setaffinity"):
        return None

    def pin() -> None:
        os.sched_setaffinity(0, {cpu})

    return pin


def as_int(value: Any, label: str = "integer field") -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid {label}: {value!r}") from error


def as_float(value: Any, label: str = "numeric field") -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"invalid {label}: {value!r}") from error


def parse_json(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except ValueError as error:
        raise RuntimeError(f"invalid JSON in {label}: {error}") from error


def captured_text(stream: bytes | str | None) -> str:
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", "replace")
    return stream


def run_command(command: list[str], cpu: int | None) -> tuple[subprocess.CompletedProcess[str], int]:
    started = time.monotonic_ns()
    completed: subprocess.CompletedProcess[str]
    try:
        raw = subprocess.run(
            command,
            capture_output=True,
            check=False,
            preexec_fn=child_affinity(cpu),
            timeout=1800,
        )
        completed = subprocess.CompletedProcess(
            command,
            returncode=raw.returncode,
            stdout=captured_text(raw.stdout),
            stderr=captured_text(raw.stderr),
        )
    except subprocess.TimeoutExpired as expired:
        completed = subprocess.CompletedProcess(
            command,
            returncode=124,
            stdout=captured_text(expired.stdout),
            stderr=captured_text(expired.stderr) + f"\nTIMEOUT after {expired.timeout}s\n",
        )
    return completed, time.monotonic_ns() - started


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def calibrate(binary: Path, output: Path, target_ms: int, cpu: int | None) -> dict[tuple[str, str, str], int]:
    calibration: dict[tuple[str, str, str], int] = {}
    records = []
    for method in METHODS:
        for case in CASES:
            for mode in MODES:
                command = [str(binary), "calibrate", method, case, mode, str(target_ms)]
                completed, wall_ns = run_command(command, cpu)
                record = {
                    "method": method,
                    "case": case,
                    "mode": mode,
                    "command": command,
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "external_wall_ns": wall_ns,
                }
                records.append(record)
                (output / "calibration_attempts.json").write_text(
                    json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                if completed.returncode != 0:
                    raise RuntimeError(f"calibration failed: {record}")
                lines = [line for line in completed.stdout.splitlines() if line.startswith("reps=")]
                if len(lines) != 1:
                    raise RuntimeError(f"invalid calibration output: {record}")
                repetitions = as_int(lines[0].split("=", 1)[1])
                if repetitions < 1:
                    raise RuntimeError(f"non-positive calibration: {record}")
                calibration[(method, case, mode)] = repetitions

    lines = ["method\tcase\tmode\treps"]
    for method in METHODS:
        for case in CASES:
            for mode in MODES:
                lines.append(f"{method}\t{case}\t{mode}\t{calibration[(method, case, mode)]}")
    (output / "calibration.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return calibration


def balanced_templates(count: int, rng: random.Random) -> list[str]:
    templates = ["ABBA"] * (count // 2) + ["BAAB"] * (count // 2)
    rng.shuffle(templates)
    return templates


def rotated_cells(block: int) -> list[tuple[str, str]]:
    cells = [(case, mode) for case in CASES for mode in MODES]
    offset = block % len(cells)
    return cells[offset:] + cells[:offset]


def make_schedule(blocks: int, aa_blocks: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    families = (
        ("left-to-right_vs_kmp", "kmp"),
        ("left-to-right_vs_horspool", "horspool"),
    )
    family_templates = {
        name: balanced_templates(blocks, rng) for name, _candidate in families
    }
    first_family = rng.randrange(2)
    schedule = []
    sequence = 0
    for block in range(blocks):
        order = list(families)
        if (block + first_family) % 2:
            order.reverse()
        for family, candidate in order:
            template = family_templates[family][block]
            for period, label in enumerate(template, start=1):
                actual = "left-to-right" if label == "A" else candidate
                schedule.append(
                    {
                        "sequence": sequence,
                        "family": family,
                        "candidate": candidate,
                        "block": block,
                        "period": period,
                        "template": template,
                        "label": label,
                        "actual_method": actual,
                        "cell_rotation": block % (len(CASES) * len(MODES)),
                    }
                )
                sequence += 1

    aa_templates = balanced_templates(aa_blocks, rng)
    for block, template in enumerate(aa_templates):
        for period, label in enumerate(template, start=1):
            schedule.append(
                {
                    "sequence": sequence,
                    "family": "left-to-right_AA",
                    "candidate": "left-to-right",
                    "block": block,
                    "period": period,
                    "template": template,
                    "label": label,
                    "actual_method": "left-to-right",
                    "cell_rotation": block % (len(CASES) * len(MODES)),
                }
            )
            sequence += 1
    return schedule


def write_process_calibration(
    path: Path,
    actual_method: str,
    block: int,
    calibration: dict[tuple[str, str, str], int],
) -> None:
    lines = ["method\tcase\tmode\treps"]
    for case, mode in rotated_cells(block):
        lines.append(
            f"{actual_method}\t{case}\t{mode}\t{calibration[(actual_method, case, mode)]}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute_schedule(
    binary: Path,
    output: Path,
    schedule: list[dict[str, Any]],
    calibration: dict[tuple[str, str, str], int],
    cpu: int | None,
) -> list[dict[str, Any]]:
    attempts_dir = output / "attempts"
    attempts_dir.mkdir()
    rows_file = output / "raw_rows.jsonl"
    process_file = output / "processes.jsonl"
    all_rows = []
    seen_pids: set[int] = set()
    with rows_file.open("w", encoding="utf-8") as rows_stream, process_file.open(
        "w", encoding="utf-8"
    ) as process_stream:
        for item in schedule:
            sequence = as_int(item["sequence"])
            attempt = attempts_dir / f"{sequence:04d}"
            attempt.mkdir()
            calibration_path = attempt / "calibration.tsv"
            actual_method = str(item["actual_method"])
            write_process_calibration(
                calibration_path, actual_method, as_int(item["block"]), calibration
            )
            command = [str(binary), "process", actual_method, str(calibration_path)]
            completed, wall_ns = run_command(command, cpu)
            (attempt / "stdout.jsonl").write_text(completed.stdout, encoding="utf-8")
            (attempt / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
            process_record = dict(item)
            process_record.update(
                {
                    "command": command,
                    "exit_code": completed.returncode,
                    "external_wall_ns": wall_ns,
                    "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                    "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
                }
            )
            if completed.returncode != 0:
                process_stream.write(json.dumps(process_record, sort_keys=True) + "\n")
                process_stream.flush()
                raise RuntimeError(f"process {sequence} failed; retained under {attempt}")
            try:
                parsed = [
                    parse_json(line, f"process {sequence} stdout")
                    for line in completed.stdout.splitlines()
                    if line.strip()
                ]
                if len(parsed) != len(CASES) * len(MODES):
                    raise RuntimeError(f"process {sequence} emitted {len(parsed)} rows")
                pids = {as_int(row["pid"]) for row in parsed}
                if len(pids) != 1:
                    raise RuntimeError(f"process {sequence} emitted multiple PIDs")
                pid = pids.pop()
                if pid in seen_pids:
                    raise RuntimeError(f"PID {pid} was reused inside the run window")
            except Exception:
                process_stream.write(json.dumps(process_record, sort_keys=True) + "\n")
                process_stream.flush()
                raise
            seen_pids.add(pid)
            process_record["pid"] = pid
            process_stream.write(json.dumps(process_record, sort_keys=True) + "\n")
            process_stream.flush()
            for row in parsed:
                enriched = dict(row)
                enriched.update(
                    {
                        "sequence": sequence,
                        "family": item["family"],
                        "candidate": item["candidate"],
                        "block": item["block"],
                        "period": item["period"],
                        "template": item["template"],
                        "label": item["label"],
                    }
                )
                all_rows.append(enriched)
                rows_stream.write(json.dumps(enriched, sort_keys=True) + "\n")
            rows_stream.flush()
    return all_rows


def analyse(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    analyses = []
    families = sorted({str(row["family"]) for row in rows})
    for family in families:
        for case in CASES:
            for mode in MODES:
                selected = [
                    row
                    for row in rows
                    if row["family"] == family and row["case"] == case and row["mode"] == mode
                ]
                by_block: dict[int, list[dict[str, Any]]] = {}
                for row in selected:
                    by_block.setdefault(as_int(row["block"]), []).append(row)
                contrasts = []
                for block in sorted(by_block):
                    block_rows = sorted(by_block[block], key=lambda row: as_int(row["period"]))
                    if len(block_rows) != 4:
                        raise RuntimeError(f"incomplete block {family}/{block}/{case}/{mode}")
                    a_logs = [math.log(as_float(row["ns_per_search"])) for row in block_rows if row["label"] == "A"]
                    b_logs = [math.log(as_float(row["ns_per_search"])) for row in block_rows if row["label"] == "B"]
                    if len(a_logs) != 2 or len(b_logs) != 2:
                        raise RuntimeError(f"invalid treatment labels in {family}/{block}")
                    contrasts.append(sum(b_logs) / 2.0 - sum(a_logs) / 2.0)
                mean_log = statistics.fmean(contrasts)
                analyses.append(
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
    return analyses


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    if args.output.exists():
        raise RuntimeError(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)
    cpu = first_allowed_cpu()
    run_metadata = {
        "binary": str(binary),
        "binary_sha256": sha256(binary),
        "blocks": args.blocks,
        "aa_blocks": args.aa_blocks,
        "seed": args.seed,
        "target_ms": args.target_ms,
        "pinned_cpu": cpu,
        "python": sys.version,
        "pid": os.getpid(),
    }
    (args.output / "run_metadata.json").write_text(
        json.dumps(run_metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    calibration = calibrate(binary, args.output, args.target_ms, cpu)
    schedule = make_schedule(args.blocks, args.aa_blocks, args.seed)
    (args.output / "schedule.json").write_text(
        json.dumps(schedule, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rows = execute_schedule(binary, args.output, schedule, calibration, cpu)
    if sha256(binary) != run_metadata["binary_sha256"]:
        raise RuntimeError(f"{binary} changed during the schedule; rows span two executables")
    summary = {"run_metadata": run_metadata, "analyses": analyse(rows)}
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"CHECK=PASS processes={len(schedule)} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # retain output before failing closed
        print(f"ERROR={error}", file=sys.stderr)
        raise
