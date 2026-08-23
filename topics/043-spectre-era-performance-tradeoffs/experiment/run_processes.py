#!/usr/bin/env python3
"""Run the fixed 24-block, six-permutation Topic 43 comparison."""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

from probe_environment import PROBE_ENVIRONMENT, probe_timeout_seconds

BLOCKS = 24
DEFAULT_ITERATIONS = 20_000_000
WORKLOAD_SEED = 0x243F_6A88_85A3_08D3
SCHEDULE_SEED = 0x43_2026_08_22
PERMUTATIONS = [
    ("plain", "mask", "barrier"),
    ("plain", "barrier", "mask"),
    ("mask", "plain", "barrier"),
    ("mask", "barrier", "plain"),
    ("barrier", "plain", "mask"),
    ("barrier", "mask", "plain"),
]


def fixed_schedule() -> list[tuple[str, str, str]]:
    schedule = PERMUTATIONS * 4
    random.Random(SCHEDULE_SEED).shuffle(schedule)
    return schedule


def partial_text(output: bytes | str | None) -> str:
    """TimeoutExpired retains captured output as raw bytes even when the
    process ran in text mode; normalize so the record stays JSON-serializable."""

    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def run_one(
    binary: Path,
    cpu: int,
    iterations: int,
    block: int,
    ordinal: int,
    mode: str,
    permutation: tuple[str, str, str],
) -> dict:
    command = [
        "taskset",
        "--cpu-list",
        str(cpu),
        str(binary),
        "--mode",
        mode,
        "--iterations",
        str(iterations),
        "--seed",
        hex(WORKLOAD_SEED),
    ]
    timeout_seconds = probe_timeout_seconds(iterations)
    started_ns = time.time_ns()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=PROBE_ENVIRONMENT,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        stdout = partial_text(error.stdout)
        stderr = partial_text(error.stderr)
    result = None
    valid = False
    try:
        lines = [line for line in stdout.splitlines() if line.strip()]
        if exit_code == 0 and len(lines) == 1:
            result = json.loads(lines[0])
            valid = isinstance(result, dict)
    except json.JSONDecodeError:
        pass
    return {
        "phase": "timing",
        "block": block,
        "ordinal": ordinal,
        "mode": mode,
        "permutation": list(permutation),
        "workload_seed": WORKLOAD_SEED,
        "schedule_seed": SCHEDULE_SEED,
        "iterations": iterations,
        "cpu": cpu,
        "command": command,
        "environment": PROBE_ENVIRONMENT,
        "timeout_seconds": timeout_seconds,
        "started_unix_ns": started_ns,
        "wall_ns": time.time_ns() - started_ns,
        "exit_code": exit_code,
        "valid": valid,
        "result": result,
        "stdout": stdout,
        "stderr": stderr,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    args = parser.parse_args()
    if args.iterations <= 0 or args.cpu < 0 or not args.binary.is_file():
        raise SystemExit("binary, CPU, and iterations must name valid fixed inputs")
    if args.output.exists() or args.summary.exists():
        raise SystemExit("output paths must not exist")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for block, permutation in enumerate(fixed_schedule(), 1):
            for ordinal, mode in enumerate(permutation, 1):
                record = run_one(
                    args.binary.resolve(), args.cpu, args.iterations, block, ordinal, mode, permutation
                )
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
    analyzer = Path(__file__).with_name("analyze.py")
    subprocess.run(
        [sys.executable, str(analyzer), "--kind", "timing", "--input", str(args.output), "--output", str(args.summary)],
        check=True,
    )


if __name__ == "__main__":
    main()
