#!/usr/bin/env python3
"""Strictly validate Topic 49 process receipts and compute frozen contrasts."""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any, NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_processes import (
    AA_BLOCKS,
    BASE_ENVIRONMENT,
    PRIMARY_BLOCKS,
    QUIET_NS,
    ExpectedResult,
    attempt_spec,
    make_schedule,
    strict_json,
    strict_json_line,
    validate_result,
)


T_975 = {
    1: 12.706204736,
    3: 3.182446305,
    5: 2.570581836,
    11: 2.200985160,
}
ATTEMPT_KEYS = {
    "schema",
    "sequence",
    "phase",
    "block",
    "template",
    "position",
    "label",
    "logical_path",
    "treatment",
    "bench_label",
    "binary",
    "binary_sha256_expected",
    "command",
    "environment",
    "timeout_seconds",
    "stdout_path",
    "stderr_path",
    "status_path",
    "started_utc",
    "binary_sha256_before",
    "started_monotonic_ns",
    "pid",
    "ended_monotonic_ns",
    "wall_ns",
    "returncode",
    "timed_out",
    "stdout",
    "stderr",
    "artifact_error",
    "binary_sha256_after",
    "result",
    "valid",
    "validation_error",
}
METADATA_KEYS = {
    "schema",
    "created_utc",
    "schedule_seed",
    "schedule",
    "primary_blocks",
    "aa_blocks",
    "periods_per_block",
    "quiet_interval_ns",
    "fixed_stopping",
    "analysis_unit",
    "primary_estimand",
    "binary_paths_distinct",
    "binary_sha256_equal",
    "binaries",
    "config",
    "base_environment",
}


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def is_int(value: object) -> bool:
    return type(value) is int


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = strict_json(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        fail(f"{path}: invalid JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{path}: expected one JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.endswith("\n") or not line.strip():
                    fail(f"{path}:{line_number}: partial or blank JSONL record")
                try:
                    value = strict_json(line)
                except (json.JSONDecodeError, ValueError) as error:
                    fail(f"{path}:{line_number}: invalid JSON: {error}")
                if not isinstance(value, dict):
                    fail(f"{path}:{line_number}: attempt must be an object")
                rows.append(value)
    except OSError as error:
        fail(f"cannot read {path}: {error}")
    return rows


def same_value(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(same_value(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_value(a, b) for a, b in zip(left, right))
    return left == right


def validate_metadata(metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if set(metadata) != METADATA_KEYS:
        fail("campaign metadata key set changed")
    if metadata.get("schema") != "topic49-campaign-metadata.v1":
        fail("campaign metadata schema changed")
    seed = metadata.get("schedule_seed")
    if not is_int(seed) or seed <= 0:
        fail("schedule seed must be a positive integer")
    schedule = make_schedule(seed)
    if not same_value(metadata.get("schedule"), schedule):
        fail("recorded schedule does not rederive from the seed")
    fixed = {
        "primary_blocks": PRIMARY_BLOCKS,
        "aa_blocks": AA_BLOCKS,
        "periods_per_block": 4,
        "quiet_interval_ns": QUIET_NS,
        "fixed_stopping": "run every predeclared period once; do not replace or peek",
        "analysis_unit": "one complete four-process block contrast",
        "primary_estimand": "geometric loaded/idle ratio of large-chain nanoseconds per load",
        "binary_paths_distinct": True,
        "binary_sha256_equal": True,
        "base_environment": BASE_ENVIRONMENT,
    }
    for key, value in fixed.items():
        if not same_value(metadata.get(key), value):
            fail(f"metadata field {key} changed")
    binaries = metadata.get("binaries")
    if not isinstance(binaries, dict) or set(binaries) != {"path-a", "path-b"}:
        fail("metadata must name both binary paths")
    paths: set[str] = set()
    digests: set[str] = set()
    for logical_path in ("path-a", "path-b"):
        item = binaries[logical_path]
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            fail(f"malformed {logical_path} binary metadata")
        path = item.get("path")
        digest = item.get("sha256")
        if not isinstance(path, str) or not os.path.isabs(path):
            fail(f"{logical_path} binary path must be absolute")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            fail(f"{logical_path} binary digest is malformed")
        paths.add(path)
        digests.add(digest)
    if len(paths) != 2 or len(digests) != 1:
        fail("A/A requires distinct paths containing one identical linked image")
    config = metadata.get("config")
    if not isinstance(config, dict) or set(config) != {
        "probe_cpu",
        "worker_cpus",
        "large_mib",
        "worker_mib",
        "warmup_ms",
        "timeout_seconds",
    }:
        fail("campaign config key set changed")
    probe_cpu = config.get("probe_cpu")
    workers = config.get("worker_cpus")
    if not is_int(probe_cpu) or probe_cpu < 0:
        fail("probe CPU is invalid")
    if (
        not isinstance(workers, list)
        or len(workers) != 8
        or any(not is_int(cpu) or cpu < 0 for cpu in workers)
        or len(set(workers)) != 8
        or probe_cpu in workers
    ):
        fail("worker CPU list is invalid")
    frozen_config = {
        "large_mib": 512,
        "worker_mib": 128,
        "warmup_ms": 750,
        "timeout_seconds": 300.0,
    }
    for key, value in frozen_config.items():
        if not same_value(config.get(key), value):
            fail(f"campaign config {key} differs from the frozen value")
    return schedule, config


def expected_command(
    binary: str,
    treatment: str,
    config: dict[str, Any],
) -> list[str]:
    return [
        binary,
        "--treatment",
        treatment,
        "--probe-cpu",
        str(config["probe_cpu"]),
        "--worker-cpus",
        ",".join(map(str, config["worker_cpus"])),
        "--large-mib",
        str(config["large_mib"]),
        "--worker-mib",
        str(config["worker_mib"]),
        "--warmup-ms",
        str(config["warmup_ms"]),
    ]


def expected_rows(schedule: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected: list[dict[str, Any]] = []
    sequence = 0
    for block in schedule:
        for position, label in enumerate(block["template"], 1):
            sequence += 1
            treatment, logical_path = attempt_spec(block, position, label)
            bench_label = (
                f"{block['phase']}:{block['block']}:{block['template']}:"
                f"position-{position}:{label}:{logical_path}"
            )
            expected.append(
                {
                    "sequence": sequence,
                    **block,
                    "position": position,
                    "label": label,
                    "logical_path": logical_path,
                    "treatment": treatment,
                    "bench_label": bench_label,
                }
            )
    return expected


def validate_raw_path(root: Path, relative: object, expected_prefix: str, expected_text: str) -> Path:
    if not isinstance(relative, str):
        fail("raw receipt path must be a string")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("raw", expected_prefix):
        fail(f"raw receipt escaped {expected_prefix}")
    full = root / path
    try:
        text = full.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"missing raw receipt {relative}: {error}")
    if text != expected_text:
        fail(f"raw receipt {relative} differs from retained attempt")
    return full


def validate_attempts(
    metadata_path: Path,
    metadata: dict[str, Any],
    schedule: list[dict[str, Any]],
    config: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected = expected_rows(schedule)
    if len(rows) != (PRIMARY_BLOCKS + AA_BLOCKS) * 4 or len(rows) != len(expected):
        fail(f"fixed horizon needs 64 attempts, found {len(rows)}")
    root = metadata_path.parent
    binaries = metadata["binaries"]
    previous_end: int | None = None
    pids: set[int] = set()
    results: list[dict[str, Any]] = []
    for row, spec in zip(rows, expected):
        if set(row) != ATTEMPT_KEYS:
            fail(f"attempt {row.get('sequence')} key set changed or records an execution error")
        if row.get("schema") != "topic49-attempt.v1":
            fail("attempt schema changed")
        for key in (
            "sequence",
            "phase",
            "block",
            "template",
            "position",
            "label",
            "logical_path",
            "treatment",
            "bench_label",
        ):
            if not same_value(row.get(key), spec[key]):
                fail(f"attempt {spec['sequence']} field {key} differs from the frozen schedule")
        logical_path = spec["logical_path"]
        binary = binaries[logical_path]["path"]
        digest = binaries[logical_path]["sha256"]
        if row.get("binary") != binary or row.get("binary_sha256_expected") != digest:
            fail(f"attempt {spec['sequence']} selected the wrong linked image")
        if row.get("binary_sha256_before") != digest or row.get("binary_sha256_after") != digest:
            fail(f"attempt {spec['sequence']} linked image changed")
        if row.get("command") != expected_command(binary, spec["treatment"], config):
            fail(f"attempt {spec['sequence']} command changed")
        environment = dict(BASE_ENVIRONMENT)
        environment["BENCH_LABEL"] = spec["bench_label"]
        if row.get("environment") != environment:
            fail(f"attempt {spec['sequence']} environment changed")
        if row.get("timeout_seconds") != config["timeout_seconds"]:
            fail(f"attempt {spec['sequence']} timeout changed")
        if (
            row.get("returncode") != 0
            or row.get("timed_out") is not False
            or row.get("artifact_error") is not None
            or row.get("validation_error") is not None
            or row.get("valid") is not True
        ):
            fail(f"attempt {spec['sequence']} failed and was correctly retained")
        pid = row.get("pid")
        if not is_int(pid) or pid <= 0 or pid in pids:
            fail(f"attempt {spec['sequence']} does not evidence a fresh PID")
        pids.add(pid)
        started = row.get("started_monotonic_ns")
        ended = row.get("ended_monotonic_ns")
        wall = row.get("wall_ns")
        if not all(is_int(value) and value >= 0 for value in (started, ended, wall)):
            fail(f"attempt {spec['sequence']} has malformed monotonic timing")
        if ended < started or wall != ended - started:
            fail(f"attempt {spec['sequence']} wall timing does not rederive")
        if previous_end is not None and started - previous_end < QUIET_NS:
            fail(f"attempt {spec['sequence']} started before the one-second quiet interval ended")
        previous_end = ended
        stdout = row.get("stdout")
        stderr = row.get("stderr")
        if not isinstance(stdout, str) or not isinstance(stderr, str):
            fail(f"attempt {spec['sequence']} output is not text")
        stdout_path = validate_raw_path(root, row.get("stdout_path"), logical_path, stdout)
        validate_raw_path(root, row.get("stderr_path"), logical_path, stderr)
        status_relative = row.get("status_path")
        if not isinstance(status_relative, str):
            fail("status path must be text")
        status_path = Path(status_relative)
        if (
            status_path.is_absolute()
            or ".." in status_path.parts
            or status_path.parts[:2] != ("raw", logical_path)
        ):
            fail("status receipt escaped its logical path")
        status = read_json(root / status_path)
        if set(status) != {"pid", "returncode", "timed_out", "wall_ns"}:
            fail(f"attempt {spec['sequence']} status receipt key set changed")
        for key in status:
            if not same_value(status[key], row[key]):
                fail(f"attempt {spec['sequence']} status receipt differs on {key}")
        reparsed = strict_json_line(stdout_path.read_text(encoding="utf-8"))
        if not same_value(reparsed, row.get("result")):
            fail(f"attempt {spec['sequence']} parsed result differs from raw stdout")
        result = validate_result(
            reparsed,
            ExpectedResult(
                label=spec["bench_label"],
                treatment=spec["treatment"],
                probe_cpu=config["probe_cpu"],
                worker_cpus=tuple(config["worker_cpus"]),
                large_mib=config["large_mib"],
                worker_mib=config["worker_mib"],
                warmup_ms=config["warmup_ms"],
            ),
        )
        results.append(result)

    for key in ("probe_loads", "probe_bytes", "probe_checksum", "small_loads", "small_checksum", "prefetch_state"):
        if len({result[key] for result in results}) != 1:
            fail(f"fixed processes disagree on {key}")
    return results


def four_period_contrast(template: str, values: list[float]) -> float:
    if len(values) != 4 or any(value <= 0 or not math.isfinite(value) for value in values):
        fail("four-period contrast needs four finite positive values")
    logs = [math.log(value) for value in values]
    if template == "ABBA":
        return ((logs[1] + logs[2]) - (logs[0] + logs[3])) / 2.0
    if template == "BAAB":
        return ((logs[0] + logs[3]) - (logs[1] + logs[2])) / 2.0
    fail(f"unsupported block template: {template}")


def descriptive(values: list[float]) -> dict[str, Any]:
    if not values:
        fail("cannot summarize an empty sample")
    return {
        "count": len(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def contrast_summary(
    contrasts: list[float], *, interval_scope: str | None
) -> dict[str, Any]:
    if len(contrasts) < 2:
        fail("contrast summary needs at least two complete blocks")
    mean = statistics.fmean(contrasts)
    sample_sd = statistics.stdev(contrasts)
    ratios = [math.exp(value) for value in contrasts]
    summary: dict[str, Any] = {
        "blocks": len(contrasts),
        "mean_log_contrast": mean,
        "geometric_mean_ratio": math.exp(mean),
        "sample_sd_log_contrast": sample_sd,
        "block_ratio_median": statistics.median(ratios),
        "block_ratio_minimum": min(ratios),
        "block_ratio_maximum": max(ratios),
    }
    if interval_scope is not None:
        degrees = len(contrasts) - 1
        critical = T_975.get(degrees)
        if critical is None:
            fail(f"no predeclared t critical for {degrees} degrees of freedom")
        standard_error = sample_sd / math.sqrt(len(contrasts))
        half_width = critical * standard_error
        summary.update(
            {
                "degrees_of_freedom": degrees,
                "standard_error_log_contrast": standard_error,
                "t_critical_975": critical,
                "ci95_ratio_low": math.exp(mean - half_width),
                "ci95_ratio_high": math.exp(mean + half_width),
                "interval_scope": interval_scope,
            }
        )
    return summary


def block_rows(
    schedule: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = collections.defaultdict(list)
    for row, result in zip(rows, results):
        grouped[row["block"]].append((row, result))
    blocks: list[dict[str, Any]] = []
    for spec in schedule:
        items = grouped.get(spec["block"], [])
        items.sort(key=lambda item: item[0]["position"])
        if len(items) != 4 or [item[0]["position"] for item in items] != [1, 2, 3, 4]:
            fail(f"block {spec['block']} is partial")
        probe_values = [item[1]["probe_elapsed_ns"] / item[1]["probe_loads"] for item in items]
        small_values = [item[1]["small_elapsed_ns"] / item[1]["small_loads"] for item in items]
        blocks.append(
            {
                "phase": spec["phase"],
                "block": spec["block"],
                "template": spec["template"],
                "probe_ns_per_load_by_position": probe_values,
                "small_ns_per_load_by_position": small_values,
                "probe_log_contrast": four_period_contrast(spec["template"], probe_values),
                "probe_ratio": math.exp(four_period_contrast(spec["template"], probe_values)),
                "small_log_contrast": four_period_contrast(spec["template"], small_values),
                "small_ratio": math.exp(four_period_contrast(spec["template"], small_values)),
                "worker_bytes_lower_by_position": [item[1]["worker_bytes_lower"] for item in items],
                "worker_bytes_upper_inclusive_by_position": [
                    item[1]["worker_bytes_upper_inclusive"] for item in items
                ],
            }
        )
    return blocks


def phase_summary(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    probes = [block["probe_log_contrast"] for block in blocks]
    small = [block["small_log_contrast"] for block in blocks]
    by_template: dict[str, Any] = {}
    for template in ("ABBA", "BAAB"):
        selected = [block for block in blocks if block["template"] == template]
        by_template[template] = {
            "probe": contrast_summary(
                [block["probe_log_contrast"] for block in selected], interval_scope=None
            ),
            "small_control": contrast_summary(
                [block["small_log_contrast"] for block in selected], interval_scope=None
            ),
        }
    return {
        "probe": contrast_summary(
            probes,
            interval_scope=(
                "between-block variation in paired fresh-process log large-chain "
                "nanoseconds-per-load ratios on this exact host, binary, and run window"
            ),
        ),
        "small_control": contrast_summary(
            small,
            interval_scope=(
                "between-block variation in paired fresh-process log small-control-chain "
                "nanoseconds-per-load ratios on this exact host, binary, and run window"
            ),
        ),
        "by_template": by_template,
    }


def analyze_campaign(metadata_path: Path, attempts_path: Path) -> dict[str, Any]:
    metadata = read_json(metadata_path)
    schedule, config = validate_metadata(metadata)
    rows = read_jsonl(attempts_path)
    results = validate_attempts(metadata_path, metadata, schedule, config, rows)
    blocks = block_rows(schedule, rows, results)
    primary_blocks = [block for block in blocks if block["phase"] == "primary"]
    aa_blocks = [block for block in blocks if block["phase"] == "aa"]
    if len(primary_blocks) != PRIMARY_BLOCKS or len(aa_blocks) != AA_BLOCKS:
        fail("phase block counts changed")
    primary_results = [result for row, result in zip(rows, results) if row["phase"] == "primary"]
    idle = [result for result in primary_results if result["treatment"] == "idle"]
    loaded = [result for result in primary_results if result["treatment"] == "loaded"]
    if len(idle) != PRIMARY_BLOCKS * 2 or len(loaded) != PRIMARY_BLOCKS * 2:
        fail("primary treatment counts changed")
    per_treatment: dict[str, Any] = {}
    for name, selected in (("idle", idle), ("loaded", loaded)):
        per_treatment[name] = {
            "processes": len(selected),
            "probe_ns_per_load": descriptive(
                [item["probe_elapsed_ns"] / item["probe_loads"] for item in selected]
            ),
            "small_ns_per_load": descriptive(
                [item["small_elapsed_ns"] / item["small_loads"] for item in selected]
            ),
            "run_epoch_ms": descriptive([item["run_epoch_ns"] / 1_000_000.0 for item in selected]),
        }
    worker_bounds = {
        "processes": len(loaded),
        "lower_gib_per_s": descriptive([float(item["worker_gib_per_s_lower"]) for item in loaded]),
        "upper_inclusive_gib_per_s": descriptive(
            [float(item["worker_gib_per_s_upper_inclusive"]) for item in loaded]
        ),
        "uncounted_tail_bytes_at_most": len(config["worker_cpus"]) * 256 * 1024,
        "boundary": "application useful source bytes, not cache-line, fabric, or DRAM traffic",
    }
    primary = phase_summary(primary_blocks)
    aa = phase_summary(aa_blocks)
    return {
        "schema": "topic49-analysis.v1",
        "status": "pass",
        "schedule_seed": metadata["schedule_seed"],
        "fixed_horizon": {
            "primary_blocks": PRIMARY_BLOCKS,
            "aa_blocks": AA_BLOCKS,
            "processes": len(rows),
            "replacement_attempts": 0,
        },
        "primary": {
            "comparison": "loaded/idle",
            **primary,
            "per_treatment": per_treatment,
            "worker_useful_bandwidth_bounds": worker_bounds,
        },
        "aa": {
            "comparison": "loaded-path-b/loaded-path-a",
            "mechanical_integrity": "pass",
            "null_calibration_claim": "none; four blocks do not estimate a false-positive rate",
            **aa,
        },
        "blocks": blocks,
        "measured_boundary": (
            "elapsed time, application useful bytes, process counters, affinity canaries, "
            "and mapping observations for one exact host run"
        ),
        "inference_boundary": (
            "no direct claim about DRAM-only latency, controller saturation, bank conflicts, "
            "row hits, refresh, channel mapping, or processor-family behavior"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and analyze a fixed Topic 49 campaign.")
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--attempts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise SystemExit(f"analysis output already exists: {args.output}")
    try:
        summary = analyze_campaign(args.metadata.resolve(), args.attempts.resolve())
    except (OSError, ValueError, TypeError) as error:
        raise SystemExit(f"Topic 49 analysis failed: {error}") from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        destination.flush()
        os.fsync(destination.fileno())


if __name__ == "__main__":
    main()
