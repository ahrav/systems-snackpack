#!/usr/bin/env python3
"""Run Topic 14 comparisons as order-balanced fresh pinned processes."""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path


COMPARISONS = (
    ("scalar-vs-simd", "scalar_whole", "simd_whole"),
    ("whole-vs-chunks", "dispatch_once", "cached_chunks"),
    ("cached-vs-detect", "cached_chunks", "detect_chunks"),
)
PAIRS = 12
INPUT_BYTES = 64 * 1024 * 1024
PASSES = 8
CHUNK_BYTES = 256
HEADER = (
    "run_id",
    "comparison",
    "pair",
    "position",
    "order",
    "mode",
    "variant",
    "input_bytes",
    "passes",
    "chunk_bytes",
    "source_commit",
    "input_checksum",
    "expected_per_pass",
    "checksum",
    "expected_checksum",
    "setup_ns",
    "steady_ns",
    "verify_ns",
    "external_wall_ns",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def schedule() -> list[tuple[str, int, int, str, str]]:
    records: list[tuple[str, int, int, str, str]] = []
    for comparison, mode_a, mode_b in COMPARISONS:
        for pair in range(1, PAIRS + 1):
            order = "ab" if pair % 2 else "ba"
            modes = (mode_a, mode_b) if order == "ab" else (mode_b, mode_a)
            for position, mode in enumerate(modes, start=1):
                records.append((comparison, pair, position, order, mode))
    return records


def print_schedule() -> None:
    for comparison, pair, position, order, mode in schedule():
        run_id = f"{comparison.replace('-vs-', '_')}-p{pair:02}-{position}"
        print(
            f"SCHEDULE {run_id} {comparison} {pair} {position} {order} {mode}"
        )


def integer(row: dict[str, str], field: str) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError):
        fail(f"{row.get('run_id', '<unknown>')}: {field} is not an integer")


def validate_row(
    fields: list[str],
    *,
    source_commit: str,
    comparison: str,
    pair: int,
    position: int,
    order: str,
    mode: str,
) -> None:
    if len(fields) != len(HEADER) - 1:
        fail(
            f"{comparison} pair {pair} position {position}: benchmark emitted "
            f"{len(fields)} fields, expected {len(HEADER) - 1}"
        )
    row = dict(zip(HEADER[:-1], fields))
    run_id = f"{comparison.replace('-vs-', '_')}-p{pair:02}-{position}"
    expected_text = {
        "run_id": run_id,
        "comparison": comparison,
        "pair": str(pair),
        "position": str(position),
        "order": order,
        "mode": mode,
        "source_commit": source_commit,
    }
    for field, expected in expected_text.items():
        if row[field] != expected:
            fail(f"{run_id}: {field}={row[field]!r}, expected {expected!r}")
    if mode == "scalar_whole":
        if row["variant"] != "scalar":
            fail(f"{run_id}: scalar mode did not report the scalar variant")
    elif row["variant"] not in {"avx2", "neon"}:
        fail(f"{run_id}: selected mode did not report avx2 or neon")

    expected_integer = {
        "input_bytes": INPUT_BYTES,
        "passes": PASSES,
        "chunk_bytes": CHUNK_BYTES,
    }
    for field, expected in expected_integer.items():
        if integer(row, field) != expected:
            fail(f"{run_id}: {field} differs from the recorded configuration")
    expected_per_pass = integer(row, "expected_per_pass")
    checksum = integer(row, "checksum")
    expected_checksum = integer(row, "expected_checksum")
    if expected_per_pass <= 0:
        fail(f"{run_id}: deterministic fixture unexpectedly has no matches")
    if checksum != expected_checksum or checksum != expected_per_pass * PASSES:
        fail(f"{run_id}: result differs from the recorded scalar oracle")
    if integer(row, "input_checksum") <= 0:
        fail(f"{run_id}: input checksum must be positive")
    if integer(row, "setup_ns") <= 0 or integer(row, "steady_ns") <= 0:
        fail(f"{run_id}: setup and steady timing must be positive")
    if integer(row, "verify_ns") < 0:
        fail(f"{run_id}: verification timing must be nonnegative")


def run(
    binary: Path,
    raw_path: Path,
    process_log: Path,
    source_commit: str,
    cpu: str,
) -> None:
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        fail("BINARY must be an absolute executable file")
    if not raw_path.is_absolute() or not process_log.is_absolute():
        fail("RAW_TSV and PROCESS_LOG must be absolute paths")
    if raw_path.exists() or process_log.exists():
        fail("RAW_TSV and PROCESS_LOG must not already exist")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail("SOURCE_COMMIT must be a 40-character lowercase SHA-1")
    if not re.fullmatch(r"[0-9]+", cpu):
        fail("CPU must be a nonnegative integer")

    child_environment = os.environ.copy()
    child_environment.update(
        {
            "TOPIC14_BYTES": str(INPUT_BYTES),
            "TOPIC14_PASSES": str(PASSES),
            "TOPIC14_CHUNK_BYTES": str(CHUNK_BYTES),
        }
    )
    records = schedule()
    with raw_path.open("x", encoding="utf-8", newline="") as raw_file, process_log.open(
        "x", encoding="utf-8"
    ) as log_file:
        writer = csv.writer(raw_file, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        log_file.write(
            "SESSION_START "
            f"source_commit={source_commit} cpu={cpu} pairs={PAIRS} "
            f"comparisons={len(COMPARISONS)} processes={len(records)}\n"
        )
        raw_file.flush()
        log_file.flush()

        for comparison, pair, position, order, mode in records:
            run_id = f"{comparison.replace('-vs-', '_')}-p{pair:02}-{position}"
            command = [
                "taskset",
                "--cpu-list",
                cpu,
                str(binary),
                run_id,
                comparison,
                str(pair),
                str(position),
                order,
                mode,
            ]
            log_file.write(
                f"PROCESS_START run_id={run_id} comparison={comparison} "
                f"pair={pair} position={position} order={order} mode={mode}\n"
            )
            log_file.flush()
            started = time.monotonic_ns()
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=child_environment,
            )
            external_wall_ns = time.monotonic_ns() - started
            if completed.returncode != 0:
                sys.stderr.write(completed.stderr)
                fail(f"{run_id}: benchmark exited with status {completed.returncode}")
            if completed.stderr:
                sys.stderr.write(completed.stderr)
                fail(f"{run_id}: successful benchmark emitted stderr")
            lines = completed.stdout.splitlines()
            if len(lines) != 1:
                fail(f"{run_id}: benchmark did not emit exactly one TSV row")
            fields = lines[0].split("\t")
            validate_row(
                fields,
                source_commit=source_commit,
                comparison=comparison,
                pair=pair,
                position=position,
                order=order,
                mode=mode,
            )
            internal_ns = sum(int(fields[index]) for index in (15, 16, 17))
            if external_wall_ns < internal_ns:
                fail(f"{run_id}: external wall time does not cover internal phases")
            writer.writerow([*fields, external_wall_ns])
            raw_file.flush()
            log_file.write(
                f"PROCESS_END run_id={run_id} external_wall_ns={external_wall_ns}\n"
            )
            log_file.flush()

        log_file.write(f"SESSION_END processes={len(records)}\n")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-schedule":
        print_schedule()
        return
    if len(sys.argv) != 6:
        fail(
            f"usage: {Path(sys.argv[0]).name} "
            "BINARY RAW_TSV PROCESS_LOG SOURCE_COMMIT CPU"
        )
    run(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        Path(sys.argv[3]),
        sys.argv[4],
        sys.argv[5],
    )


if __name__ == "__main__":
    main()
