#!/usr/bin/env python3
"""Exercise Topic 45 protocol failure paths without running the benchmark."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Force a byte-valued timeout and prove the attempted row remains serializable."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")

    runner_path = Path(__file__).resolve().parent / "run_experiment.py"
    spec = importlib.util.spec_from_file_location("topic45_runner", runner_path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load run_experiment.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    stat_values = iter((
        {"user": 1, "nice": 0, "system": 1, "idle": 10, "iowait": 0, "irq": 0, "softirq": 0, "steal": 0},
        {"user": 2, "nice": 0, "system": 1, "idle": 10, "iowait": 0, "irq": 0, "softirq": 0, "steal": 0},
    ))
    runner.read_cpu_stat = lambda _cpu: next(stat_values)

    original_run = runner.subprocess.run
    try:
        def force_timeout(command, **_kwargs):
            raise subprocess.TimeoutExpired(command, 0.001, output=b"partial stdout", stderr=b"partial stderr")

        runner.subprocess.run = force_timeout
        row = runner.invoke(Path(sys.executable), "scalar", 1, 0, 0, "A")
    finally:
        runner.subprocess.run = original_run

    encoded = json.dumps(row, sort_keys=True)
    if row["returncode"] != 124 or not row["timed_out"]:
        raise SystemExit("forced timeout did not produce a failed retained row")
    if row["stdout"] != "partial stdout" or row["stderr"] != "partial stderr":
        raise SystemExit("timeout byte output was not decoded")
    args.output.write_text(
        json.dumps({"status": "pass", "serialized_bytes": len(encoded)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
