#!/usr/bin/env python3
"""Run Topic 21 as fresh, pinned, order-balanced processes.

The analysis unit is one four-process block. Odd primary blocks use ABBA;
even blocks use BAAB. A/A controls use distinct labels that resolve to the
same implementation. The reported Student-t interval covers variation among
block-level log time ratios, not inner-loop iterations.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, TextIO

PRIMARY_BLOCKS = 12
CONTROL_BLOCKS = 4
WRITE_MIB = 512
STLF_ITERATIONS = 500_000_000
PROCESS_TIMEOUT_SECONDS = 300
T_975 = {3: 3.182446, 11: 2.200985}


@dataclass(frozen=True)
class Comparison:
    """One primary comparison and its identity control."""

    name: str
    command: str
    primary_a: str
    primary_b: str
    control_a: str
    control_b: str

    def command_line(self, binary: Path, mode: str) -> list[str]:
        if self.command == "write":
            return [str(binary), "write", mode, str(WRITE_MIB)]
        if self.command == "stlf":
            return [str(binary), "stlf", mode, str(STLF_ITERATIONS)]
        fail(f"internal error: unknown command {self.command}")


COMPARISONS = (
    Comparison(
        name="write-nontemporal-over-temporal",
        command="write",
        primary_a="temporal",
        primary_b="nontemporal",
        control_a="temporal_a",
        control_b="temporal_b",
    ),
    Comparison(
        name="stlf-partial-over-exact",
        command="stlf",
        primary_a="exact",
        primary_b="partial",
        control_a="exact_a",
        control_b="exact_b",
    ),
)


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def require_integer(record: dict[str, Any], name: str, *, positive: bool = False) -> int:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        fail(f"{record.get('run_id', '<unknown>')}: {name} is not an integer")
    if value < 0 or (positive and value == 0):
        fail(f"{record.get('run_id', '<unknown>')}: invalid {name}={value}")
    return value


def schedule_modes(a: str, b: str, block: int) -> tuple[str, tuple[tuple[str, str], ...]]:
    if block % 2:
        return "ABBA", (("A", a), ("B", b), ("B", b), ("A", a))
    return "BAAB", (("B", b), ("A", a), ("A", a), ("B", b))


def validate_binary_record(
    record: dict[str, Any],
    *,
    comparison: Comparison,
    requested_mode: str,
    run_id: str,
) -> None:
    record["run_id"] = run_id
    expected_kind = comparison.command
    if record.get("schema") != 1:
        fail(f"{run_id}: unsupported JSON schema")
    if record.get("kind") != expected_kind:
        fail(f"{run_id}: kind does not match {expected_kind}")
    if record.get("mode") != requested_mode:
        fail(f"{run_id}: binary reported a different mode")
    if record.get("architecture") not in {"x86_64", "aarch64"}:
        fail(f"{run_id}: unsupported or missing architecture")

    expected_implementation = {
        "temporal": "temporal",
        "temporal_a": "temporal",
        "temporal_b": "temporal",
        "nontemporal": "nontemporal",
        "exact": "exact",
        "exact_a": "exact",
        "exact_b": "exact",
        "partial": "partial",
    }[requested_mode]
    if record.get("implementation") != expected_implementation:
        fail(f"{run_id}: implementation does not match requested mode")

    for field in ("setup_ns", "scrub_ns", "timed_ns", "verify_ns"):
        # Only the timed phase must be strictly positive. Short setup, scrub,
        # or verification phases may legitimately measure zero at the clock's
        # resolution.
        require_integer(record, field, positive=field == "timed_ns")
    for phase in ("setup", "scrub", "timed", "verify"):
        minor = require_integer(record, f"{phase}_minor_faults")
        major = require_integer(record, f"{phase}_major_faults")
        if major != 0:
            fail(f"{run_id}: {phase} period incurred {major} major faults")
        if phase == "timed" and minor != 0:
            fail(f"{run_id}: timed period incurred {minor} minor faults")

    if comparison.command == "write":
        if require_integer(record, "bytes", positive=True) != WRITE_MIB * 1024 * 1024:
            fail(f"{run_id}: binary used the wrong write size")
        if require_integer(record, "published") != 1:
            fail(f"{run_id}: release publication was not observed")
        if require_integer(record, "bad_words") != 0:
            fail(f"{run_id}: full-pattern verification failed")
    else:
        if require_integer(record, "iterations", positive=True) != STLF_ITERATIONS:
            fail(f"{run_id}: binary used the wrong STLF iteration count")
        if record.get("oracle_match") is not True:
            fail(f"{run_id}: STLF result differs from the oracle")


def run_one(
    *,
    binary: Path,
    cpu: str,
    source_commit: str,
    binary_sha256: str,
    comparison: Comparison,
    phase: str,
    block: int,
    position: int,
    order: str,
    arm: str,
    mode: str,
    raw_file: TextIO,
    attempts_file: TextIO,
    log_file: TextIO,
) -> dict[str, Any]:
    run_id = f"{comparison.name}-{phase}-b{block:02d}-p{position}"
    command = [
        "taskset",
        "--cpu-list",
        cpu,
        *comparison.command_line(binary, mode),
    ]
    log_file.write(
        f"PROCESS_START run_id={run_id} phase={phase} block={block} "
        f"position={position} order={order} arm={arm} mode={mode}\n"
    )
    log_file.flush()
    started = time.monotonic_ns()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        log_file.write(f"PROCESS_TIMEOUT run_id={run_id} timeout_seconds={error.timeout}\n")
        log_file.flush()
        fail(f"{run_id}: process timed out")
    external_wall_ns = time.monotonic_ns() - started
    log_file.write(
        f"PROCESS_OUTPUT run_id={run_id} returncode={completed.returncode} "
        f"stdout={json.dumps(completed.stdout)} stderr={json.dumps(completed.stderr)}\n"
    )
    log_file.flush()

    lines = completed.stdout.splitlines()
    if len(lines) != 1:
        fail(f"{run_id}: benchmark did not emit exactly one JSON line")
    try:
        record = json.loads(lines[0])
    except json.JSONDecodeError as error:
        fail(f"{run_id}: invalid benchmark JSON: {error}")
    if not isinstance(record, dict):
        fail(f"{run_id}: benchmark JSON is not an object")

    # Preserve the emitted record even when the binary rejects a faulted run.
    # This leaves diagnostic evidence while still making the schedule fail.
    record.update(
        {
            "run_id": run_id,
            "source_commit": source_commit,
            "binary_sha256": binary_sha256,
            "comparison": comparison.name,
            "phase": phase,
            "block": block,
            "position": position,
            "order": order,
            "arm": arm,
            "external_wall_ns": external_wall_ns,
        }
    )
    attempts_file.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    attempts_file.flush()

    if completed.returncode != 0:
        fail(f"{run_id}: benchmark exited with status {completed.returncode}")
    if completed.stderr:
        fail(f"{run_id}: successful benchmark emitted stderr")
    validate_binary_record(
        record,
        comparison=comparison,
        requested_mode=mode,
        run_id=run_id,
    )
    internal_ns = sum(
        require_integer(record, field)
        for field in ("setup_ns", "scrub_ns", "timed_ns", "verify_ns")
    )
    if external_wall_ns < internal_ns:
        fail(f"{run_id}: external wall time is shorter than internal phases")
    record["unmeasured_process_ns"] = external_wall_ns - internal_ns
    raw_file.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    raw_file.flush()
    log_file.write(
        f"PROCESS_END run_id={run_id} external_wall_ns={external_wall_ns} "
        f"unmeasured_process_ns={record['unmeasured_process_ns']}\n"
    )
    log_file.flush()
    return record


def geometric_mean(values: list[int]) -> float:
    return math.exp(statistics.fmean(math.log(value) for value in values))


def summarize_group(
    records: list[dict[str, Any]], comparison: Comparison, phase: str
) -> dict[str, Any]:
    block_count = PRIMARY_BLOCKS if phase == "primary" else CONTROL_BLOCKS
    expected_runs = block_count * 4
    if len(records) != expected_runs:
        fail(
            f"{comparison.name} {phase}: partial schedule: "
            f"{len(records)} of {expected_runs} processes"
        )
    block_log_ratios: list[float] = []
    all_a: list[int] = []
    all_b: list[int] = []
    for block in range(1, block_count + 1):
        block_records = [record for record in records if record["block"] == block]
        if sorted(record["position"] for record in block_records) != [1, 2, 3, 4]:
            fail(f"{comparison.name} {phase} block {block}: incomplete positions")
        a = [record["timed_ns"] for record in block_records if record["arm"] == "A"]
        b = [record["timed_ns"] for record in block_records if record["arm"] == "B"]
        if len(a) != 2 or len(b) != 2:
            fail(f"{comparison.name} {phase} block {block}: unbalanced arms")
        all_a.extend(a)
        all_b.extend(b)
        block_log_ratios.append(statistics.fmean(math.log(value) for value in b) - statistics.fmean(math.log(value) for value in a))

    mean_log_ratio = statistics.fmean(block_log_ratios)
    log_ratio_sd = statistics.stdev(block_log_ratios)
    degrees_of_freedom = block_count - 1
    critical = T_975[degrees_of_freedom]
    half_width = critical * log_ratio_sd / math.sqrt(block_count)
    return {
        "comparison": comparison.name,
        "phase": phase,
        "ratio": "B_over_A",
        "arm_a": comparison.primary_a if phase == "primary" else comparison.control_a,
        "arm_b": comparison.primary_b if phase == "primary" else comparison.control_b,
        "process_runs": expected_runs,
        "blocks": block_count,
        "observations_per_arm_per_block": 2,
        "geometric_mean_a_ns": geometric_mean(all_a),
        "geometric_mean_b_ns": geometric_mean(all_b),
        "geometric_time_ratio": math.exp(mean_log_ratio),
        "log_ratio_sd": log_ratio_sd,
        "student_t_df": degrees_of_freedom,
        "student_t_critical_95": critical,
        "ci95_low": math.exp(mean_log_ratio - half_width),
        "ci95_high": math.exp(mean_log_ratio + half_width),
        "interval_scope": "between-block variation in paired process-level log time ratios",
    }


def prepare_output(path: Path) -> None:
    if not path.is_absolute():
        fail("OUTPUT_DIRECTORY must be absolute")
    if path.exists():
        if not path.is_dir():
            fail("OUTPUT_DIRECTORY exists and is not a directory")
        if any(path.iterdir()):
            fail("OUTPUT_DIRECTORY must be empty")
    else:
        path.mkdir(parents=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if len(sys.argv) != 5:
        fail("usage: run_processes.py BINARY OUTPUT_DIRECTORY CPU SOURCE_COMMIT")
    binary = Path(sys.argv[1])
    output = Path(sys.argv[2])
    cpu = sys.argv[3]
    source_commit = sys.argv[4]
    if not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK):
        fail("BINARY must be an absolute executable file")
    if not re.fullmatch(r"[0-9]+", cpu):
        fail("CPU must be a nonnegative integer")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        fail("SOURCE_COMMIT must be a 40-character lowercase Git object ID")
    affinity = subprocess.run(
        ["taskset", "--cpu-list", cpu, "true"],
        check=False,
        capture_output=True,
        text=True,
    )
    if affinity.returncode != 0:
        fail(f"taskset cannot pin to CPU {cpu}: {affinity.stderr.strip()}")
    prepare_output(output)
    binary_sha256 = sha256_file(binary)

    raw_path = output / "raw.jsonl"
    attempts_path = output / "attempts.jsonl"
    log_path = output / "process.log"
    session_path = output / "session.json"
    summary_path = output / "summary.json"
    session = {
        "schema": 1,
        "source_commit": source_commit,
        "binary_sha256": binary_sha256,
        "binary": str(binary),
        "cpu": int(cpu),
        "primary_blocks": PRIMARY_BLOCKS,
        "control_blocks": CONTROL_BLOCKS,
        "write_mib": WRITE_MIB,
        "stlf_iterations": STLF_ITERATIONS,
        "schedule": "odd ABBA; even BAAB; four fresh processes per block",
        "analysis_unit": "four-process block",
    }
    session_path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    records: list[dict[str, Any]] = []
    with (
        raw_path.open("x", encoding="utf-8") as raw_file,
        attempts_path.open("x", encoding="utf-8") as attempts_file,
        log_path.open("x", encoding="utf-8") as log_file,
    ):
        for comparison in COMPARISONS:
            for phase, blocks, mode_a, mode_b in (
                (
                    "control",
                    CONTROL_BLOCKS,
                    comparison.control_a,
                    comparison.control_b,
                ),
                (
                    "primary",
                    PRIMARY_BLOCKS,
                    comparison.primary_a,
                    comparison.primary_b,
                ),
            ):
                for block in range(1, blocks + 1):
                    order, positions = schedule_modes(mode_a, mode_b, block)
                    for position, (arm, mode) in enumerate(positions, start=1):
                        records.append(
                            run_one(
                                binary=binary,
                                cpu=cpu,
                                source_commit=source_commit,
                                binary_sha256=binary_sha256,
                                comparison=comparison,
                                phase=phase,
                                block=block,
                                position=position,
                                order=order,
                                arm=arm,
                                mode=mode,
                                raw_file=raw_file,
                                attempts_file=attempts_file,
                                log_file=log_file,
                            )
                        )

    expected_total = len(COMPARISONS) * (PRIMARY_BLOCKS + CONTROL_BLOCKS) * 4
    if len(records) != expected_total:
        fail(f"partial experiment: {len(records)} of {expected_total} processes")
    architectures = {record["architecture"] for record in records}
    if len(architectures) != 1:
        fail("architecture changed within one experiment")
    summaries = []
    for comparison in COMPARISONS:
        for phase in ("primary", "control"):
            group = [
                record
                for record in records
                if record["comparison"] == comparison.name and record["phase"] == phase
            ]
            summaries.append(summarize_group(group, comparison, phase))
    summary = {
        "schema": 1,
        "source_commit": source_commit,
        "binary_sha256": binary_sha256,
        "architecture": next(iter(architectures)),
        "process_runs": len(records),
        "comparisons": summaries,
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
