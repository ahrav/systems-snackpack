#!/usr/bin/env python3
"""Run Topic 25 as retained fresh-process, counterbalanced NUMA blocks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

MAPPING_BYTES = 512 * 1024 * 1024
PASSES = 4
AB_BLOCKS_PER_DIRECTION = 8
AA_BLOCKS_PER_DIRECTION = 4
SCHEDULE_SEED = 25_202_608_04
TIMEOUT_SECONDS = 300
MEASUREMENT_KEYS = {
    "schema", "kind", "treatment", "direction", "mapping_bytes", "page_size",
    "page_count", "passes", "loads", "permutation_seed", "permutation_start",
    "permutation_step", "pair_nodes", "pair_cpus", "pair_distances", "worker_node",
    "worker_cpu", "touch_node", "touch_cpu", "peer_node", "peer_cpu",
    "access_distance", "touch_affinity", "worker_affinity", "madv_nohugepage",
    "smaps", "placement_before", "placement_after", "touch_ns", "read_ns",
    "ns_per_load", "touch_minor_faults", "touch_major_faults", "read_minor_faults",
    "read_major_faults", "checksum", "expected_checksum", "checksum_ok",
    "read_faults_zero",
}


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def exact_json_line(stdout: str) -> dict[str, Any]:
    if not stdout.endswith("\n") or stdout.count("\n") != 1:
        fail("probe stdout must be exactly one newline-terminated JSON line")
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as error:
        fail(f"probe emitted invalid JSON: {error}")
    if not isinstance(value, dict):
        fail("probe JSON must be an object")
    return value


def validate_topology(value: dict[str, Any]) -> None:
    required = {
        "schema", "kind", "mapping_bytes", "all_node_count", "eligible_node_count",
        "control_supported", "control_node", "control_cpu", "control_distance",
        "supported",
    }
    required |= (
        {"pair_nodes", "pair_cpus", "pair_distances"}
        if value.get("supported") is True
        else {"reason"}
    )
    if set(value) != required:
        fail(f"topology fields differ: {sorted(set(value) ^ required)}")
    if value["schema"] != 1 or value["kind"] != "topology":
        fail("unsupported topology schema")
    if value["mapping_bytes"] != MAPPING_BYTES:
        fail("topology mapping size differs from the fixed 512 MiB design")
    if value["control_supported"] is not True or value["eligible_node_count"] < 1:
        fail("host does not support the required one-node correctness control")
    if value["control_node"] < 0 or value["control_cpu"] < 0:
        fail("topology returned an invalid control node or CPU")
    if value["supported"] is not True:
        if value["eligible_node_count"] >= 2:
            fail("two eligible nodes were reported without a supported reciprocal pair")
        return
    for field in ("pair_nodes", "pair_cpus", "pair_distances"):
        if not isinstance(value[field], list) or len(value[field]) != 2:
            fail(f"topology {field} must contain two entries")
    if value["pair_nodes"][0] == value["pair_nodes"][1]:
        fail("topology selected the same node twice")
    if value["pair_cpus"][0] == value["pair_cpus"][1]:
        fail("topology selected the same CPU twice")


def validate_affinity(value: Any, expected_cpu: int, name: str) -> None:
    fields = {"requested_cpu", "effective_cpu", "current_cpu", "effective_count"}
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{name} affinity fields differ")
    if value["effective_count"] != 1 or any(
        value[key] != expected_cpu for key in ("requested_cpu", "effective_cpu", "current_cpu")
    ):
        fail(f"{name} affinity is not the requested effective singleton")


def validate_placement(value: Any, pages: int, name: str) -> None:
    fields = {"syscall_result", "expected_pages", "other_pages", "error_pages"}
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{name} placement fields differ")
    total = value["expected_pages"] + value["other_pages"] + value["error_pages"]
    if total != pages or value["syscall_result"] != 0 or value["error_pages"] != 0:
        fail(f"{name} move_pages query is incomplete or erroneous")


def validate_measurement(
    value: dict[str, Any], treatment: str, direction: int, topology: dict[str, Any]
) -> None:
    if set(value) != MEASUREMENT_KEYS:
        fail(f"measurement fields differ: {sorted(set(value) ^ MEASUREMENT_KEYS)}")
    if value["schema"] != 1 or value["kind"] != "measurement":
        fail("unsupported measurement schema")
    control = treatment == "control"
    pair_nodes = (
        [topology["control_node"], topology["control_node"]]
        if control else topology["pair_nodes"]
    )
    pair_cpus = (
        [topology["control_cpu"], topology["control_cpu"]]
        if control else topology["pair_cpus"]
    )
    pair_distances = (
        [topology["control_distance"], topology["control_distance"]]
        if control else topology["pair_distances"]
    )
    fixed = {
        "treatment": treatment,
        "direction": direction,
        "mapping_bytes": MAPPING_BYTES,
        "passes": PASSES,
        "pair_nodes": pair_nodes,
        "pair_cpus": pair_cpus,
        "pair_distances": pair_distances,
    }
    for field, expected in fixed.items():
        if value[field] != expected:
            fail(f"measurement {field} differs: {value[field]!r} != {expected!r}")
    if value["page_count"] * value["page_size"] != MAPPING_BYTES:
        fail("page count and page size do not cover the mapping")
    if value["loads"] != value["page_count"] * PASSES:
        fail("load count differs from complete permutation passes")
    if math.gcd(value["permutation_step"], value["page_count"]) != 1:
        fail("pointer permutation is not a single cycle")
    expected_worker_node = pair_nodes[direction]
    expected_worker_cpu = pair_cpus[direction]
    expected_peer_node = pair_nodes[1 - direction]
    expected_peer_cpu = pair_cpus[1 - direction]
    if (value["worker_node"], value["worker_cpu"], value["peer_node"], value["peer_cpu"]) != (
        expected_worker_node, expected_worker_cpu, expected_peer_node, expected_peer_cpu
    ):
        fail("worker/peer selection differs from discovered reciprocal pair")
    expected_touch = (
        (expected_worker_node, expected_worker_cpu)
        if treatment in {"local", "control"}
        else (expected_peer_node, expected_peer_cpu)
    )
    if (value["touch_node"], value["touch_cpu"]) != expected_touch:
        fail("first-touch placement differs from treatment")
    validate_affinity(value["touch_affinity"], expected_touch[1], "touch")
    validate_affinity(value["worker_affinity"], expected_worker_cpu, "worker")
    smaps = value["smaps"]
    if not isinstance(smaps, dict) or set(smaps) != {
        "exact_vma", "vmflag_nh", "anon_huge_kib", "kernel_page_kib",
        "mmu_page_kib", "thp_eligible",
    }:
        fail("smaps fields differ")
    if value["madv_nohugepage"] is not True or smaps["exact_vma"] is not True or (
        smaps["vmflag_nh"] is not True or smaps["anon_huge_kib"] != 0
        or smaps["thp_eligible"] != 0
    ):
        fail("smaps does not prove an exact non-THP VMA")
    validate_placement(value["placement_before"], value["page_count"], "before")
    validate_placement(value["placement_after"], value["page_count"], "after")
    if any(
        value[field]["expected_pages"] != value["page_count"]
        or value[field]["other_pages"] != 0
        for field in ("placement_before", "placement_after")
    ):
        fail("every page must remain on the expected node before and after reading")
    if value["checksum_ok"] is not True or value["checksum"] != value["expected_checksum"]:
        fail("dependent chase checksum failed")
    if value["read_faults_zero"] is not True or value["read_minor_faults"] != 0 or (
        value["read_major_faults"] != 0
    ):
        fail("timed dependent chase incurred a page fault")
    if value["read_ns"] <= 0 or value["touch_ns"] <= 0:
        fail("phase timings must be positive")
    if not math.isclose(value["ns_per_load"], value["read_ns"] / value["loads"], rel_tol=1e-9):
        fail("ns_per_load differs from timed read_ns / loads")


def schedule_per_direction(blocks: int, rng: random.Random) -> list[dict[str, Any]]:
    """Create an equal ABBA/BAAB schedule separately for each direction."""
    if blocks <= 0 or blocks % 2 != 0:
        fail("blocks per direction must be a positive even number")
    result: list[dict[str, Any]] = []
    block_id = 1
    for direction in (0, 1):
        templates = ["ABBA"] * (blocks // 2) + ["BAAB"] * (blocks // 2)
        rng.shuffle(templates)
        for template in templates:
            result.append({"block": block_id, "template": template, "direction": direction})
            block_id += 1
    return result


def invoke(
    binary: Path,
    label: str,
    treatment: str,
    direction: int,
    identity: dict[str, Any],
    attempts,
    topology: dict[str, Any],
) -> dict[str, Any] | None:
    command = (
        [str(binary), "--control", "--passes", str(PASSES)]
        if treatment == "control"
        else [
            str(binary), "--treatment", treatment, "--direction", str(direction),
            "--passes", str(PASSES),
        ]
    )
    started = time.monotonic_ns()
    timed_out = False
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, check=False, timeout=TIMEOUT_SECONDS
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = None
        stdout = error.stdout or ""
        stderr = error.stderr or ""
    process_ns = time.monotonic_ns() - started
    parse_status = "ok"
    parse_error = ""
    parsed: dict[str, Any] | None = None
    try:
        if timed_out:
            fail("probe timed out")
        if returncode != 0:
            fail(f"probe exited {returncode}")
        if stderr:
            fail("probe wrote to stderr")
        parsed = exact_json_line(stdout)
        validate_measurement(parsed, treatment, direction, topology)
    except SystemExit as error:
        parse_status = "error"
        parse_error = str(error)
    attempt = {
        **identity,
        "label": label,
        "treatment": treatment,
        "command": command,
        "timeout_seconds": TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "returncode": returncode,
        "process_ns": process_ns,
        "stdout": stdout,
        "stderr": stderr,
        "parse_status": parse_status,
        "parse_error": parse_error,
    }
    attempts.write(json.dumps(attempt, sort_keys=True) + "\n")
    attempts.flush()
    if parsed is None:
        return None
    return {**identity, "label": label, "process_ns": process_ns, **parsed}


def log_contrast(rows: list[dict[str, Any]], numerator: str, denominator: str) -> float:
    numerator_logs = [math.log(row["read_ns"]) for row in rows if row["label"] == numerator]
    denominator_logs = [math.log(row["read_ns"]) for row in rows if row["label"] == denominator]
    if len(numerator_logs) != 2 or len(denominator_logs) != 2:
        fail("complete four-period block is missing")
    return statistics.fmean(numerator_logs) - statistics.fmean(denominator_logs)


def interval(contrasts: list[float]) -> dict[str, Any]:
    critical = {
        4: 3.182446305,
        8: 2.364624251,
        16: 2.131449546,
    }.get(len(contrasts))
    if critical is None:
        fail("no predeclared Student-t critical value for contrast count")
    mean = statistics.fmean(contrasts)
    half = critical * statistics.stdev(contrasts) / math.sqrt(len(contrasts))
    return {
        "n_complete_blocks": len(contrasts),
        "geometric_mean_ratio": math.exp(mean),
        "log_t_95_low": math.exp(mean - half),
        "log_t_95_high": math.exp(mean + half),
        "mean_log_contrast": mean,
        "log_sd": statistics.stdev(contrasts),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        fail(f"binary is unavailable: {binary}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        fail("output directory must be absent or empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    binary_digest = sha256(binary)
    describe = subprocess.run(
        [str(binary), "--describe"], text=True, capture_output=True, check=False,
        timeout=TIMEOUT_SECONDS,
    )
    topology_attempt = {
        "command": [str(binary), "--describe"], "returncode": describe.returncode,
        "stdout": describe.stdout, "stderr": describe.stderr,
    }
    write_json(args.output_dir / "topology-attempt.json", topology_attempt)
    if describe.returncode != 0 or describe.stderr:
        fail("topology probe failed; raw attempt retained")
    topology = exact_json_line(describe.stdout)
    validate_topology(topology)
    write_json(args.output_dir / "topology.json", topology)

    rng = random.Random(SCHEDULE_SEED)
    if topology["supported"] is not True:
        design = {
            "schema": 1,
            "mode": "one-node-correctness-control",
            "binary_sha256": binary_digest,
            "mapping_bytes": MAPPING_BYTES,
            "passes": PASSES,
            "fixed_processes": 4,
            "estimand": None,
            "timing_claim": "none; diagnostic elapsed values are retained only",
        }
        write_json(args.output_dir / "design.json", design)
        observations: list[dict[str, Any]] = []
        failures = 0
        with (args.output_dir / "attempts.jsonl").open("x", encoding="utf-8") as attempts:
            for sequence in range(4):
                identity = {
                    "family": "control", "block": sequence + 1,
                    "template": "C", "direction": 0,
                    "position": 1, "sequence": sequence,
                }
                result = invoke(
                    binary, "C", "control", 0, identity, attempts, topology
                )
                if result is None:
                    failures += 1
                else:
                    observations.append(result)
        with (args.output_dir / "observations.jsonl").open("x", encoding="utf-8") as stream:
            for row in observations:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        complete = failures == 0 and len(observations) == 4
        summary = {
            "schema": 1,
            "mode": "one-node-correctness-control",
            "binary_sha256": binary_digest,
            "attempt_count": 4,
            "valid_observation_count": len(observations),
            "remote_local_estimate": None,
            "diagnostic_read_ns": [row["read_ns"] for row in observations],
            "all_pages_stayed_on_control_node": complete,
        }
        write_json(args.output_dir / "summary.json", summary)
        write_json(args.output_dir / "run-status.json", {
            "complete": complete, "attempts": 4,
            "valid_observations": len(observations), "invalid_attempts": failures,
        })
        if not complete:
            fail("one-node correctness control is incomplete")
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    ab_schedule = schedule_per_direction(AB_BLOCKS_PER_DIRECTION, rng)
    aa_schedule = schedule_per_direction(AA_BLOCKS_PER_DIRECTION, rng)
    design = {
        "schema": 1,
        "binary_sha256": binary_digest,
        "mapping_bytes": MAPPING_BYTES,
        "passes": PASSES,
        "schedule_seed": SCHEDULE_SEED,
        "ab_schedule": ab_schedule,
        "aa_schedule": aa_schedule,
        "analysis_unit": "one complete four-process ABBA or BAAB block",
        "stopping": (
            "fixed 8 A/B blocks and 4 A/A blocks in each reciprocal direction; "
            "no peeking or retry"
        ),
        "invalid_attempt_policy": "retain every attempt; any invalid or incomplete block fails the run",
        "estimand": "geometric-mean remote/local ratio of dependent-chase read_ns",
        "interval": "two-sided 95% Student-t interval over complete-block log contrasts",
    }
    write_json(args.output_dir / "design.json", design)

    observations: list[dict[str, Any]] = []
    failures = 0
    sequence = 0
    with (args.output_dir / "attempts.jsonl").open("x", encoding="utf-8") as attempts:
        for family, blocks in (("ab", ab_schedule), ("aa", aa_schedule)):
            for block in blocks:
                for position, letter in enumerate(block["template"], start=1):
                    if family == "ab":
                        label = letter
                        treatment = "local" if letter == "A" else "remote"
                    else:
                        label = "A0" if letter == "A" else "A1"
                        treatment = "local"
                    identity = {
                        "family": family, "block": block["block"],
                        "template": block["template"], "direction": block["direction"],
                        "position": position, "sequence": sequence,
                    }
                    result = invoke(
                        binary, label, treatment, block["direction"], identity,
                        attempts, topology,
                    )
                    if result is None:
                        failures += 1
                    else:
                        observations.append(result)
                    sequence += 1

    with (args.output_dir / "observations.jsonl").open("x", encoding="utf-8") as stream:
        for row in observations:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    expected_observations = 2 * (
        AB_BLOCKS_PER_DIRECTION + AA_BLOCKS_PER_DIRECTION
    ) * 4
    if failures or len(observations) != expected_observations:
        write_json(args.output_dir / "run-status.json", {
            "complete": False, "attempts": sequence, "valid_observations": len(observations),
            "invalid_attempts": failures,
        })
        fail("one or more attempts failed; retained run is incomplete")

    contrast_rows: list[dict[str, Any]] = []
    for family, blocks in (("ab", ab_schedule), ("aa", aa_schedule)):
        for block in blocks:
            rows = [
                row for row in observations
                if row["family"] == family and row["block"] == block["block"]
            ]
            numerator, denominator = (("B", "A") if family == "ab" else ("A1", "A0"))
            contrast = log_contrast(rows, numerator, denominator)
            contrast_rows.append({
                "family": family, "block": block["block"],
                "template": block["template"], "direction": block["direction"],
                "log_contrast": contrast, "ratio": math.exp(contrast),
            })
    with (args.output_dir / "block-contrasts.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(contrast_rows[0]))
        writer.writeheader()
        writer.writerows(contrast_rows)

    ab = [row["log_contrast"] for row in contrast_rows if row["family"] == "ab"]
    aa = [row["log_contrast"] for row in contrast_rows if row["family"] == "aa"]
    summary = {
        "schema": 1,
        "binary_sha256": binary_digest,
        "attempt_count": sequence,
        "valid_observation_count": len(observations),
        "ab": interval(ab),
        "direction_0": interval([
            row["log_contrast"] for row in contrast_rows
            if row["family"] == "ab" and row["direction"] == 0
        ]),
        "direction_1": interval([
            row["log_contrast"] for row in contrast_rows
            if row["family"] == "ab" and row["direction"] == 1
        ]),
        "aa": interval(aa),
        "aa_direction_0": interval([
            row["log_contrast"] for row in contrast_rows
            if row["family"] == "aa" and row["direction"] == 0
        ]),
        "aa_direction_1": interval([
            row["log_contrast"] for row in contrast_rows
            if row["family"] == "aa" and row["direction"] == 1
        ]),
        "aa_scope": "mechanical path-asymmetry diagnostic, not long-run null calibration",
        "placement_after_changed_pages": sum(
            row["placement_after"]["other_pages"] for row in observations
        ),
    }
    write_json(args.output_dir / "summary.json", summary)
    write_json(args.output_dir / "run-status.json", {
        "complete": True, "attempts": sequence, "valid_observations": len(observations),
        "invalid_attempts": 0,
    })
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SystemExit as error:
        if str(error):
            print(str(error), file=sys.stderr)
        raise
