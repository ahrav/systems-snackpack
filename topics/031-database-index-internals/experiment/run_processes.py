#!/usr/bin/env python3
"""Run paired fresh-process index-layout measurements without dependencies."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


SEED = 31082026
ORDERS = ("narrow", "covering", "covering", "narrow"), (
    "covering",
    "narrow",
    "narrow",
    "covering",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--entries", type=int, default=1 << 20)
    parser.add_argument("--queries", type=int, default=1 << 16)
    parser.add_argument("--reps", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        raise SystemExit(f"binary does not exist: {binary}")
    if args.output.exists():
        raise SystemExit(f"output must not exist: {args.output}")
    if args.blocks <= 0 or args.blocks % 2:
        raise SystemExit("--blocks must be a positive even number")
    for name in ("entries", "queries", "reps"):
        if getattr(args, name) <= 0:
            raise SystemExit(f"--{name} must be positive")

    args.output.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "TOPIC31_ENTRIES": str(args.entries),
            "TOPIC31_QUERIES": str(args.queries),
            "TOPIC31_REPS": str(args.reps),
        }
    )
    prefix: list[str] = []
    if sys.platform.startswith("linux") and shutil.which("taskset"):
        prefix = ["taskset", "-c", str(args.cpu)]

    metadata = {
        "protocol": "topic31-paired-v1",
        "seed": SEED,
        "binary": str(binary),
        "blocks": args.blocks,
        "processes": args.blocks * 4,
        "cpu": args.cpu if prefix else None,
        "pin_command": prefix,
        "entries": args.entries,
        "queries": args.queries,
        "reps": args.reps,
        "platform": platform.platform(),
        "python": sys.version,
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    check = subprocess.run(
        prefix + [str(binary), "check"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    (args.output / "check.json").write_text(
        json.dumps(
            {
                "command": prefix + [str(binary), "check"],
                "exit_code": check.returncode,
                "stdout": check.stdout,
                "stderr": check.stderr,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    failures = int(check.returncode != 0)
    runs_path = args.output / "runs.jsonl"
    with runs_path.open("w", encoding="utf-8") as runs_file:
        for block in range(args.blocks):
            order_id = "ABBA" if block % 2 == 0 else "BAAB"
            order = ORDERS[block % 2]
            for slot, treatment in enumerate(order):
                command = prefix + [str(binary), treatment]
                started = time.perf_counter_ns()
                completed = subprocess.run(
                    command,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                wall_ns = time.perf_counter_ns() - started
                parsed = None
                try:
                    lines = [line for line in completed.stdout.splitlines() if line]
                    parsed = json.loads(lines[-1]) if lines else None
                except (json.JSONDecodeError, IndexError):
                    parsed = None
                record = {
                    "block": block,
                    "order": order_id,
                    "slot": slot,
                    "treatment": treatment,
                    "command": command,
                    "exit_code": completed.returncode,
                    "wall_ns": wall_ns,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "result": parsed,
                }
                runs_file.write(json.dumps(record, sort_keys=True) + "\n")
                runs_file.flush()
                if completed.returncode != 0 or parsed is None:
                    failures += 1

    print(
        f"retained {args.blocks * 4} fresh processes in {args.output}; "
        f"failures={failures}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
