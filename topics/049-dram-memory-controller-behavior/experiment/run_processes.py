#!/usr/bin/env python3
"""Run the fixed Topic 49 fresh-process campaign and retain every attempt."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PRIMARY_BLOCKS = 12
AA_BLOCKS = 4
PRIMARY_TEMPLATES = ("ABBA",) * 6 + ("BAAB",) * 6
AA_TEMPLATES = ("ABBA",) * 2 + ("BAAB",) * 2
DEFAULT_SEED = 20260828
QUIET_NS = 1_000_000_000
CHUNK_BYTES = 256 * 1024
NODE_BYTES = 64
FROZEN_LARGE_MIB = 512
FROZEN_WORKER_MIB = 128
FROZEN_WARMUP_MS = 750
FROZEN_TIMEOUT_SECONDS = 300.0
RESULT_SCHEMA = "dram-memory-controller.v1"
RESULT_KEYS = {
    "schema",
    "label",
    "treatment",
    "probe_cpu",
    "worker_cpus",
    "numa_node",
    "memory_policy",
    "memory_policy_bound",
    "probe_start_cpu",
    "probe_end_cpu",
    "worker_start_cpus",
    "worker_end_cpus",
    "large_mib",
    "worker_mib",
    "warmup_ms",
    "chunk_bytes",
    "correct",
    "affinity_ok",
    "prefetch_state",
    "madv_nohugepage",
    "page_size_bytes",
    "smaps_available",
    "large_kernel_page_kib",
    "large_mmu_page_kib",
    "large_anon_huge_kib",
    "large_thpeligible",
    "large_vmflag_nh",
    "small_kernel_page_kib",
    "small_anon_huge_kib",
    "small_vmflag_nh",
    "worker_anon_huge_kib",
    "worker_vmflag_nh_all",
    "startup_ns",
    "warmup_ns",
    "arm_wait_ns",
    "run_epoch_ns",
    "teardown_ns",
    "total_ns",
    "small_loads",
    "small_elapsed_ns",
    "small_ns_per_load",
    "small_checksum",
    "probe_loads",
    "probe_elapsed_ns",
    "probe_ns_per_load",
    "probe_bytes",
    "probe_checksum",
    "worker_chunks",
    "worker_chunks_by_thread",
    "worker_bytes",
    "worker_bytes_lower",
    "worker_bytes_upper_inclusive",
    "worker_gib_per_s_lower",
    "worker_gib_per_s_upper_inclusive",
    "worker_checksum",
    "process_large_window_minor_faults",
    "process_large_window_major_faults",
    "process_large_window_voluntary_context_switches",
    "process_large_window_involuntary_context_switches",
    "probe_thread_large_window_minor_faults",
    "probe_thread_large_window_major_faults",
    "probe_thread_large_window_voluntary_context_switches",
    "probe_thread_large_window_involuntary_context_switches",
    "total_major_faults",
}
BASE_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": os.defpath,
    "TZ": "UTC",
}


@dataclasses.dataclass(frozen=True)
class ExpectedResult:
    label: str
    treatment: str
    probe_cpu: int
    worker_cpus: tuple[int, ...]
    numa_node: int
    large_mib: int
    worker_mib: int
    warmup_ms: int


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON number: {token}")


def strict_json(text: str) -> object:
    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite,
    )


def strict_json_line(stdout: str) -> object:
    lines = stdout.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        raise ValueError("stdout must contain exactly one nonempty JSON line")
    return strict_json(lines[0])


def is_int(value: object) -> bool:
    return type(value) is int


def is_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def require_result(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_result(result: object, expected: ExpectedResult) -> dict[str, Any]:
    """Validate the versioned one-line result, including all safety canaries."""

    require_result(isinstance(result, dict), "result must be a JSON object")
    assert isinstance(result, dict)
    require_result(set(result) == RESULT_KEYS, "result key set differs from the v1 schema")
    exact = {
        "schema": RESULT_SCHEMA,
        "label": expected.label,
        "treatment": expected.treatment,
        "probe_cpu": expected.probe_cpu,
        "worker_cpus": list(expected.worker_cpus),
        "numa_node": expected.numa_node,
        "memory_policy": "MPOL_BIND",
        "memory_policy_bound": True,
        "probe_start_cpu": expected.probe_cpu,
        "probe_end_cpu": expected.probe_cpu,
        "worker_start_cpus": list(expected.worker_cpus),
        "worker_end_cpus": list(expected.worker_cpus),
        "large_mib": expected.large_mib,
        "worker_mib": expected.worker_mib,
        "warmup_ms": expected.warmup_ms,
        "chunk_bytes": CHUNK_BYTES,
        "correct": True,
        "affinity_ok": True,
        "madv_nohugepage": True,
    }
    for key, value in exact.items():
        require_result(
            type(result.get(key)) is type(value) and result.get(key) == value,
            f"result field {key} differs from the fixed invocation",
        )

    require_result(
        result["prefetch_state"] == "production-default-unmodified",
        "prefetch_state differs from the frozen production-default observation",
    )
    require_result(type(result["smaps_available"]) is bool, "smaps_available must be boolean")
    for key in ("large_vmflag_nh", "small_vmflag_nh", "worker_vmflag_nh_all"):
        require_result(type(result[key]) is bool, f"{key} must be boolean")

    nonnegative = (
        "large_kernel_page_kib",
        "large_mmu_page_kib",
        "large_anon_huge_kib",
        "small_kernel_page_kib",
        "small_anon_huge_kib",
        "worker_anon_huge_kib",
        "startup_ns",
        "warmup_ns",
        "arm_wait_ns",
        "run_epoch_ns",
        "teardown_ns",
        "total_ns",
        "small_loads",
        "small_elapsed_ns",
        "small_checksum",
        "probe_loads",
        "probe_elapsed_ns",
        "probe_bytes",
        "probe_checksum",
        "worker_chunks",
        "worker_bytes",
        "worker_bytes_lower",
        "worker_bytes_upper_inclusive",
        "worker_checksum",
        "process_large_window_minor_faults",
        "process_large_window_major_faults",
        "process_large_window_voluntary_context_switches",
        "process_large_window_involuntary_context_switches",
        "probe_thread_large_window_minor_faults",
        "probe_thread_large_window_major_faults",
        "probe_thread_large_window_voluntary_context_switches",
        "probe_thread_large_window_involuntary_context_switches",
        "total_major_faults",
    )
    for key in nonnegative:
        require_result(is_int(result[key]) and result[key] >= 0, f"{key} must be a nonnegative integer")
    require_result(
        is_int(result["page_size_bytes"]) and result["page_size_bytes"] > 0,
        "page_size_bytes must be a positive integer",
    )
    require_result(
        is_int(result["large_thpeligible"]) and result["large_thpeligible"] >= -1,
        "large_thpeligible must be -1 or a nonnegative integer",
    )
    for key in ("small_loads", "small_elapsed_ns", "probe_loads", "probe_elapsed_ns", "probe_bytes"):
        require_result(result[key] > 0, f"{key} must be positive")
    for key in (
        "small_ns_per_load",
        "probe_ns_per_load",
        "worker_gib_per_s_lower",
        "worker_gib_per_s_upper_inclusive",
    ):
        require_result(is_number(result[key]) and result[key] >= 0, f"{key} must be finite and nonnegative")

    chunks_by_thread = result["worker_chunks_by_thread"]
    require_result(
        isinstance(chunks_by_thread, list)
        and len(chunks_by_thread) == len(expected.worker_cpus)
        and all(is_int(value) and value >= 0 for value in chunks_by_thread),
        "worker_chunks_by_thread must contain one nonnegative integer per worker",
    )

    require_result(
        result["total_ns"]
        == result["startup_ns"]
        + result["warmup_ns"]
        + result["arm_wait_ns"]
        + result["run_epoch_ns"]
        + result["teardown_ns"],
        "total_ns does not equal the recorded phase sum",
    )
    require_result(result["run_epoch_ns"] > 0, "run_epoch_ns must be positive")
    require_result(
        math.isclose(
            float(result["small_ns_per_load"]),
            result["small_elapsed_ns"] / result["small_loads"],
            rel_tol=2e-9,
            abs_tol=1e-9,
        ),
        "small_ns_per_load does not rederive",
    )
    require_result(
        math.isclose(
            float(result["probe_ns_per_load"]),
            result["probe_elapsed_ns"] / result["probe_loads"],
            rel_tol=2e-9,
            abs_tol=1e-9,
        ),
        "probe_ns_per_load does not rederive",
    )
    expected_probe_loads = expected.large_mib * 1024 * 1024 // NODE_BYTES * 4
    require_result(result["probe_loads"] == expected_probe_loads, "probe_loads changed")
    require_result(result["probe_bytes"] == result["probe_loads"] * NODE_BYTES, "probe_bytes changed")
    require_result(result["worker_bytes"] == result["worker_bytes_lower"], "worker lower bound changed")
    require_result(
        result["worker_bytes"] == result["worker_chunks"] * CHUNK_BYTES,
        "worker byte count does not match complete chunks",
    )
    require_result(
        result["worker_chunks"] == sum(chunks_by_thread),
        "worker_chunks does not equal worker_chunks_by_thread sum",
    )
    require_result(
        result["worker_bytes_upper_inclusive"]
        == (
            0
            if expected.treatment == "idle"
            else result["worker_bytes_lower"] + len(expected.worker_cpus) * CHUNK_BYTES
        ),
        "worker upper bound changed",
    )
    if expected.treatment == "idle":
        require_result(result["worker_chunks"] == 0, "idle workers published chunks")
        require_result(all(value == 0 for value in chunks_by_thread), "idle worker thread published chunks")
        require_result(result["worker_bytes_lower"] == 0, "idle workers published bytes")
    else:
        require_result(
            all(value >= 1 for value in chunks_by_thread),
            "loaded treatment lacks one completed chunk from every worker",
        )
    gib = float(1024**3)
    lower_rate = result["worker_bytes_lower"] * 1_000_000_000.0 / result["run_epoch_ns"] / gib
    upper_rate = result["worker_bytes_upper_inclusive"] * 1_000_000_000.0 / result["run_epoch_ns"] / gib
    require_result(
        math.isclose(float(result["worker_gib_per_s_lower"]), lower_rate, rel_tol=2e-9, abs_tol=1e-9),
        "worker lower rate does not rederive",
    )
    require_result(
        math.isclose(
            float(result["worker_gib_per_s_upper_inclusive"]),
            upper_rate,
            rel_tol=2e-9,
            abs_tol=1e-9,
        ),
        "worker upper rate does not rederive",
    )
    if expected.treatment == "idle":
        require_result(lower_rate == 0.0 and upper_rate == 0.0, "idle worker rate bounds must be exact zero")
    require_result(
        result["process_large_window_major_faults"] == 0,
        "process-wide large dependent-walk window incurred a major fault",
    )
    require_result(
        result["process_large_window_minor_faults"] == 0,
        "process-wide large dependent-walk window incurred a minor fault",
    )
    require_result(
        result["probe_thread_large_window_major_faults"] == 0,
        "probe thread large dependent-walk window incurred a major fault",
    )
    require_result(
        result["probe_thread_large_window_minor_faults"] == 0,
        "probe thread large dependent-walk window incurred a minor fault",
    )
    require_result(result["total_major_faults"] == 0, "process incurred a major fault")

    if result["smaps_available"]:
        require_result(result["large_kernel_page_kib"] > 0, "large mapping lacks KernelPageSize")
        require_result(result["large_mmu_page_kib"] > 0, "large mapping lacks MMUPageSize")
        require_result(result["small_kernel_page_kib"] > 0, "small mapping lacks KernelPageSize")
        require_result(result["large_anon_huge_kib"] == 0, "large mapping used anonymous huge pages")
        require_result(result["small_anon_huge_kib"] == 0, "small mapping used anonymous huge pages")
        require_result(result["worker_anon_huge_kib"] == 0, "worker mappings used anonymous huge pages")
        require_result(result["large_vmflag_nh"] is True, "large mapping lacks the no-hugepage flag")
        require_result(result["small_vmflag_nh"] is True, "small mapping lacks the no-hugepage flag")
        require_result(result["worker_vmflag_nh_all"] is True, "a worker mapping lacks the no-hugepage flag")
    return result


def parse_cpu_csv(value: str) -> tuple[int, ...]:
    try:
        cpus = tuple(int(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("CPUs must be comma-separated integers") from error
    if len(cpus) != 8 or any(cpu < 0 for cpu in cpus) or len(set(cpus)) != len(cpus):
        raise argparse.ArgumentTypeError("worker CPU list must contain eight distinct nonnegative integers")
    return cpus


def make_schedule(seed: int) -> list[dict[str, Any]]:
    """Return one seed-recorded restricted shuffle over complete blocks."""

    rng = random.Random(seed)
    primary = list(PRIMARY_TEMPLATES)
    aa = list(AA_TEMPLATES)
    rng.shuffle(primary)
    rng.shuffle(aa)
    blocks: list[dict[str, Any]] = []
    for index, template in enumerate(primary, 1):
        blocks.append({"phase": "primary", "block": f"primary-{index:02d}", "template": template})
    for index, template in enumerate(aa, 1):
        blocks.append({"phase": "aa", "block": f"aa-{index:02d}", "template": template})
    rng.shuffle(blocks)
    return blocks


def append_jsonl(handle: Any, value: object) -> None:
    handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def write_exclusive(path: Path, data: str) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def normalized_output(value: bytes | str | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def stop_process_session(process: subprocess.Popen[str]) -> tuple[str, str]:
    """Stop one fresh process session and retain its final pipe contents."""

    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        stdout, stderr = process.communicate(timeout=5.0)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stdout, stderr = process.communicate()
    return normalized_output(stdout), normalized_output(stderr)


def attempt_spec(block: dict[str, Any], position: int, label: str) -> tuple[str, str]:
    logical_path = "path-a" if label == "A" else "path-b"
    if block["phase"] == "aa":
        return "loaded", logical_path
    return ("idle" if label == "A" else "loaded"), logical_path


def run_attempt(
    *,
    sequence: int,
    block: dict[str, Any],
    position: int,
    label: str,
    binary: Path,
    binary_digest: str,
    logical_path: str,
    treatment: str,
    args: argparse.Namespace,
    raw_root: Path,
) -> dict[str, Any]:
    bench_label = (
        f"{block['phase']}:{block['block']}:{block['template']}:"
        f"position-{position}:{label}:{logical_path}"
    )
    command = [
        str(binary),
        "--treatment",
        treatment,
        "--probe-cpu",
        str(args.probe_cpu),
        "--worker-cpus",
        ",".join(map(str, args.worker_cpus)),
        "--numa-node",
        str(args.numa_node),
        "--large-mib",
        str(args.large_mib),
        "--worker-mib",
        str(args.worker_mib),
        "--warmup-ms",
        str(args.warmup_ms),
    ]
    environment = dict(BASE_ENVIRONMENT)
    environment["BENCH_LABEL"] = bench_label
    basename = f"{sequence:03d}-{block['block']}-p{position}-{label}"
    stdout_path = raw_root / logical_path / f"{basename}.stdout"
    stderr_path = raw_root / logical_path / f"{basename}.stderr"
    status_path = raw_root / logical_path / f"{basename}.status.json"
    record: dict[str, Any] = {
        "schema": "topic49-attempt.v1",
        "sequence": sequence,
        "phase": block["phase"],
        "block": block["block"],
        "template": block["template"],
        "position": position,
        "label": label,
        "logical_path": logical_path,
        "treatment": treatment,
        "bench_label": bench_label,
        "binary": str(binary),
        "binary_sha256_expected": binary_digest,
        "command": command,
        "environment": environment,
        "timeout_seconds": args.timeout_seconds,
        "stdout_path": str(stdout_path.relative_to(args.out)),
        "stderr_path": str(stderr_path.relative_to(args.out)),
        "status_path": str(status_path.relative_to(args.out)),
        "started_utc": utc_now(),
    }
    try:
        record["binary_sha256_before"] = sha256(binary)
    except OSError as error:
        record["binary_sha256_before"] = None
        record["binary_hash_before_error"] = repr(error)
    wall_start = time.monotonic_ns()
    record["started_monotonic_ns"] = wall_start
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
            start_new_session=True,
        )
    except OSError as error:
        record["pid"] = None
        returncode = None
        timed_out = False
        stdout = ""
        stderr = repr(error)
    else:
        record["pid"] = process.pid
        try:
            stdout, stderr = process.communicate(timeout=args.timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            stdout, stderr = stop_process_session(process)
        except BaseException as error:
            stdout, stderr = stop_process_session(process)
            interrupted_status = {
                "pid": process.pid,
                "returncode": process.returncode,
                "timed_out": False,
                "wall_ns": time.monotonic_ns() - wall_start,
                "exception_type": type(error).__name__,
            }
            for path, text in ((stdout_path, stdout), (stderr_path, stderr)):
                try:
                    write_exclusive(path, text)
                except OSError:
                    pass
            try:
                write_exclusive(
                    status_path,
                    json.dumps(interrupted_status, indent=2, sort_keys=True) + "\n",
                )
            except OSError:
                pass
            raise
        returncode = process.returncode
    ended = time.monotonic_ns()
    record.update(
        {
            "ended_monotonic_ns": ended,
            "wall_ns": ended - wall_start,
            "returncode": returncode,
            "timed_out": timed_out,
            "stdout": stdout,
            "stderr": stderr,
        }
    )
    artifact_error = None
    try:
        write_exclusive(stdout_path, stdout)
        write_exclusive(stderr_path, stderr)
        write_exclusive(
            status_path,
            json.dumps(
                {
                    "pid": record["pid"],
                    "returncode": returncode,
                    "timed_out": timed_out,
                    "wall_ns": record["wall_ns"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    except OSError as error:
        artifact_error = repr(error)
    record["artifact_error"] = artifact_error
    try:
        record["binary_sha256_after"] = sha256(binary)
    except OSError as error:
        record["binary_sha256_after"] = None
        record["binary_hash_after_error"] = repr(error)
    parsed = None
    validation_error = None
    try:
        parsed = strict_json_line(stdout)
        validate_result(
            parsed,
            ExpectedResult(
                label=bench_label,
                treatment=treatment,
                probe_cpu=args.probe_cpu,
                worker_cpus=args.worker_cpus,
                numa_node=args.numa_node,
                large_mib=args.large_mib,
                worker_mib=args.worker_mib,
                warmup_ms=args.warmup_ms,
            ),
        )
    except (ValueError, TypeError) as error:
        validation_error = str(error)
    record["result"] = parsed
    record["valid"] = (
        returncode == 0
        and not timed_out
        and artifact_error is None
        and validation_error is None
        and record.get("binary_sha256_before") == binary_digest
        and record.get("binary_sha256_after") == binary_digest
    )
    record["validation_error"] = validation_error
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed 12-block primary and four-block A/A Topic 49 campaign."
    )
    parser.add_argument("--binary-a", required=True, type=Path, help="idle/A executable path")
    parser.add_argument("--binary-b", required=True, type=Path, help="loaded/B executable path")
    parser.add_argument("--out", required=True, type=Path, help="new campaign directory")
    parser.add_argument("--probe-cpu", required=True, type=int)
    parser.add_argument("--worker-cpus", required=True, type=parse_cpu_csv)
    parser.add_argument("--numa-node", required=True, type=int)
    parser.add_argument("--large-mib", default=512, type=int)
    parser.add_argument("--worker-mib", default=128, type=int)
    parser.add_argument("--warmup-ms", default=750, type=int)
    parser.add_argument("--seed", default=DEFAULT_SEED, type=int)
    parser.add_argument("--timeout-seconds", default=300.0, type=float)
    args = parser.parse_args()
    if (
        args.probe_cpu < 0
        or args.numa_node < 0
        or args.probe_cpu in args.worker_cpus
        or args.large_mib <= 0
        or args.worker_mib <= 0
        or args.warmup_ms <= 0
        or args.seed <= 0
        or args.timeout_seconds <= 0
        or not math.isfinite(args.timeout_seconds)
    ):
        parser.error("CPUs must be distinct and sizes, seed, warmup, and timeout must be positive")
    if (
        args.large_mib != FROZEN_LARGE_MIB
        or args.worker_mib != FROZEN_WORKER_MIB
        or args.warmup_ms != FROZEN_WARMUP_MS
        or args.seed != DEFAULT_SEED
        or args.timeout_seconds != FROZEN_TIMEOUT_SECONDS
    ):
        parser.error(
            "published campaign is frozen at 512/128 MiB, 750 ms, seed 20260828, "
            "and timeout 300 seconds"
        )
    for binary in (args.binary_a, args.binary_b):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            parser.error(f"binary is not an executable regular file: {binary}")
    args.binary_a = args.binary_a.resolve()
    args.binary_b = args.binary_b.resolve()
    args.out = args.out.resolve()
    if args.binary_a == args.binary_b:
        parser.error("A/A must exercise two distinct executable paths")
    return args


def main() -> None:
    args = parse_args()
    if args.out.exists():
        raise SystemExit(f"campaign output already exists: {args.out}")
    digest_a = sha256(args.binary_a)
    digest_b = sha256(args.binary_b)
    if digest_a != digest_b:
        raise SystemExit("A/A executable paths do not contain identical linked images")
    schedule = make_schedule(args.seed)
    args.out.mkdir(parents=True)
    raw_root = args.out / "raw"
    (raw_root / "path-a").mkdir(parents=True)
    (raw_root / "path-b").mkdir(parents=True)
    metadata = {
        "schema": "topic49-campaign-metadata.v1",
        "created_utc": utc_now(),
        "schedule_seed": args.seed,
        "schedule": schedule,
        "primary_blocks": PRIMARY_BLOCKS,
        "aa_blocks": AA_BLOCKS,
        "periods_per_block": 4,
        "quiet_interval_ns": QUIET_NS,
        "fixed_stopping": "run every predeclared period once; do not replace or peek",
        "analysis_unit": "one complete four-process block contrast",
        "primary_estimand": "geometric loaded/idle ratio of large-chain nanoseconds per load",
        "binary_paths_distinct": True,
        "binary_sha256_equal": True,
        "binaries": {
            "path-a": {"path": str(args.binary_a), "sha256": digest_a},
            "path-b": {"path": str(args.binary_b), "sha256": digest_b},
        },
        "config": {
            "probe_cpu": args.probe_cpu,
            "worker_cpus": list(args.worker_cpus),
            "numa_node": args.numa_node,
            "large_mib": args.large_mib,
            "worker_mib": args.worker_mib,
            "warmup_ms": args.warmup_ms,
            "timeout_seconds": args.timeout_seconds,
        },
        "base_environment": BASE_ENVIRONMENT,
    }
    write_exclusive(args.out / "metadata.json", json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    sequence = 0
    attempts_path = args.out / "attempts.jsonl"
    journal_path = args.out / "attempt-journal.jsonl"
    with (
        attempts_path.open("x", encoding="utf-8") as attempts,
        journal_path.open("x", encoding="utf-8") as journal,
    ):
        total = len(schedule) * 4
        for block in schedule:
            for position, label in enumerate(block["template"], 1):
                sequence += 1
                treatment, logical_path = attempt_spec(block, position, label)
                binary = args.binary_a if logical_path == "path-a" else args.binary_b
                digest = digest_a if logical_path == "path-a" else digest_b
                append_jsonl(
                    journal,
                    {
                        "schema": "topic49-attempt-journal.v1",
                        "event": "attempt-start",
                        "sequence": sequence,
                        "phase": block["phase"],
                        "block": block["block"],
                        "template": block["template"],
                        "position": position,
                        "label": label,
                        "logical_path": logical_path,
                        "treatment": treatment,
                        "journaled_utc": utc_now(),
                        "journaled_monotonic_ns": time.monotonic_ns(),
                    },
                )
                try:
                    record = run_attempt(
                        sequence=sequence,
                        block=block,
                        position=position,
                        label=label,
                        binary=binary,
                        binary_digest=digest,
                        logical_path=logical_path,
                        treatment=treatment,
                        args=args,
                        raw_root=raw_root,
                    )
                except BaseException as error:
                    append_jsonl(
                        journal,
                        {
                            "schema": "topic49-attempt-journal.v1",
                            "event": "attempt-end",
                            "sequence": sequence,
                            "outcome": "interrupted",
                            "exception_type": type(error).__name__,
                            "journaled_utc": utc_now(),
                            "journaled_monotonic_ns": time.monotonic_ns(),
                        },
                    )
                    raise
                append_jsonl(attempts, record)
                append_jsonl(
                    journal,
                    {
                        "schema": "topic49-attempt-journal.v1",
                        "event": "attempt-end",
                        "sequence": sequence,
                        "outcome": "valid" if record["valid"] else "invalid",
                        "pid": record["pid"],
                        "journaled_utc": utc_now(),
                        "journaled_monotonic_ns": time.monotonic_ns(),
                    },
                )
                if sequence < total:
                    time.sleep(QUIET_NS / 1_000_000_000)

    analyzer = Path(__file__).with_name("analyze.py")
    completed = subprocess.run(
        [
            sys.executable,
            str(analyzer),
            "--metadata",
            str(args.out / "metadata.json"),
            "--attempts",
            str(attempts_path),
            "--output",
            str(args.out / "summary.json"),
        ],
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit("campaign retained all fixed attempts, but strict analysis failed")


if __name__ == "__main__":
    main()
