#!/usr/bin/env python3
"""Run correctness checks and a no-retry fresh-process transfer schedule."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedule import ScheduledRun, make_schedule  # noqa: E402


RESULT_FIELDS = (
    "method",
    "bytes",
    "verify",
    "chunk",
    "transfer_sec",
    "setup_sec",
    "total_sec",
    "gib_per_sec",
    "sender_cpu_sec",
    "receiver_cpu_sec",
    "input_calls",
    "output_calls",
    "recv_calls",
    "pipe_capacity",
    "sndbuf",
    "rcvbuf",
    "sender_cpu",
    "receiver_cpu",
    "transfer_errno",
    "receiver_status",
    "received_bytes",
    "mismatch_offset",
    "expected",
    "observed",
    "ok",
)


def digest(data: bytes) -> str:
    """Return a hexadecimal SHA-256 digest."""

    return hashlib.sha256(data).hexdigest()


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest for a file."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_result(stdout: bytes) -> dict[str, str]:
    """Parse the probe's one machine-readable result line."""

    lines = [line for line in stdout.decode("utf-8", errors="strict").splitlines() if line]
    if len(lines) != 1 or not lines[0].startswith("result "):
        raise ValueError("probe did not emit exactly one result record")
    fields: dict[str, str] = {}
    for token in lines[0].split()[1:]:
        if "=" not in token:
            raise ValueError(f"result token lacks '=': {token}")
        key, value = token.split("=", 1)
        if key in fields:
            raise ValueError(f"duplicate result field: {key}")
        fields[key] = value
    if tuple(fields) != RESULT_FIELDS:
        raise ValueError(f"result schema changed: {tuple(fields)}")
    return fields


def command_prefix(cpu_list: str | None) -> list[str]:
    """Return the optional fixed-affinity launcher."""

    return ["taskset", "-c", cpu_list] if cpu_list else []


def run_control(
    argv: list[str],
    stdout_path: Path,
    stderr_path: Path,
    *,
    expected_result: bool,
) -> tuple[int, int, dict[str, str] | None]:
    """Run one process once, retain both streams, and return outer time."""

    started = time.monotonic_ns()
    completed = subprocess.run(argv, check=False, capture_output=True)
    outer_ns = time.monotonic_ns() - started
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    try:
        parsed = parse_result(completed.stdout) if expected_result else None
    except ValueError as error:
        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(
            f"{error} (exit code {completed.returncode}; stderr: {stderr_text[:500]!r})"
        ) from error
    return completed.returncode, outer_ns, parsed


def schedule_dict(row: ScheduledRun) -> dict[str, str]:
    """Convert one immutable scheduled run into text fields."""

    return {name: str(value) for name, value in row.__dict__.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bytes", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--correctness-bytes", type=int, default=16_777_219)
    parser.add_argument("--chunk", type=int, default=256 * 1024)
    parser.add_argument("--seed", type=int, default=38_017)
    parser.add_argument("--blocks", type=int, default=8)
    parser.add_argument("--cpu-list")
    arguments = parser.parse_args()
    # Resolve once so the hashed file, the recorded path, and every executed
    # command name the same binary; a bare filename would otherwise be hashed
    # from the working directory but executed through PATH lookup.
    arguments.binary = arguments.binary.resolve()

    if arguments.output.exists():
        parser.error(f"output already exists: {arguments.output}")
    if arguments.payload.exists():
        parser.error(f"payload already exists: {arguments.payload}")
    for value_name in ("bytes", "correctness_bytes", "chunk"):
        if getattr(arguments, value_name) <= 0:
            parser.error(f"--{value_name.replace('_', '-')} must be positive")

    arguments.output.mkdir(parents=True)
    raw_dir = arguments.output / "raw"
    raw_dir.mkdir()
    prefix = command_prefix(arguments.cpu_list)
    configuration = {
        "binary": str(arguments.binary.resolve()),
        "binary_sha256": digest_path(arguments.binary),
        "payload": str(arguments.payload.resolve()),
        "bytes": arguments.bytes,
        "correctness_bytes": arguments.correctness_bytes,
        "chunk": arguments.chunk,
        "seed": arguments.seed,
        "blocks": arguments.blocks,
        "cpu_list": arguments.cpu_list,
        "python": sys.version,
        "process_unit": "one fresh transfer-probe invocation",
        "retry_policy": "none",
        "transfer_timer_boundary": (
            "socket and input file setup excluded; buffered allocation/free and "
            "splice pipe create/close included"
        ),
    }
    (arguments.output / "run-config.json").write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    prepare = [str(arguments.binary), "prepare", str(arguments.payload), str(arguments.bytes)]
    completed = subprocess.run(prepare, check=False, capture_output=True)
    (raw_dir / "prepare.stdout").write_bytes(completed.stdout)
    (raw_dir / "prepare.stderr").write_bytes(completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"payload preparation failed with {completed.returncode}")

    warm = [str(arguments.binary), "warm", str(arguments.payload)]
    completed = subprocess.run(warm, check=False, capture_output=True)
    (raw_dir / "warm.stdout").write_bytes(completed.stdout)
    (raw_dir / "warm.stderr").write_bytes(completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"payload warmup failed with {completed.returncode}")

    correctness_rows: list[dict[str, str]] = []
    for method in ("buffered", "sendfile", "splice"):
        argv = prefix + [
            str(arguments.binary),
            "run",
            method,
            str(arguments.payload),
            str(arguments.correctness_bytes),
            "1",
            str(arguments.chunk),
        ]
        stdout_path = raw_dir / f"correctness-{method}.stdout"
        stderr_path = raw_dir / f"correctness-{method}.stderr"
        rc, outer_ns, parsed = run_control(
            argv,
            stdout_path,
            stderr_path,
            expected_result=True,
        )
        assert parsed is not None
        correctness_rows.append(
            {
                "method": method,
                "argv_json": json.dumps(argv, separators=(",", ":")),
                "rc": str(rc),
                "outer_ns": str(outer_ns),
                "stdout_sha256": digest(stdout_path.read_bytes()),
                "stderr_sha256": digest(stderr_path.read_bytes()),
                **parsed,
            }
        )
        if rc != 0 or parsed["ok"] != "1" or parsed["verify"] != "1":
            raise RuntimeError(f"correctness process failed for {method}")

    with (arguments.output / "correctness.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(correctness_rows[0]))
        writer.writeheader()
        writer.writerows(correctness_rows)

    schedule = make_schedule(arguments.seed, arguments.blocks)
    with (arguments.output / "schedule.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(ScheduledRun.__annotations__))
        writer.writeheader()
        writer.writerows(row.__dict__ for row in schedule)

    run_rows: list[dict[str, str]] = []
    for sequence, scheduled in enumerate(schedule, 1):
        run_id = (
            f"{sequence:03d}-{scheduled.pair}-b{scheduled.block:02d}-"
            f"p{scheduled.position}-{scheduled.label}-{scheduled.method}"
        )
        argv = prefix + [
            str(arguments.binary),
            "run",
            scheduled.method,
            str(arguments.payload),
            str(arguments.bytes),
            "0",
            str(arguments.chunk),
        ]
        stdout_path = raw_dir / f"{run_id}.stdout"
        stderr_path = raw_dir / f"{run_id}.stderr"
        rc, outer_ns, parsed = run_control(argv, stdout_path, stderr_path, expected_result=True)
        assert parsed is not None
        row = {
            "run_id": run_id,
            "sequence": str(sequence),
            **schedule_dict(scheduled),
            "argv_json": json.dumps(argv, separators=(",", ":")),
            "rc": str(rc),
            "outer_ns": str(outer_ns),
            "stdout_sha256": digest(stdout_path.read_bytes()),
            "stderr_sha256": digest(stderr_path.read_bytes()),
            **parsed,
        }
        run_rows.append(row)
        if (
            rc != 0
            or parsed["ok"] != "1"
            or parsed["verify"] != "0"
            or parsed["method"] != scheduled.method
            or int(parsed["bytes"]) != arguments.bytes
        ):
            raise RuntimeError(f"timing process failed for {run_id}")

    with (arguments.output / "runs.tsv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(run_rows[0]))
        writer.writeheader()
        writer.writerows(run_rows)

    payload_receipt = {
        "size": arguments.payload.stat().st_size,
        "sha256": digest_path(arguments.payload),
    }
    (arguments.output / "payload.json").write_text(
        json.dumps(payload_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"RUNS=PASS process_runs={len(run_rows)} correctness_runs={len(correctness_rows)} "
        f"blocks={arguments.blocks} seed={arguments.seed}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR={error}", file=sys.stderr)
        raise SystemExit(1) from error
