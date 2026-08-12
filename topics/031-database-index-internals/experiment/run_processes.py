#!/usr/bin/env python3
"""Run paired fresh-process index-layout measurements without dependencies."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

SEED = 31082026
RESULT_INT_FIELDS = (
    "entries",
    "queries",
    "reps",
    "lookups",
    "setup_ns",
    "nonsteady_ns",
    "steady_ns",
    "checksum",
    "logical_narrow_index",
    "logical_heap",
    "logical_covering_index",
    "rust_narrow_entry",
    "rust_payload",
    "rust_covering_entry",
)
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
    parser.add_argument("--cpu", type=int, default=None)
    parser.add_argument("--entries", type=int, default=1 << 20)
    parser.add_argument("--queries", type=int, default=1 << 16)
    parser.add_argument("--reps", type=int, default=8)
    return parser.parse_args()


def result_matches_contract(
    parsed: object, treatment: str, args: argparse.Namespace
) -> bool:
    """Reject probe output that is incomplete or contradicts the run contract."""

    if not isinstance(parsed, dict) or parsed.get("treatment") != treatment:
        return False
    for field in RESULT_INT_FIELDS:
        value = parsed.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            return False
    ns_per_lookup = parsed.get("ns_per_lookup")
    if not isinstance(ns_per_lookup, float) or not math.isfinite(ns_per_lookup):
        return False
    if ns_per_lookup <= 0:
        return False
    lookups = parsed["lookups"]
    if lookups <= 0 or lookups != parsed["queries"] * parsed["reps"]:
        return False
    if not math.isclose(
        ns_per_lookup, parsed["steady_ns"] / lookups, rel_tol=1e-9, abs_tol=1e-6
    ):
        return False
    return (
        parsed["entries"] == args.entries
        and parsed["queries"] == args.queries
        and parsed["reps"] == args.reps
    )


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
    if args.entries & (args.entries - 1):
        raise SystemExit("--entries must be a power of two")
    prefix: list[str] = []
    if sys.platform.startswith("linux") and shutil.which("taskset"):
        # Default to an allowed CPU because taskset rejects CPUs outside the
        # affinity mask before the probe starts.
        allowed = sorted(os.sched_getaffinity(0))
        cpu = allowed[0] if args.cpu is None else args.cpu
        if cpu not in allowed:
            raise SystemExit(f"--cpu {cpu} is outside the allowed CPUs {allowed}")
        args.cpu = cpu
        prefix = ["taskset", "-c", str(cpu)]

    args.output.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "TOPIC31_ENTRIES": str(args.entries),
            "TOPIC31_QUERIES": str(args.queries),
            "TOPIC31_REPS": str(args.reps),
        }
    )
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

    failures = 1 if check.returncode != 0 else 0
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
                if completed.returncode != 0 or not result_matches_contract(
                    parsed, treatment, args
                ):
                    failures += 1

    print(
        f"retained {args.blocks * 4} fresh processes in {args.output}; "
        f"failures={failures}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
