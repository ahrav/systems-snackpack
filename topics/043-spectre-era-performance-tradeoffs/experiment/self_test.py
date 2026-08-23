#!/usr/bin/env python3
"""Check deterministic equivalence across all three lookup modes."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from probe_environment import PROBE_ENVIRONMENT

MODES = ("plain", "mask", "barrier")
ITERATIONS = 200_000
SEED = 0x243F_6A88_85A3_08D3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.binary.is_file() or args.cpu < 0 or args.output.exists():
        raise SystemExit("self-test inputs must be valid and output must not exist")
    records = []
    for mode in MODES:
        command = [
            "taskset",
            "--cpu-list",
            str(args.cpu),
            str(args.binary.resolve()),
            "--mode",
            mode,
            "--iterations",
            str(ITERATIONS),
            "--seed",
            hex(SEED),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=PROBE_ENVIRONMENT,
        )
        if completed.returncode != 0:
            raise SystemExit(f"{mode} self-test failed: {completed.stderr}")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise SystemExit(f"{mode} self-test emitted {len(lines)} nonempty lines")
        result = json.loads(lines[0])
        if result.get("mode") != mode or result.get("iterations") != ITERATIONS:
            raise SystemExit(f"{mode} self-test output changed schema")
        records.append(result)
    if len({record["checksum"] for record in records}) != 1:
        raise SystemExit("timed checksums differ across modes")
    if len({record["warmup_checksum"] for record in records}) != 1:
        raise SystemExit("warmup checksums differ across modes")
    output = {
        "schema": "topic43-self-test-v1",
        "status": "pass",
        "iterations": ITERATIONS,
        "seed": SEED,
        "environment": PROBE_ENVIRONMENT,
        "records": records,
        "security_claim": "none",
    }
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
