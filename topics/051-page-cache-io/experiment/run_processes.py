#!/usr/bin/env python3
"""Run fixed, fresh-process Topic 51 benchmark blocks without replacement."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import struct
import sys
import time
from typing import Any, NoReturn


FILE_BYTES = 16 * 1024 * 1024
IO_BLOCK = 4096
BASE_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PATH": "/bin:/usr/bin", "TZ": "UTC"}
SCENARIOS = {
    "primary": {
        "seed": 510101,
        "templates": ("ABBA", "BAAB", "ABBA", "BAAB", "BAAB", "ABBA", "BAAB", "ABBA"),
        "treatments": {"A": ("buf_seq", "seq"), "B": ("buf_random", "random")},
    },
    "aa": {
        "seed": 510102,
        "templates": ("XYYX", "YXXY", "XYYX", "YXXY", "YXXY", "XYYX", "YXXY", "XYYX"),
        "treatments": {"X": ("buf_seq", "aa_x"), "Y": ("buf_seq", "aa_y")},
    },
    "direct": {
        "seed": 510103,
        "templates": ("ABBA", "BAAB", "BAAB", "ABBA"),
        "treatments": {"A": ("buf_seq", "buffered"), "B": ("direct_seq", "direct")},
    },
}


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    fail(f"non-finite JSON number: {token}")


def strict_json_line(text: str) -> dict[str, Any]:
    if not text.endswith("\n") or len(text.splitlines()) != 1:
        fail("native stdout must contain one newline-terminated JSON object")
    value = json.loads(text, object_pairs_hook=reject_pairs, parse_constant=reject_constant)
    if not isinstance(value, dict):
        fail("native stdout is not a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as destination:
        json.dump(value, destination, indent=2, sort_keys=True)
        destination.write("\n")


def append_jsonl(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as destination:
        destination.write(json.dumps(value, sort_keys=True) + "\n")
        destination.flush()
        os.fsync(destination.fileno())


def validate_observed(
    observed: dict[str, Any], *, mode: str, label: str, seed: int, pid: int, page_count: int
) -> list[str]:
    errors: list[str] = []
    expected = {
        "kind": "bench",
        "status": "ok",
        "pid": pid,
        "mode": mode,
        "label": label,
        "seed": seed,
        "bytes": FILE_BYTES,
        "blocks": FILE_BYTES // IO_BLOCK,
        "pages": page_count,
        "resident_before": 0,
        "cold_verified": 1,
        "errors": 0,
        "read_bytes_delta": FILE_BYTES,
    }
    for key, wanted in expected.items():
        if observed.get(key) != wanted:
            errors.append(f"{key}: expected {wanted!r}, got {observed.get(key)!r}")
    for key in ("started_realtime_ns", "startup_to_measure_ns", "measurement_ns"):
        value = observed.get(key)
        if type(value) is not int or value <= 0:
            errors.append(f"{key} must be a positive integer")
    resident_after = observed.get("resident_after")
    if type(resident_after) is not int or not 0 <= resident_after <= page_count:
        errors.append(
            f"resident_after must be an integer from 0 through {page_count}, got {resident_after!r}"
        )
    elif mode != "direct_seq" and resident_after != page_count:
        errors.append(f"resident_after: expected {page_count}, got {resident_after!r}")
    if mode == "direct_seq":
        if observed.get("dio_align_reported") != 1:
            errors.append("direct I/O requires STATX_DIOALIGN evidence")
        memory_alignment = observed.get("dio_mem_align")
        allocation_alignment = observed.get("dio_allocation_align")
        offset_alignment = observed.get("dio_offset_align")
        if (
            type(memory_alignment) is not int
            or memory_alignment <= 0
            or type(allocation_alignment) is not int
            or allocation_alignment < struct.calcsize("P")
            or (allocation_alignment & (allocation_alignment - 1)) != 0
            or allocation_alignment % memory_alignment != 0
            or type(offset_alignment) is not int
            or offset_alignment <= 0
            or IO_BLOCK % offset_alignment != 0
        ):
            errors.append("direct-I/O alignment fields do not admit 4 KiB requests")
    for key, value in observed.items():
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f"{key} is non-finite")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--data-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--scenario", required=True, choices=tuple(SCENARIOS))
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-archive-sha256", required=True)
    parser.add_argument("--target-label", required=True)
    args = parser.parse_args()

    binary = args.binary.resolve(strict=True)
    data_file = args.data_file.resolve(strict=True)
    output_dir = args.output_dir.resolve(strict=False)
    if output_dir.exists():
        parser.error(f"output path already exists: {output_dir}")
    if data_file.stat().st_size != FILE_BYTES:
        parser.error(f"data file must contain exactly {FILE_BYTES} bytes")
    page_size = os.sysconf("SC_PAGE_SIZE")
    if page_size != IO_BLOCK:
        parser.error(f"publication hosts require a {IO_BLOCK}-byte page size, got {page_size}")

    config = SCENARIOS[args.scenario]
    templates = config["templates"]
    treatments = config["treatments"]
    base_seed = config["seed"]
    assert isinstance(templates, tuple)
    assert isinstance(treatments, dict)
    assert isinstance(base_seed, int)

    output_dir.mkdir(mode=0o700, parents=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(mode=0o700)
    attempts_path = output_dir / "attempts.jsonl"
    journal_path = output_dir / "attempt-journal.jsonl"
    failures_path = output_dir / "failures.jsonl"
    schedule = {
        "schema": "topic51-schedule.v1",
        "scenario": args.scenario,
        "seed": base_seed,
        "templates": list(templates),
        "treatments": {
            key: {"mode": value[0], "label_prefix": value[1]}
            for key, value in treatments.items()
        },
        "analysis_unit": "complete four-process block",
        "treatment_application_unit": "fresh native process",
        "subsample_unit": "one 4 KiB pread inside a process",
        "stopping": "fixed horizon; stop after first invalid attempt",
        "replacement": "none",
        "source_commit": args.source_commit,
        "source_archive_sha256": args.source_archive_sha256,
        "target_label": args.target_label,
        "binary_sha256": sha256(binary),
        "data_file_bytes": FILE_BYTES,
        "page_size": page_size,
    }
    write_json(output_dir / "schedule.json", schedule)

    sequence = 0
    seen_pids: set[int] = set()
    for block, template in enumerate(templates, 1):
        for period, letter in enumerate(template, 1):
            sequence += 1
            mode, prefix = treatments[letter]
            label = f"{prefix}_b{block:02d}_p{period}"
            run_seed = base_seed * 100000 + block * 100 + period
            stem = f"{sequence:03d}-block{block:02d}-p{period}-{letter}"
            stdout_path = raw_dir / f"{stem}.stdout"
            stderr_path = raw_dir / f"{stem}.stderr"
            status_path = raw_dir / f"{stem}.status.json"
            command = [str(binary), "bench", str(data_file), mode, label, str(run_seed)]
            planned = {
                "event": "planned",
                "sequence": sequence,
                "block": block,
                "period": period,
                "template": template,
                "letter": letter,
                "mode": mode,
                "label": label,
                "command": command,
                "recorded_realtime_ns": time.time_ns(),
            }
            append_jsonl(journal_path, planned)
            started = time.time_ns()
            process = subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=BASE_ENVIRONMENT,
            )
            stdout, stderr = process.communicate()
            ended = time.time_ns()
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            validation_errors: list[str] = []
            observed: dict[str, Any] | None = None
            try:
                observed = strict_json_line(stdout)
            except (ValueError, json.JSONDecodeError) as error:
                validation_errors.append(str(error))
            if process.returncode != 0:
                validation_errors.append(f"native return code is {process.returncode}")
            if process.pid in seen_pids:
                validation_errors.append(f"process identifier reused: {process.pid}")
            seen_pids.add(process.pid)
            if observed is not None:
                validation_errors.extend(
                    validate_observed(
                        observed,
                        mode=mode,
                        label=label,
                        seed=run_seed,
                        pid=process.pid,
                        page_count=FILE_BYTES // page_size,
                    )
                )
            status = {
                "schema": "topic51-attempt-status.v1",
                "sequence": sequence,
                "block": block,
                "period": period,
                "template": template,
                "letter": letter,
                "mode": mode,
                "label": label,
                "pid": process.pid,
                "started_realtime_ns": started,
                "ended_realtime_ns": ended,
                "returncode": process.returncode,
                "valid": not validation_errors,
                "validation_errors": validation_errors,
                "stdout_sha256": sha256(stdout_path),
                "stderr_sha256": sha256(stderr_path),
                "observed": observed,
            }
            write_json(status_path, status)
            attempt = {
                **status,
                "stdout_file": stdout_path.relative_to(output_dir).as_posix(),
                "stderr_file": stderr_path.relative_to(output_dir).as_posix(),
                "status_file": status_path.relative_to(output_dir).as_posix(),
            }
            append_jsonl(attempts_path, attempt)
            append_jsonl(
                journal_path,
                {
                    "event": "completed",
                    "sequence": sequence,
                    "valid": not validation_errors,
                    "recorded_realtime_ns": time.time_ns(),
                },
            )
            print(
                json.dumps(
                    {
                        "scenario": args.scenario,
                        "sequence": sequence,
                        "block": block,
                        "period": period,
                        "valid": not validation_errors,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if validation_errors:
                append_jsonl(failures_path, attempt)
                return 1

    write_json(
        output_dir / "COMPLETE.json",
        {
            "schema": "topic51-complete.v1",
            "scenario": args.scenario,
            "attempt_count": sequence,
            "unique_pid_count": len(seen_pids),
            "completed_realtime_ns": time.time_ns(),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
