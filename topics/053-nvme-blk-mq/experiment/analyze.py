#!/usr/bin/env python3
"""Analyze Topic 53 fresh-process campaigns on the complete-block log scale."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any, NoReturn


BLOCK_BYTES = 4096
T975_DF7 = 2.364624251
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DEVICE = re.compile(r"[A-Za-z0-9_.-]+\Z")
ATTEMPT_KEYS = {
    "schema",
    "scenario",
    "sequence",
    "block",
    "period",
    "template",
    "letter",
    "mode",
    "depth",
    "seed",
    "label",
    "ops",
    "source_sha256",
    "binary_sha256",
    "pid",
    "returncode",
    "timed_out",
    "wall_elapsed_ns",
    "stdout_sha256",
    "stderr_sha256",
    "before_sha256",
    "after_sha256",
    "valid",
    "validation_errors",
    "observed",
    "counter_deltas",
    "before_file",
    "stdout_file",
    "stderr_file",
    "after_file",
    "status_file",
}
SCENARIOS: dict[str, dict[str, Any]] = {
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
        "left": "A",
        "right": "B",
        "left_treatment": ("q1", "direct", 1),
        "right_treatment": ("q8", "direct", 8),
        "ratio": "direct_q8_over_direct_q1_iops",
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
        "left": "X",
        "right": "Y",
        "left_treatment": ("aa-x", "direct", 1),
        "right_treatment": ("aa-y", "direct", 1),
        "ratio": "aa_y_over_aa_x_iops",
    },
}


def fail(message: str) -> NoReturn:
    """Reject malformed or semantically invalid evidence."""
    raise ValueError(message)


def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON keys instead of silently taking the last value."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    """Reject NaN and infinity, which are not valid receipt numbers."""
    fail(f"non-finite JSON number: {token}")


def parse_json(text: str, label: str) -> dict[str, Any]:
    """Parse one strict JSON object."""
    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_pairs,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError) as error:
        fail(f"{label}: invalid JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{label}: expected one JSON object")
    return value


def read_json(path: Path) -> dict[str, Any]:
    """Read one strict JSON object."""
    return parse_json(path.read_text(encoding="utf-8"), str(path))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read newline-terminated strict JSON objects."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.endswith("\n") or not line.strip():
                fail(f"{path}:{line_number}: partial or blank JSONL record")
            rows.append(parse_json(line, f"{path}:{line_number}"))
    if not rows:
        fail(f"{path}: no process records")
    return rows


def is_int(value: object) -> bool:
    """Return true only for integers, excluding booleans."""
    return type(value) is int


def is_number(value: object) -> bool:
    """Return true for finite JSON numbers, excluding booleans."""
    return type(value) in (int, float) and math.isfinite(float(value))


def require_positive_int(value: object, label: str) -> int:
    """Return a strictly positive integer or reject the receipt."""
    if not is_int(value) or value <= 0:
        fail(f"{label}: expected a positive integer")
    return value


def expected_treatment(scenario: str, letter: str) -> tuple[str, str, int]:
    """Return the frozen treatment tuple for one schedule letter."""
    config = SCENARIOS[scenario]
    if letter == config["left"]:
        return config["left_treatment"]
    if letter == config["right"]:
        return config["right_treatment"]
    fail(f"{scenario}: unexpected schedule letter {letter!r}")


def validate_result(
    result: dict[str, Any],
    *,
    scenario: str,
    letter: str,
    seed: int,
    label: str,
    scheduled_ops: int,
    expected_blocks: int,
) -> dict[str, int | float | str]:
    """Validate one probe result and return its analysis fields."""
    treatment, mode, depth = expected_treatment(scenario, letter)
    result_keys = {
        "schema",
        "kind",
        "status",
        "pid",
        "tid",
        "threads_before",
        "threads_after",
        "mode",
        "label",
        "seed",
        "depth",
        "total_ops",
        "bytes",
        "blocks",
        "startup_to_measure_ns",
        "setup_ns",
        "elapsed_ns",
        "iops",
        "mib_s",
        "read_bytes_delta",
        "verified_reads",
        "errors",
        "checksum",
        "peak_outstanding",
        "resident_before",
        "resident_after",
        "total_pages",
        "dioalign_known",
        "dio_mem_align",
        "dio_offset_align",
        "dio_allocation_align",
        "nvcsw",
        "nivcsw",
    }
    if set(result) != result_keys:
        fail(f"{scenario}/{letter}: probe result key set differs")
    exact = {
        "schema": "topic53-probe.v1",
        "kind": "bench",
        "status": "ok",
        "mode": mode,
        "depth": depth,
        "seed": seed,
        "errors": 0,
    }
    for key, wanted in exact.items():
        observed = result.get(key)
        if type(observed) is not type(wanted) or observed != wanted:
            fail(
                f"{scenario}/{letter}: result {key} differs: "
                f"expected {wanted!r}, found {observed!r}"
            )

    if result.get("label") != label or not label.startswith(treatment):
        fail(f"{scenario}/{letter}: result label differs from its schedule")

    total_ops = require_positive_int(result.get("total_ops"), "total_ops")
    byte_count = require_positive_int(result.get("bytes"), "bytes")
    blocks = require_positive_int(result.get("blocks"), "blocks")
    elapsed_ns = require_positive_int(result.get("elapsed_ns"), "elapsed_ns")
    setup_ns = require_positive_int(result.get("setup_ns"), "setup_ns")
    startup_ns = require_positive_int(
        result.get("startup_to_measure_ns"), "startup_to_measure_ns"
    )
    verified = require_positive_int(result.get("verified_reads"), "verified_reads")
    peak = require_positive_int(result.get("peak_outstanding"), "peak_outstanding")
    pid = require_positive_int(result.get("pid"), "pid")
    tid = require_positive_int(result.get("tid"), "tid")
    threads_before = require_positive_int(
        result.get("threads_before"), "threads_before"
    )
    threads_after = require_positive_int(
        result.get("threads_after"), "threads_after"
    )
    read_bytes_delta = result.get("read_bytes_delta")
    if not is_int(read_bytes_delta) or read_bytes_delta < 0:
        fail(f"{scenario}/{letter}: read_bytes_delta is invalid")
    checksum = result.get("checksum")
    if not is_int(checksum) or checksum < 0:
        fail(f"{scenario}/{letter}: checksum is invalid")
    iops = result.get("iops")
    mib_s = result.get("mib_s")
    if not is_number(iops) or iops <= 0 or not is_number(mib_s) or mib_s <= 0:
        fail(f"{scenario}/{letter}: nonpositive or non-finite rate")

    if byte_count != total_ops * BLOCK_BYTES:
        fail(f"{scenario}/{letter}: byte count does not equal 4 KiB per operation")
    if verified != total_ops:
        fail(f"{scenario}/{letter}: not every read was verified")
    if blocks != expected_blocks:
        fail(f"{scenario}/{letter}: data-file block count differs")
    if pid != tid or threads_before != 1 or threads_after != 1:
        fail(f"{scenario}/{letter}: probe did not retain one userspace thread")
    if peak != depth:
        fail(f"{scenario}/{letter}: achieved peak outstanding depth differs")
    if startup_ns < setup_ns:
        fail(f"{scenario}/{letter}: setup exceeds startup-to-measure interval")
    if total_ops != scheduled_ops:
        fail(f"{scenario}/{letter}: probe operation count differs from schedule")

    expected_iops = total_ops * 1e9 / elapsed_ns
    expected_mib_s = byte_count * 1e9 / elapsed_ns / (1024.0 * 1024.0)
    if not math.isclose(float(iops), expected_iops, rel_tol=1e-8, abs_tol=5.1e-7):
        fail(f"{scenario}/{letter}: IOPS does not rederive")
    if not math.isclose(float(mib_s), expected_mib_s, rel_tol=1e-8, abs_tol=5.1e-7):
        fail(f"{scenario}/{letter}: MiB/s does not rederive")

    if read_bytes_delta != byte_count:
        fail(
            f"{scenario}/{letter}: direct storage accounting differs from "
            "requested bytes"
        )
    dio_memory = require_positive_int(result.get("dio_mem_align"), "dio_mem_align")
    dio_offset = require_positive_int(
        result.get("dio_offset_align"), "dio_offset_align"
    )
    dio_allocation = require_positive_int(
        result.get("dio_allocation_align"), "dio_allocation_align"
    )
    if result.get("dioalign_known") != 1:
        fail(f"{scenario}/{letter}: STATX_DIOALIGN evidence is missing")
    if (
        dio_memory & (dio_memory - 1)
        or dio_allocation & (dio_allocation - 1)
        or dio_allocation < dio_memory
        or BLOCK_BYTES % dio_offset != 0
    ):
        fail(f"{scenario}/{letter}: direct-I/O alignment evidence is invalid")
    for key in ("resident_before", "resident_after", "total_pages"):
        if result.get(key) != 0:
            fail(f"{scenario}/{letter}: direct result {key} must be zero")
    for key in ("nvcsw", "nivcsw"):
        if not is_int(result.get(key)) or result[key] < 0:
            fail(f"{scenario}/{letter}: {key} is invalid")

    return {
        "treatment": treatment,
        "iops": float(iops),
        "mib_s": float(mib_s),
        "elapsed_ns": elapsed_ns,
        "setup_ns": setup_ns,
        "startup_to_measure_ns": startup_ns,
        "checksum": checksum,
        "total_ops": total_ops,
        "bytes": byte_count,
    }


def quantiles(values: list[float]) -> dict[str, float | int]:
    """Return a small deterministic distribution summary."""
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "median": statistics.median(ordered),
        "max": ordered[-1],
    }


def analyze_scenario(campaign_root: Path, scenario: str) -> dict[str, Any]:
    """Validate and analyze one fixed balanced campaign."""
    config = SCENARIOS[scenario]
    directory = campaign_root / scenario
    schedule = read_json(directory / "schedule.json")
    templates = config["templates"]
    schedule_keys = {
        "schema",
        "scenario",
        "templates",
        "treatments",
        "seed_base",
        "blocks",
        "processes_per_block",
        "ops_per_process",
        "block_bytes",
        "data_file_bytes",
        "source_sha256",
        "binary_sha256",
        "devices",
        "primary_device",
        "treatment_application_unit",
        "analysis_unit",
        "subsample_unit",
        "stopping",
    }
    if set(schedule) != schedule_keys:
        fail(f"{scenario}: schedule key set differs from the frozen schema")
    expected_schedule = {
        "schema": "topic53-schedule.v1",
        "scenario": scenario,
        "templates": list(templates),
        "blocks": len(templates),
        "processes_per_block": 4,
        "block_bytes": BLOCK_BYTES,
        "data_file_bytes": 128 * 1024 * 1024,
        "treatment_application_unit": "fresh native process",
        "analysis_unit": "complete four-process block",
        "subsample_unit": "one verified 4 KiB O_DIRECT read",
        "stopping": "fixed horizon; stop after first invalid attempt",
    }
    for key, wanted in expected_schedule.items():
        if schedule.get(key) != wanted:
            fail(f"{scenario}: schedule {key} differs from the fixed design")
    expected_treatments = {
        "depth": {
            "A": {"mode": "direct", "depth": 1, "label_prefix": "q1"},
            "B": {"mode": "direct", "depth": 8, "label_prefix": "q8"},
        },
        "aa": {
            "X": {"mode": "direct", "depth": 1, "label_prefix": "aa-x"},
            "Y": {"mode": "direct", "depth": 1, "label_prefix": "aa-y"},
        },
    }[scenario]
    if schedule.get("treatments") != expected_treatments:
        fail(f"{scenario}: treatment mapping differs from the fixed design")
    expected_seed_base = 530100 if scenario == "depth" else 530200
    if schedule.get("seed_base") != expected_seed_base:
        fail(f"{scenario}: seed base differs from the fixed design")
    scheduled_ops = require_positive_int(
        schedule.get("ops_per_process"), f"{scenario} ops_per_process"
    )
    if not 256 <= scheduled_ops <= schedule["data_file_bytes"] // BLOCK_BYTES:
        fail(f"{scenario}: scheduled operation count is outside the fixed bounds")
    for key in ("source_sha256", "binary_sha256"):
        if not isinstance(schedule.get(key), str) or HEX64.fullmatch(schedule[key]) is None:
            fail(f"{scenario}: schedule {key} is invalid")
    if not isinstance(schedule.get("primary_device"), str):
        fail(f"{scenario}: schedule primary_device is invalid")
    devices = schedule.get("devices")
    if (
        not isinstance(devices, list)
        or not devices
        or len(set(devices)) != len(devices)
        or any(
            not isinstance(device, str) or DEVICE.fullmatch(device) is None
            for device in devices
        )
        or schedule["primary_device"] not in devices
    ):
        fail(f"{scenario}: schedule device stack is invalid")

    rows = read_jsonl(directory / "attempts.jsonl")
    if len(rows) != len(templates) * 4:
        fail(f"{scenario}: expected {len(templates) * 4} retained processes")

    grouped: dict[int, list[dict[str, Any]]] = {}
    sequence_seen: set[int] = set()
    pid_seen: set[int] = set()
    for expected_sequence, row in enumerate(rows, 1):
        if set(row) != ATTEMPT_KEYS:
            fail(f"{scenario}: attempt {expected_sequence} key set differs")
        if row.get("schema") != "topic53-attempt.v1":
            fail(f"{scenario}: attempt schema differs")
        if row.get("scenario") != scenario or row.get("valid") is not True:
            fail(f"{scenario}: invalid or cross-scenario attempt entered analysis")
        sequence = row.get("sequence")
        block = row.get("block")
        period = row.get("period")
        if (
            not is_int(sequence)
            or sequence != expected_sequence
            or sequence in sequence_seen
        ):
            fail(f"{scenario}: duplicate or invalid process sequence")
        if not is_int(block) or not 1 <= block <= len(templates):
            fail(f"{scenario}: invalid block number")
        if not is_int(period) or not 1 <= period <= 4:
            fail(f"{scenario}: invalid period number")
        sequence_seen.add(sequence)
        grouped.setdefault(block, []).append(row)

    left_rates: list[float] = []
    right_rates: list[float] = []
    block_contrasts: list[dict[str, Any]] = []
    total_ops: set[int] = set()
    byte_counts: set[int] = set()

    for block_number, template in enumerate(templates, 1):
        block_rows = grouped.get(block_number, [])
        if len(block_rows) != 4:
            fail(f"{scenario}: block {block_number} is incomplete")
        block_rows.sort(key=lambda row: row["period"])
        if [row["period"] for row in block_rows] != [1, 2, 3, 4]:
            fail(f"{scenario}: block {block_number} periods are not exact")
        if "".join(str(row.get("letter")) for row in block_rows) != template:
            fail(f"{scenario}: block {block_number} treatment order changed")

        seeds = {row.get("seed") for row in block_rows}
        if len(seeds) != 1 or any(not is_int(seed) or seed < 0 for seed in seeds):
            fail(f"{scenario}: block {block_number} does not share one valid seed")
        seed = next(iter(seeds))
        assert isinstance(seed, int)
        if seed != expected_seed_base + block_number:
            fail(f"{scenario}: block {block_number} seed differs")

        left: list[float] = []
        right: list[float] = []
        block_checksums: set[int] = set()
        for row in block_rows:
            letter = row.get("letter")
            if not isinstance(letter, str):
                fail(f"{scenario}: attempt letter is missing")
            result = row.get("result")
            if result is None:
                result = row.get("observed")
            if not isinstance(result, dict):
                fail(f"{scenario}: parsed probe result is missing")
            label = row.get("label")
            if not isinstance(label, str):
                fail(f"{scenario}: attempt label is missing")
            treatment_name, expected_mode, expected_depth = expected_treatment(
                scenario, letter
            )
            expected_label = f"{treatment_name}-b{block_number:02d}-p{row['period']}"
            stem = (
                f"{row['sequence']:03d}-b{block_number:02d}-"
                f"p{row['period']}-{expected_label}"
            )
            expected_row = {
                "template": template,
                "mode": expected_mode,
                "depth": expected_depth,
                "seed": seed,
                "label": expected_label,
                "ops": scheduled_ops,
                "source_sha256": schedule["source_sha256"],
                "binary_sha256": schedule["binary_sha256"],
                "returncode": 0,
                "timed_out": False,
                "valid": True,
                "validation_errors": [],
                "before_file": f"raw/{stem}.before.json",
                "stdout_file": f"raw/{stem}.stdout",
                "stderr_file": f"raw/{stem}.stderr",
                "after_file": f"raw/{stem}.after.json",
                "status_file": f"raw/{stem}.status.json",
            }
            for key, wanted in expected_row.items():
                if row.get(key) != wanted:
                    fail(f"{scenario}: attempt {row['sequence']} {key} differs")
            pid = require_positive_int(row.get("pid"), "attempt pid")
            if pid in pid_seen:
                fail(f"{scenario}: native pid was reused")
            pid_seen.add(pid)
            if result.get("pid") != pid:
                fail(f"{scenario}: native pid differs from attempt status")
            wall_elapsed_ns = require_positive_int(
                row.get("wall_elapsed_ns"), "attempt wall_elapsed_ns"
            )
            for key in (
                "stdout_sha256",
                "stderr_sha256",
                "before_sha256",
                "after_sha256",
            ):
                if not isinstance(row.get(key), str) or HEX64.fullmatch(row[key]) is None:
                    fail(f"{scenario}: attempt {row['sequence']} {key} is invalid")
            observed = validate_result(
                result,
                scenario=scenario,
                letter=letter,
                seed=seed,
                label=label,
                scheduled_ops=scheduled_ops,
                expected_blocks=schedule["data_file_bytes"] // BLOCK_BYTES,
            )
            if wall_elapsed_ns < int(observed["elapsed_ns"]):
                fail(f"{scenario}: process wall time is shorter than measurement")
            deltas = row.get("counter_deltas")
            if not isinstance(deltas, dict) or set(deltas) != {
                "devices",
                "psi_total_us",
                "vmstat",
            }:
                fail(f"{scenario}: retained counter delta schema differs")
            delta_devices = deltas["devices"]
            if not isinstance(delta_devices, dict) or set(delta_devices) != set(devices):
                fail(f"{scenario}: retained counter device set differs")
            for device, evidence in delta_devices.items():
                if (
                    not isinstance(evidence, dict)
                    or set(evidence) != {"stat", "inflight"}
                    or not isinstance(evidence["stat"], list)
                    or len(evidence["stat"]) < 11
                    or any(not is_int(value) for value in evidence["stat"])
                    or not isinstance(evidence["inflight"], list)
                    or len(evidence["inflight"]) != 2
                    or any(not is_int(value) for value in evidence["inflight"])
                ):
                    fail(f"{scenario}: {device} counter delta is invalid")
                for field, value in enumerate(evidence["stat"]):
                    if field != 8 and value < 0:
                        fail(f"{scenario}: {device} cumulative counter moved backward")
            primary = delta_devices[schedule["primary_device"]]["stat"]
            if primary[0] <= 0 or primary[2] < int(observed["bytes"]) // 512:
                fail(f"{scenario}: primary-device read accounting is insufficient")
            psi = deltas["psi_total_us"]
            vmstat = deltas["vmstat"]
            if (
                not isinstance(psi, dict)
                or set(psi) != {"some", "full"}
                or any(not is_int(value) or value < 0 for value in psi.values())
                or not isinstance(vmstat, dict)
                or set(vmstat) != {"pgpgin", "pgpgout", "nr_dirty", "nr_writeback"}
                or any(not is_int(value) for value in vmstat.values())
            ):
                fail(f"{scenario}: PSI or vmstat counter delta is invalid")
            rate = float(observed["iops"])
            block_checksums.add(int(observed["checksum"]))
            total_ops.add(int(observed["total_ops"]))
            byte_counts.add(int(observed["bytes"]))
            if letter == config["left"]:
                left.append(rate)
                left_rates.append(rate)
            elif letter == config["right"]:
                right.append(rate)
                right_rates.append(rate)
            else:
                fail(f"{scenario}: unknown treatment letter")

        if len(left) != 2 or len(right) != 2:
            fail(f"{scenario}: block {block_number} lacks two runs per treatment")
        if len(block_checksums) != 1:
            fail(f"{scenario}: paired processes read different logical data")

        left_geomean = math.exp(statistics.mean(math.log(value) for value in left))
        right_geomean = math.exp(statistics.mean(math.log(value) for value in right))
        log_ratio = math.log(right_geomean) - math.log(left_geomean)
        block_contrasts.append(
            {
                "block": block_number,
                "template": template,
                "left_geomean_iops": left_geomean,
                "right_geomean_iops": right_geomean,
                "log_ratio": log_ratio,
                "right_over_left": math.exp(log_ratio),
            }
        )

    if len(total_ops) != 1 or len(byte_counts) != 1:
        fail(f"{scenario}: fixed work changed between fresh processes")

    log_ratios = [float(item["log_ratio"]) for item in block_contrasts]
    mean_log = statistics.mean(log_ratios)
    log_sd = statistics.stdev(log_ratios)
    half_width = T975_DF7 * log_sd / math.sqrt(len(log_ratios))
    interval = [math.exp(mean_log - half_width), math.exp(mean_log + half_width)]
    point = math.exp(mean_log)

    return {
        "scenario": scenario,
        "ratio_name": config["ratio"],
        "fresh_process_count": len(rows),
        "whole_block_count": len(block_contrasts),
        "total_ops_per_process": next(iter(total_ops)),
        "bytes_per_process": next(iter(byte_counts)),
        "point_ratio": point,
        "ratio_95pct_student_t_interval": interval,
        "log_contrast_sd": log_sd,
        "left_iops": quantiles(left_rates),
        "right_iops": quantiles(right_rates),
        "block_contrasts": block_contrasts,
    }


def build_analysis(campaign_root: Path) -> dict[str, Any]:
    """Return the complete deterministic Topic 53 analysis."""
    scenarios = {
        name: analyze_scenario(campaign_root, name) for name in ("depth", "aa")
    }
    aa_interval = scenarios["aa"]["ratio_95pct_student_t_interval"]
    assert isinstance(aa_interval, list)
    aa_point = scenarios["aa"]["point_ratio"]
    assert isinstance(aa_point, float)
    aa_criteria = {
        "point_ratio_within_0_95_to_1_05": 0.95 <= aa_point <= 1.05,
        "interval_contains_1": aa_interval[0] <= 1.0 <= aa_interval[1],
        "interval_within_0_90_to_1_10": (
            0.90 <= aa_interval[0] and aa_interval[1] <= 1.10
        ),
    }
    aa_pass = all(aa_criteria.values())
    return {
        "schema": "topic53-analysis.v1",
        "method": (
            "mean complete-block log IOPS ratio with a two-sided 95% "
            "Student-t interval across eight whole-process blocks"
        ),
        "interval_scope": (
            "between-block process variation on one host, source, binary, kernel, "
            "filesystem, block stack, and run window; excludes host-population and "
            "device-population variation"
        ),
        "analysis_unit": "whole four-process block; inner reads are not samples",
        "aa_acceptance": aa_criteria,
        "aa_control_pass": aa_pass,
        "measurement_usable": aa_pass,
        "scenarios": scenarios,
    }


def main() -> int:
    """Parse arguments, analyze the campaign, and emit stable compact JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root", type=Path)
    arguments = parser.parse_args()
    root = arguments.campaign_root.resolve(strict=True)
    result = build_analysis(root)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["measurement_usable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
