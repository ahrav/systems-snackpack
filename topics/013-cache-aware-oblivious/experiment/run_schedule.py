#!/usr/bin/env python3
"""Run the balanced Topic 13 schedule as fresh pinned processes."""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path


MODES = (
    "pow2-naive",
    "pow2-tiled",
    "pow2-recursive",
    "padded-naive",
    "padded-tiled",
    "padded-recursive",
)
SCHEDULE = tuple(
    tuple(MODES[(offset + position) % len(MODES)] for position in range(len(MODES)))
    for offset in range(len(MODES))
) + tuple(
    tuple(tuple(reversed(MODES))[(offset + position) % len(MODES)] for position in range(len(MODES)))
    for offset in range(len(MODES))
)
HEADER = (
    "run_id",
    "block",
    "position",
    "mode",
    "variant",
    "n",
    "leading_dimension",
    "tile_edge",
    "recursive_leaf_elements",
    "condition_bytes",
    "source_commit",
    "source_virtual_base",
    "destination_virtual_base",
    "source_mod64",
    "destination_mod64",
    "source_page_offset",
    "destination_page_offset",
    "setup_ns",
    "kernel_ns",
    "verify_ns",
    "checksum",
    "expected_checksum",
    "external_wall_ns",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def expected_checksum(n: int) -> int:
    axis_sum = n * (n - 1) // 2
    return n * n * 7 + (131 + 17) * n * axis_sum


def validate_row(
    fields: list[str],
    *,
    source_commit: str,
    block: int,
    position: int,
    mode: str,
) -> None:
    if len(fields) != len(HEADER) - 1:
        fail(
            f"b{block:02}-p{position}: benchmark emitted {len(fields)} fields, "
            f"expected {len(HEADER) - 1}"
        )
    row = dict(zip(HEADER[:-1], fields))
    run_id = f"b{block:02}-p{position}"
    if row["run_id"] != run_id:
        fail(f"{run_id}: benchmark emitted run ID {row['run_id']!r}")
    if row["block"] != str(block) or row["position"] != str(position):
        fail(f"{run_id}: benchmark block or position differs from the schedule")
    if row["mode"] != mode:
        fail(f"{run_id}: benchmark emitted mode {row['mode']!r}, expected {mode!r}")
    expected_variant = mode.split("-", 1)[1]
    if row["variant"] != expected_variant:
        fail(f"{run_id}: variant differs from mode suffix")
    expected_ld = 2_048 if mode.startswith("pow2-") else 2_049
    expected_fields = {
        "n": 2_048,
        "leading_dimension": expected_ld,
        "tile_edge": 32,
        "recursive_leaf_elements": 1_024,
        "condition_bytes": 128 * 1024 * 1024,
        "checksum": expected_checksum(2_048),
        "expected_checksum": expected_checksum(2_048),
    }
    for field, expected in expected_fields.items():
        try:
            observed = int(row[field])
        except ValueError:
            fail(f"{run_id}: {field} is not an integer")
        if observed != expected:
            fail(f"{run_id}: {field}={observed}, expected {expected}")
    if row["source_commit"] != source_commit:
        fail(f"{run_id}: embedded source commit differs from the verified archive")
    try:
        source_base = int(row["source_virtual_base"])
        destination_base = int(row["destination_virtual_base"])
    except ValueError:
        fail(f"{run_id}: virtual base fields are not integers")
    if source_base <= 0 or destination_base <= 0 or source_base == destination_base:
        fail(f"{run_id}: virtual bases must be distinct positive addresses")
    storage_bytes = 2_048 * expected_ld * 8
    if source_base < destination_base + storage_bytes and destination_base < source_base + storage_bytes:
        fail(f"{run_id}: source and destination virtual ranges overlap")
    expected_placement = {
        "source_mod64": source_base % 64,
        "destination_mod64": destination_base % 64,
        "source_page_offset": source_base % 4_096,
        "destination_page_offset": destination_base % 4_096,
    }
    for field, expected in expected_placement.items():
        try:
            observed = int(row[field])
        except ValueError:
            fail(f"{run_id}: {field} is not an integer")
        if observed != expected:
            fail(f"{run_id}: {field} disagrees with the recorded virtual base")
    for field in ("setup_ns", "kernel_ns", "verify_ns"):
        try:
            observed = int(row[field])
        except ValueError:
            fail(f"{run_id}: {field} is not an integer")
        if observed <= 0:
            fail(f"{run_id}: {field} must be positive")


def print_schedule() -> None:
    for block in SCHEDULE:
        print("SCHEDULE " + " ".join(block))


def run(binary: Path, raw_path: Path, process_log: Path, source_commit: str, cpu: str) -> None:
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        fail("BINARY must be an absolute executable file")
    if not raw_path.is_absolute() or not process_log.is_absolute():
        fail("RAW_TSV and PROCESS_LOG must be absolute paths")
    if raw_path.exists() or process_log.exists():
        fail("RAW_TSV and PROCESS_LOG must not already exist")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail("SOURCE_COMMIT must be a 40-character lowercase SHA-1")
    if cpu != "0":
        fail("recorded runs require CPU 0")

    with raw_path.open("x", encoding="utf-8", newline="") as raw_file, process_log.open(
        "x", encoding="utf-8"
    ) as log_file:
        writer = csv.writer(raw_file, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        log_file.write(
            "SESSION_START "
            f"source_commit={source_commit} cpu={cpu} blocks={len(SCHEDULE)} "
            f"modes={len(MODES)}\n"
        )
        raw_file.flush()
        log_file.flush()

        for block, order in enumerate(SCHEDULE, start=1):
            for position, mode in enumerate(order, start=1):
                run_id = f"b{block:02}-p{position}"
                log_file.write(
                    f"PROCESS_START run_id={run_id} block={block} "
                    f"position={position} mode={mode}\n"
                )
                log_file.flush()
                started = time.monotonic_ns()
                completed = subprocess.run(
                    [
                        "taskset",
                        "--cpu-list",
                        cpu,
                        str(binary),
                        run_id,
                        str(block),
                        str(position),
                        mode,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
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
                    block=block,
                    position=position,
                    mode=mode,
                )
                internal_ns = sum(int(fields[index]) for index in (17, 18, 19))
                if external_wall_ns < internal_ns:
                    fail(f"{run_id}: external wall time does not cover internal phases")
                writer.writerow([*fields, external_wall_ns])
                raw_file.flush()
                log_file.write(
                    f"PROCESS_END run_id={run_id} external_wall_ns={external_wall_ns}\n"
                )
                log_file.flush()

        log_file.write(f"SESSION_END processes={len(SCHEDULE) * len(MODES)}\n")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-schedule":
        print_schedule()
        return
    if len(sys.argv) != 6:
        fail(
            f"usage: {Path(sys.argv[0]).name} "
            "BINARY RAW_TSV PROCESS_LOG SOURCE_COMMIT CPU"
        )
    binary = Path(sys.argv[1])
    raw_path = Path(sys.argv[2])
    process_log = Path(sys.argv[3])
    run(binary, raw_path, process_log, sys.argv[4], sys.argv[5])


if __name__ == "__main__":
    main()
