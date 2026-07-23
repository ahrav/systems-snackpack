#!/usr/bin/env python3
"""Run one pinned workload process inside a monotonic wall-time boundary."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    if len(sys.argv) != 7:
        fail("usage: run_one.py BINARY FILE_DIR CPU MODE MIB RUN_ID")
    binary, file_dir, cpu, mode, mib, run_id = sys.argv[1:]
    if not Path(binary).is_file():
        fail(f"workload binary does not exist: {binary}")

    environment = os.environ.copy()
    environment["VM_FAULT_FILE_DIR"] = file_dir
    started = time.monotonic_ns()
    completed = subprocess.run(
        ["taskset", "-c", cpu, binary, mode, mib, run_id],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    finished = time.monotonic_ns()
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        fail(f"workload exited with status {completed.returncode}")
    rows = completed.stdout.splitlines()
    if len(rows) != 1 or rows[0].count(",") != 13:
        fail("workload did not emit exactly one 14-field CSV row")
    if completed.stderr:
        sys.stderr.write(completed.stderr)
        fail("successful workload emitted stderr")
    print(f"{rows[0]},{finished - started}")


if __name__ == "__main__":
    main()
