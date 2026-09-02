#!/usr/bin/env python3
"""Run fixed Topic 53 process blocks and retain every raw observation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, NoReturn


BLOCK_BYTES = 4096
MASK64 = (1 << 64) - 1
# Bound on the post-SIGKILL wait. A probe blocked in an uninterruptible kernel
# sleep on the block path cannot die until that I/O settles, so an unbounded
# wait here would hang the whole campaign instead of failing the attempt.
KILL_GRACE_SECONDS = 30.0
BASE_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/bin:/usr/bin",
    "TZ": "UTC",
}
VMSTAT_KEYS = ("pgpgin", "pgpgout", "nr_dirty", "nr_writeback")
DEVICE_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")
SCENARIOS: dict[str, dict[str, object]] = {
    "depth": {
        "templates": (
            "ABBA",
            "BAAB",
            "ABBA",
            "BAAB",
            "BAAB",
            "ABBA",
            "BAAB",
            "ABBA",
        ),
        "seed_base": 530100,
        "treatments": {
            "A": {"mode": "direct", "depth": 1, "label_prefix": "q1"},
            "B": {"mode": "direct", "depth": 8, "label_prefix": "q8"},
        },
    },
    "aa": {
        "templates": (
            "XYYX",
            "YXXY",
            "XYYX",
            "YXXY",
            "YXXY",
            "XYYX",
            "YXXY",
            "XYYX",
        ),
        "seed_base": 530200,
        "treatments": {
            "X": {"mode": "direct", "depth": 1, "label_prefix": "aa-x"},
            "Y": {"mode": "direct", "depth": 1, "label_prefix": "aa-y"},
        },
    },
}


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(token: str) -> NoReturn:
    _fail(f"non-finite JSON number: {token}")


def _strict_json_line(text: str) -> dict[str, Any]:
    if not text.endswith("\n") or len(text.splitlines()) != 1:
        _fail("native stdout must contain one newline-terminated JSON object")
    value = json.loads(
        text,
        object_pairs_hook=_reject_pairs,
        parse_constant=_reject_constant,
    )
    if not isinstance(value, dict):
        _fail("native stdout is not a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as destination:
        json.dump(value, destination, indent=2, sort_keys=True)
        destination.write("\n")


def _write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as destination:
        destination.write(value)


def _append_jsonl(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as destination:
        destination.write(json.dumps(value, sort_keys=True) + "\n")
        destination.flush()
        os.fsync(destination.fileno())


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        return f"unavailable:{error.errno}\n"


def _cgroup_path() -> tuple[str, Path]:
    for line in Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
        if line.startswith("0::"):
            relative = line[3:] or "/"
            return relative, Path("/sys/fs/cgroup") / relative.lstrip("/")
    return "unavailable", Path("/sys/fs/cgroup")


def _read_vmstat() -> dict[str, int]:
    selected: dict[str, int] = {}
    with Path("/proc/vmstat").open(encoding="utf-8") as source:
        for line in source:
            fields = line.split()
            if len(fields) == 2 and fields[0] in VMSTAT_KEYS:
                selected[fields[0]] = int(fields[1])
    if set(selected) != set(VMSTAT_KEYS):
        _fail("/proc/vmstat lacks a required counter")
    return selected


def _read_devices(devices: tuple[str, ...]) -> dict[str, dict[str, list[int]]]:
    values: dict[str, dict[str, list[int]]] = {}
    for device in devices:
        root = Path("/sys/class/block") / device
        status = [int(item) for item in (root / "stat").read_text().split()]
        inflight = [int(item) for item in (root / "inflight").read_text().split()]
        if len(status) < 11:
            _fail(f"{device}: block stat has fewer than 11 fields")
        if len(inflight) != 2:
            _fail(f"{device}: inflight must contain read and write counts")
        values[device] = {"stat": status, "inflight": inflight}
    return values


def _snapshot(phase: str, devices: tuple[str, ...]) -> dict[str, object]:
    cgroup_name, cgroup_root = _cgroup_path()
    return {
        "schema": "topic53-snapshot.v1",
        "phase": phase,
        "wall_time_ns": time.time_ns(),
        "monotonic_ns": time.monotonic_ns(),
        "proc_diskstats": Path("/proc/diskstats").read_text(encoding="utf-8"),
        "proc_pressure_io": Path("/proc/pressure/io").read_text(encoding="utf-8"),
        "proc_vmstat": _read_vmstat(),
        "cgroup_path": cgroup_name,
        "cgroup_io_stat": _read_text(cgroup_root / "io.stat"),
        "cgroup_io_pressure": _read_text(cgroup_root / "io.pressure"),
        "devices": _read_devices(devices),
    }


def _psi_totals(text: str) -> dict[str, int]:
    totals: dict[str, int] = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        total = next((item[6:] for item in fields[1:] if item.startswith("total=")), None)
        if total is None:
            _fail("pressure line lacks total")
        totals[fields[0]] = int(total)
    if set(totals) != {"some", "full"}:
        _fail("I/O pressure data lacks some or full totals")
    return totals


def _subtract(after: list[int], before: list[int], label: str) -> list[int]:
    if len(after) != len(before):
        _fail(f"{label}: counter field count changed")
    return [right - left for left, right in zip(before, after)]


def _counter_deltas(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, object]:
    before_devices = before["devices"]
    after_devices = after["devices"]
    if before_devices.keys() != after_devices.keys():
        _fail("device set changed during one process")
    device_deltas = {}
    for device in before_devices:
        device_deltas[device] = {
            "stat": _subtract(
                after_devices[device]["stat"],
                before_devices[device]["stat"],
                f"{device} stat",
            ),
            "inflight": _subtract(
                after_devices[device]["inflight"],
                before_devices[device]["inflight"],
                f"{device} inflight",
            ),
        }
    psi_before = _psi_totals(before["proc_pressure_io"])
    psi_after = _psi_totals(after["proc_pressure_io"])
    return {
        "devices": device_deltas,
        "psi_total_us": {
            key: psi_after[key] - psi_before[key] for key in ("some", "full")
        },
        "vmstat": {
            key: after["proc_vmstat"][key] - before["proc_vmstat"][key]
            for key in VMSTAT_KEYS
        },
    }


def _mix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return (value ^ (value >> 31)) & MASK64


def _expected_word(block: int, word: int) -> int:
    value = _mix64(block ^ ((word * 0xD6E8FEB86659FD93) & MASK64))
    return 0x6A09E667F3BCC909 if value == 0 else value


def _expected_checksum(operations: int, blocks: int, seed: int) -> int:
    checksum = 0
    indexes = (0, BLOCK_BYTES // 16, BLOCK_BYTES // 8 - 1)
    for operation in range(operations):
        block = ((operation * 0xD1342543DE82EF95) + seed) & (blocks - 1)
        sample = _mix64(block)
        for word in indexes:
            sample ^= _expected_word(block, word)
        checksum ^= sample
    return checksum


def _validate_observed(
    observed: dict[str, Any],
    *,
    pid: int,
    label: str,
    depth: int,
    operations: int,
    seed: int,
    file_bytes: int,
) -> list[str]:
    errors: list[str] = []
    blocks = file_bytes // BLOCK_BYTES
    expected = {
        "schema": "topic53-probe.v1",
        "kind": "bench",
        "status": "ok",
        "pid": pid,
        "tid": pid,
        "threads_before": 1,
        "threads_after": 1,
        "mode": "direct",
        "label": label,
        "seed": seed,
        "depth": depth,
        "total_ops": operations,
        "bytes": operations * BLOCK_BYTES,
        "blocks": blocks,
        "read_bytes_delta": operations * BLOCK_BYTES,
        "verified_reads": operations,
        "errors": 0,
        "checksum": _expected_checksum(operations, blocks, seed),
        "peak_outstanding": depth,
        "resident_before": 0,
        "resident_after": 0,
        "total_pages": 0,
        "dioalign_known": 1,
    }
    for key, wanted in expected.items():
        if observed.get(key) != wanted:
            errors.append(f"{key}: expected {wanted!r}, got {observed.get(key)!r}")
    for key in ("startup_to_measure_ns", "setup_ns", "elapsed_ns"):
        value = observed.get(key)
        if type(value) is not int or value <= 0:
            errors.append(f"{key}: expected a positive integer")
    for key in ("iops", "mib_s"):
        value = observed.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            errors.append(f"{key}: expected a positive finite number")
    memory = observed.get("dio_mem_align")
    offset = observed.get("dio_offset_align")
    allocation = observed.get("dio_allocation_align")
    if (
        type(memory) is not int
        or memory <= 0
        or type(offset) is not int
        or offset <= 0
        or type(allocation) is not int
        or allocation < memory
        or allocation & (allocation - 1)
        or BLOCK_BYTES % offset
    ):
        errors.append("direct-I/O alignment evidence is invalid")
    for key in ("nvcsw", "nivcsw"):
        value = observed.get(key)
        if type(value) is not int or value < 0:
            errors.append(f"{key}: expected a nonnegative integer")
    return errors


def _run_attempt(
    *,
    binary: Path,
    data: Path,
    output: Path,
    journal: Path,
    attempts: Path,
    failures: Path,
    devices: tuple[str, ...],
    source_sha256: str,
    binary_sha256: str,
    scenario: str,
    sequence: int,
    block: int,
    period: int,
    template: str,
    letter: str,
    mode: str,
    depth: int,
    seed: int,
    label: str,
    operations: int,
    file_bytes: int,
    timeout_seconds: float,
    seen_pids: frozenset[int],
) -> tuple[dict[str, Any], int]:
    raw = output / "raw"
    stem = f"{sequence:03d}-b{block:02d}-p{period}-{label}"
    before_path = raw / f"{stem}.before.json"
    stdout_path = raw / f"{stem}.stdout"
    stderr_path = raw / f"{stem}.stderr"
    after_path = raw / f"{stem}.after.json"
    status_path = raw / f"{stem}.status.json"
    planned = {
        "event": "planned",
        "scenario": scenario,
        "sequence": sequence,
        "block": block,
        "period": period,
        "template": template,
        "letter": letter,
        "mode": mode,
        "depth": depth,
        "seed": seed,
        "label": label,
        "ops": operations,
    }
    _append_jsonl(journal, planned)
    before = _snapshot("before", devices)
    _write_json(before_path, before)
    argv = [
        str(binary),
        "run",
        str(data),
        mode,
        str(operations),
        str(depth),
        str(seed),
        label,
    ]
    started = time.monotonic_ns()
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=BASE_ENVIRONMENT,
    )
    timed_out = False
    kill_escaped = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        try:
            stdout, stderr = process.communicate(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            kill_escaped = True
            stdout, stderr = "", ""
    ended = time.monotonic_ns()
    _write_text(stdout_path, stdout)
    _write_text(stderr_path, stderr)
    after = _snapshot("after", devices)
    _write_json(after_path, after)

    validation_errors: list[str] = []
    observed: dict[str, Any] | None = None
    if process.pid in seen_pids:
        validation_errors.append(f"process identifier reused: {process.pid}")
    if timed_out:
        validation_errors.append("native process timed out")
    if kill_escaped:
        validation_errors.append(
            f"native process outlived SIGKILL by {KILL_GRACE_SECONDS:g}s; output abandoned"
        )
    if process.returncode != 0:
        validation_errors.append(f"native return code is {process.returncode}")
    if stderr:
        validation_errors.append("native stderr is not empty")
    try:
        observed = _strict_json_line(stdout)
        validation_errors.extend(
            _validate_observed(
                observed,
                pid=process.pid,
                label=label,
                depth=depth,
                operations=operations,
                seed=seed,
                file_bytes=file_bytes,
            )
        )
    except (ValueError, json.JSONDecodeError) as error:
        validation_errors.append(f"native output validation failed: {error}")
    status: dict[str, Any] = {
        "schema": "topic53-attempt-status.v1",
        "scenario": scenario,
        "sequence": sequence,
        "block": block,
        "period": period,
        "template": template,
        "letter": letter,
        "mode": mode,
        "depth": depth,
        "seed": seed,
        "label": label,
        "ops": operations,
        "source_sha256": source_sha256,
        "binary_sha256": binary_sha256,
        "pid": process.pid,
        "returncode": process.returncode,
        "timed_out": timed_out,
        "wall_elapsed_ns": ended - started,
        "stdout_sha256": _sha256(stdout_path),
        "stderr_sha256": _sha256(stderr_path),
        "before_sha256": _sha256(before_path),
        "after_sha256": _sha256(after_path),
        "valid": not validation_errors,
        "validation_errors": validation_errors,
        "observed": observed,
        "counter_deltas": _counter_deltas(before, after),
    }
    _write_json(status_path, status)
    attempt = {
        **status,
        "schema": "topic53-attempt.v1",
        "before_file": before_path.relative_to(output).as_posix(),
        "stdout_file": stdout_path.relative_to(output).as_posix(),
        "stderr_file": stderr_path.relative_to(output).as_posix(),
        "after_file": after_path.relative_to(output).as_posix(),
        "status_file": status_path.relative_to(output).as_posix(),
    }
    _append_jsonl(attempts, attempt)
    _append_jsonl(
        journal,
        {
            "event": "completed",
            "scenario": scenario,
            "sequence": sequence,
            "returncode": process.returncode,
            "timed_out": timed_out,
            "valid": not validation_errors,
            "status_file": status_path.relative_to(output).as_posix(),
            "status_sha256": _sha256(status_path),
        },
    )
    if validation_errors:
        _append_jsonl(failures, attempt)
    return attempt, process.pid


def main() -> int:
    """Run one fixed scenario and return zero only for a complete campaign."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scenario", required=True, choices=tuple(SCENARIOS))
    parser.add_argument("--devices", required=True)
    parser.add_argument("--primary-device", required=True)
    parser.add_argument("--ops", required=True, type=int)
    parser.add_argument("--file-bytes", required=True, type=int)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    args = parser.parse_args()

    binary = args.binary.resolve(strict=True)
    source = args.source.resolve(strict=True)
    data = args.data.resolve(strict=True)
    if not data.is_file() or data.stat().st_size != args.file_bytes:
        parser.error("data file size differs from --file-bytes")
    if args.file_bytes <= 0 or args.file_bytes % BLOCK_BYTES:
        parser.error("--file-bytes must be a positive multiple of 4096")
    blocks = args.file_bytes // BLOCK_BYTES
    if blocks & (blocks - 1):
        parser.error("data file must contain a power-of-two block count")
    if args.ops <= 0 or args.ops > blocks:
        parser.error("--ops must fit the file's unique block count")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    devices = tuple(item for item in args.devices.split(",") if item)
    if not devices or len(set(devices)) != len(devices):
        parser.error("--devices must name unique block devices")
    if any(DEVICE_NAME.fullmatch(device) is None for device in devices):
        parser.error("--devices contains an invalid Linux block-device name")
    if args.primary_device not in devices:
        parser.error("--primary-device must appear in --devices")
    for device in devices:
        if not (Path("/sys/class/block") / device).is_dir():
            parser.error(f"block device is absent from sysfs: {device}")

    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    (output / "raw").mkdir(mode=0o700)
    config = SCENARIOS[args.scenario]
    templates = config["templates"]
    treatments = config["treatments"]
    seed_base = config["seed_base"]
    assert isinstance(templates, tuple)
    assert isinstance(treatments, dict)
    assert isinstance(seed_base, int)
    source_sha256 = _sha256(source)
    binary_sha256 = _sha256(binary)
    schedule = {
        "schema": "topic53-schedule.v1",
        "scenario": args.scenario,
        "templates": list(templates),
        "treatments": treatments,
        "seed_base": seed_base,
        "blocks": len(templates),
        "processes_per_block": 4,
        "ops_per_process": args.ops,
        "block_bytes": BLOCK_BYTES,
        "data_file_bytes": args.file_bytes,
        "source_sha256": source_sha256,
        "binary_sha256": binary_sha256,
        "devices": list(devices),
        "primary_device": args.primary_device,
        "treatment_application_unit": "fresh native process",
        "analysis_unit": "complete four-process block",
        "subsample_unit": "one verified 4 KiB O_DIRECT read",
        "stopping": "fixed horizon; stop after first invalid attempt",
    }
    _write_json(output / "schedule.json", schedule)
    journal = output / "attempt-journal.jsonl"
    attempts = output / "attempts.jsonl"
    failures = output / "failures.jsonl"
    seen_pids: set[int] = set()
    sequence = 0
    for block, template in enumerate(templates, 1):
        seed = seed_base + block
        for period, letter in enumerate(template, 1):
            sequence += 1
            treatment = treatments[letter]
            mode = treatment["mode"]
            depth = treatment["depth"]
            prefix = treatment["label_prefix"]
            assert isinstance(mode, str)
            assert isinstance(depth, int)
            assert isinstance(prefix, str)
            label = f"{prefix}-b{block:02d}-p{period}"
            attempt, pid = _run_attempt(
                binary=binary,
                data=data,
                output=output,
                journal=journal,
                attempts=attempts,
                failures=failures,
                devices=devices,
                source_sha256=source_sha256,
                binary_sha256=binary_sha256,
                scenario=args.scenario,
                sequence=sequence,
                block=block,
                period=period,
                template=template,
                letter=letter,
                mode=mode,
                depth=depth,
                seed=seed,
                label=label,
                operations=args.ops,
                file_bytes=args.file_bytes,
                timeout_seconds=args.timeout_seconds,
                seen_pids=frozenset(seen_pids),
            )
            if pid in seen_pids:
                _fail(f"process identifier reused: {pid}")
            seen_pids.add(pid)
            if attempt["valid"] is not True:
                _fail(f"invalid attempt {sequence}; campaign stopped without replacement")

    _write_json(
        output / "COMPLETE.json",
        {
            "schema": "topic53-scenario-complete.v1",
            "scenario": args.scenario,
            "attempt_count": sequence,
            "unique_pid_count": len(seen_pids),
            "complete_block_count": len(templates),
            "invalid_attempt_count": 0,
            "source_sha256": source_sha256,
            "binary_sha256": binary_sha256,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"run_processes.py: {error}", file=sys.stderr)
        raise SystemExit(1) from error
