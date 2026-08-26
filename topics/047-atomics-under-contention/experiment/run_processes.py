#!/usr/bin/env python3
"""Run the fixed Topic 47 process schedule and retain every attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path


MODES = ("shared", "cas", "striped", "batched")
MODE_BY_LABEL = dict(zip("ABCD", MODES))
WILLIAMS_TEMPLATES = ("ABDC", "BCAD", "CDBA", "DACB")
PRIMARY_PAIRS = (("cas", "shared"), ("striped", "shared"), ("batched", "shared"))
RECORDED_BINARY = "binary/atomic_contention"
RESULT_KEYS = {
    "schema", "label", "mode", "threads", "iterations_per_thread",
    "warmup_iterations_per_thread", "batch_size", "logical_ops",
    "rmw_attempts", "cas_retries", "final_count", "correct", "affinity_ok",
    "startup_ns", "warmup_ns", "steady_ns", "teardown_ns", "total_ns",
    "coordinator_cpu", "worker_cpus", "worker_start_cpus", "worker_end_cpus",
    "stripe_alignment",
}
PROBE_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": os.defpath,
    "TZ": "UTC",
}


def parse_cpu_csv(value: str) -> list[int]:
    try:
        cpus = [int(part) for part in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("worker CPUs must be comma-separated integers") from error
    if not cpus or any(cpu < 0 for cpu in cpus) or len(set(cpus)) != len(cpus):
        raise argparse.ArgumentTypeError("worker CPUs must be distinct nonnegative integers")
    return cpus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--threads", required=True, type=int)
    parser.add_argument("--iterations", required=True, type=int)
    parser.add_argument("--warmup-iterations", required=True, type=int)
    parser.add_argument("--batch-size", required=True, type=int)
    parser.add_argument("--coordinator-cpu", required=True, type=int)
    parser.add_argument("--worker-cpus", required=True, type=parse_cpu_csv)
    parser.add_argument("--blocks", default=12, type=int)
    parser.add_argument("--aa-blocks", default=4, type=int)
    parser.add_argument("--seed", default=20260826, type=int)
    parser.add_argument("--timeout-seconds", default=120.0, type=float)
    parser.add_argument("--bootstrap-draws", default=20_000, type=int)
    args = parser.parse_args()
    if (
        args.threads <= 0
        or args.iterations <= 0
        or args.warmup_iterations <= 0
        or args.batch_size <= 0
        or args.coordinator_cpu < 0
        or args.threads != len(args.worker_cpus)
        or args.coordinator_cpu in args.worker_cpus
        or args.blocks < 4
        or args.blocks % 4
        or args.aa_blocks < 2
        or args.aa_blocks % 2
        or args.seed <= 0
        or args.timeout_seconds <= 0
        or args.bootstrap_draws <= 0
    ):
        parser.error(
            "use positive work, one worker CPU per thread, a distinct coordinator, "
            "primary blocks divisible by four, and an even A/A count"
        )
    return args


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_schedule(blocks: int, aa_blocks: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    primary = []
    cycles = blocks // len(WILLIAMS_TEMPLATES)
    for cycle in range(1, cycles + 1):
        for template in WILLIAMS_TEMPLATES:
            primary.append({
                "kind": "primary",
                "block": f"primary-{cycle:02d}-{template}",
                "cycle": cycle,
                "template": template,
                "order": [MODE_BY_LABEL[label] for label in template],
            })
    rng.shuffle(primary)
    aa_templates = ["ABBA"] * (aa_blocks // 2) + ["BAAB"] * (aa_blocks // 2)
    rng.shuffle(aa_templates)
    aa = [
        {
            "kind": "aa",
            "block": f"aa-{index:02d}",
            "template": template,
            "order": ["shared"] * 4,
        }
        for index, template in enumerate(aa_templates, 1)
    ]
    schedule = primary + aa
    rng.shuffle(schedule)
    return schedule


def append_jsonl(handle, record: dict) -> None:
    handle.write(json.dumps(record, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def integer(value: object) -> bool:
    return type(value) is int


def exact_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            exact_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_result(result: object, mode: str, bench_label: str, args: argparse.Namespace) -> bool:
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        return False
    logical_ops = args.threads * args.iterations
    expected = {
        "schema": "atomics-contention.v1",
        "label": bench_label,
        "mode": mode,
        "threads": args.threads,
        "iterations_per_thread": args.iterations,
        "warmup_iterations_per_thread": args.warmup_iterations,
        "batch_size": args.batch_size,
        "logical_ops": logical_ops,
        "final_count": logical_ops,
        "correct": True,
        "affinity_ok": True,
        "coordinator_cpu": args.coordinator_cpu,
        "worker_cpus": args.worker_cpus,
        "worker_start_cpus": args.worker_cpus,
        "worker_end_cpus": args.worker_cpus,
        "stripe_alignment": 128,
    }
    if not exact_equal({key: result.get(key) for key in expected}, expected):
        return False
    count_fields = ("logical_ops", "rmw_attempts", "cas_retries", "final_count")
    phase_fields = ("startup_ns", "warmup_ns", "steady_ns", "teardown_ns", "total_ns")
    if any(not integer(result.get(key)) or result[key] < 0 for key in count_fields + phase_fields):
        return False
    if result["total_ns"] != sum(result[key] for key in phase_fields[:-1]):
        return False
    if mode == "cas":
        if result["rmw_attempts"] != logical_ops + result["cas_retries"]:
            return False
    elif result["cas_retries"] != 0:
        return False
    elif mode in ("shared", "striped"):
        if result["rmw_attempts"] != logical_ops:
            return False
    elif mode == "batched":
        expected_flushes = args.threads * math.ceil(args.iterations / args.batch_size)
        if result["rmw_attempts"] != expected_flushes:
            return False
    else:
        return False
    return True


def normalized_output(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def run_attempt(
    binary: Path,
    expected_binary_sha256: str,
    block: dict,
    position: int,
    label: str,
    mode: str,
    attempt_number: int,
    args: argparse.Namespace,
) -> dict:
    bench_label = f"{block['kind']}:{block['block']}:{label}"
    worker_csv = ",".join(map(str, args.worker_cpus))
    command = [
        f"./{RECORDED_BINARY}", mode, str(args.threads), str(args.iterations),
        str(args.warmup_iterations), str(args.batch_size),
        str(args.coordinator_cpu), worker_csv,
    ]
    environment = dict(PROBE_ENVIRONMENT)
    environment["BENCH_LABEL"] = bench_label
    record = {
        "attempt": attempt_number,
        "kind": block["kind"],
        "block": block["block"],
        "cycle": block.get("cycle"),
        "template": block["template"],
        "position": position,
        "label": label,
        "bench_label": bench_label,
        "mode": mode,
        "command": command,
        "environment": environment,
        "timeout_seconds": args.timeout_seconds,
    }
    try:
        record["binary_sha256_before"] = sha256(binary)
    except OSError as error:
        record["binary_sha256_before"] = None
        record["binary_hash_before_error"] = repr(error)
    wall_start = time.monotonic_ns()
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout_seconds,
            env=environment,
            cwd=binary.parent.parent,
        )
        record.update({
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        })
    except subprocess.TimeoutExpired as error:
        record.update({
            "returncode": None,
            "stdout": normalized_output(error.stdout),
            "stderr": normalized_output(error.stderr),
            "timed_out": True,
        })
    except OSError as error:
        record.update({
            "returncode": None,
            "stdout": "",
            "stderr": repr(error),
            "timed_out": False,
        })
    record["process_wall_ns"] = time.monotonic_ns() - wall_start
    try:
        record["binary_sha256_after"] = sha256(binary)
    except OSError as error:
        record["binary_sha256_after"] = None
        record["binary_hash_after_error"] = repr(error)
    try:
        lines = record["stdout"].splitlines()
        if len(lines) != 1:
            raise ValueError("probe must emit exactly one JSON line")
        result = json.loads(lines[0], object_pairs_hook=reject_duplicate_keys)
        if not isinstance(result, dict):
            raise ValueError("probe JSON must be an object")
        record["result"] = result
        record["protocol_valid"] = (
            type(record["returncode"]) is int
            and record["returncode"] == 0
            and record["timed_out"] is False
            and record["binary_sha256_before"] == expected_binary_sha256
            and record["binary_sha256_after"] == expected_binary_sha256
            and strict_result(result, mode, bench_label, args)
        )
        record["steady_analysis_valid"] = (
            record["protocol_valid"] and result["steady_ns"] > 0
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        record["parse_error"] = repr(error)
        record["protocol_valid"] = False
        record["steady_analysis_valid"] = False
    record["valid"] = record["protocol_valid"] and record["steady_analysis_valid"]
    return record


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    location = probability * (len(ordered) - 1)
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return ordered[lower]
    weight = location - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_contrasts(values: list[float], seed: int, draws: int) -> dict:
    if len(values) < 2:
        return {"complete_blocks": len(values), "estimable": False}
    mean_log = statistics.fmean(values)
    rng = random.Random(seed)
    bootstrap = [
        math.exp(statistics.fmean(rng.choice(values) for _ in values))
        for _ in range(draws)
    ]
    return {
        "complete_blocks": len(values),
        "estimable": True,
        "geometric_mean_ratio": math.exp(mean_log),
        "log_contrast_mean": mean_log,
        "log_contrast_sd": statistics.stdev(values),
        "multiplicative_sd": math.exp(statistics.stdev(values)),
        "min_block_ratio": math.exp(min(values)),
        "max_block_ratio": math.exp(max(values)),
        "bootstrap_95pct_ratio": [
            percentile(bootstrap, 0.025), percentile(bootstrap, 0.975)
        ],
        "bootstrap_draws": draws,
        "interval_scope": (
            "descriptive percentile bootstrap over complete process-level blocks "
            "from this host, binary, placement, and run window"
        ),
    }


def mode_summary(records: list[dict], mode: str) -> dict:
    selected = [
        record for record in records
        if record["kind"] == "primary" and record["mode"] == mode and record["protocol_valid"]
    ]
    output = {"process_runs": len(selected)}
    for field in ("startup_ns", "warmup_ns", "steady_ns", "teardown_ns", "total_ns"):
        values = [record["result"][field] for record in selected]
        if values:
            output[f"{field}_median"] = statistics.median(values)
            output[f"{field}_min"] = min(values)
            output[f"{field}_max"] = max(values)
    if selected:
        output["steady_ns_per_logical_op_median"] = statistics.median(
            record["result"]["steady_ns"] / record["result"]["logical_ops"]
            for record in selected
        )
        output["rmw_attempts_per_logical_op_median"] = statistics.median(
            record["result"]["rmw_attempts"] / record["result"]["logical_ops"]
            for record in selected
        )
    if mode == "cas" and selected:
        retry_rates = [
            record["result"]["cas_retries"] / record["result"]["logical_ops"]
            for record in selected
        ]
        output.update({
            "cas_retry_rate_median": statistics.median(retry_rates),
            "cas_retry_rate_min": min(retry_rates),
            "cas_retry_rate_max": max(retry_rates),
            "cas_retries_total": sum(record["result"]["cas_retries"] for record in selected),
        })
    return output


def analyze(schedule: list[dict], attempts: list[dict], seed: int, draws: int) -> dict:
    by_block: dict[str, list[dict]] = {}
    for record in attempts:
        by_block.setdefault(record["block"], []).append(record)
    contrasts = {f"{numerator}_over_{denominator}": [] for numerator, denominator in PRIMARY_PAIRS}
    aa_contrasts: list[float] = []
    invalid_blocks = []
    for block in schedule:
        records = by_block.get(block["block"], [])
        if len(records) != 4 or not all(record["valid"] for record in records):
            invalid_blocks.append(block["block"])
            continue
        if block["kind"] == "primary":
            by_mode = {record["mode"]: record for record in records}
            if set(by_mode) != set(MODES):
                invalid_blocks.append(block["block"])
                continue
            for numerator, denominator in PRIMARY_PAIRS:
                numerator_value = by_mode[numerator]["result"]["steady_ns"] / by_mode[numerator]["result"]["logical_ops"]
                denominator_value = by_mode[denominator]["result"]["steady_ns"] / by_mode[denominator]["result"]["logical_ops"]
                contrasts[f"{numerator}_over_{denominator}"].append(
                    math.log(numerator_value) - math.log(denominator_value)
                )
        else:
            labels = {"A": [], "B": []}
            for record in records:
                labels[record["label"]].append(
                    math.log(record["result"]["steady_ns"] / record["result"]["logical_ops"])
                )
            if len(labels["A"]) != 2 or len(labels["B"]) != 2:
                invalid_blocks.append(block["block"])
                continue
            aa_contrasts.append(statistics.fmean(labels["A"]) - statistics.fmean(labels["B"]))
    pairs = {}
    for index, name in enumerate(sorted(contrasts)):
        pairs[name] = summarize_contrasts(contrasts[name], seed + index + 1, draws)
        pairs[name]["ratio_definition"] = (
            "numerator steady_ns per logical operation divided by shared steady_ns "
            "per logical operation within each complete Williams block"
        )
    aa = summarize_contrasts(aa_contrasts, seed + 100, draws)
    aa["ratio_definition"] = (
        "shared label A steady_ns per logical operation divided by byte-identical "
        "shared label B within each complete ABBA or BAAB block"
    )
    return {
        "invalid_blocks": invalid_blocks,
        "pairs": pairs,
        "aa_shared_A_over_shared_B": aa,
        "modes": {mode: mode_summary(attempts, mode) for mode in MODES},
    }


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve()
    output = args.out.resolve()
    runner = Path(__file__).resolve()
    expected_binary = output.parent / RECORDED_BINARY
    if (
        not binary.is_file()
        or output.exists()
        or output.name != "experiment"
        or binary != expected_binary.resolve()
    ):
        raise SystemExit(
            "binary must be receipt-root/binary/atomic_contention and output must be "
            "the absent receipt-root/experiment directory"
        )
    output.mkdir(parents=True)
    binary_before = sha256(binary)
    runner_before = sha256(runner)
    schedule = make_schedule(args.blocks, args.aa_blocks, args.seed)
    metadata = {
        "binary": RECORDED_BINARY,
        "working_directory": "receipt-root",
        "binary_sha256": binary_before,
        "runner": str(runner),
        "runner_sha256": runner_before,
        "threads": args.threads,
        "iterations_per_thread": args.iterations,
        "warmup_iterations_per_thread": args.warmup_iterations,
        "batch_size": args.batch_size,
        "coordinator_cpu": args.coordinator_cpu,
        "worker_cpus": args.worker_cpus,
        "blocks": args.blocks,
        "aa_blocks": args.aa_blocks,
        "seed": args.seed,
        "timeout_seconds": args.timeout_seconds,
        "bootstrap_draws": args.bootstrap_draws,
        "schedule": schedule,
        "analysis_unit": "one complete four-process Williams or A/A block",
        "subsamples": "workers and loop iterations inside one fresh process",
        "primary_estimands": [f"{a}_over_{b}" for a, b in PRIMARY_PAIRS],
        "timing_boundary": "steady_ns per logical operation; startup, warmup, and teardown excluded",
        "stopping_rule": "fixed schedule; no retries, replacement, peeking, or early stopping",
        "aa_scope": "mechanical label, parser, and position check; not a noise floor",
        "python": sys.version,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    attempts = []
    with (output / "attempts.jsonl").open("x") as raw:
        attempt_number = 0
        for block in schedule:
            for position, (label, mode) in enumerate(zip(block["template"], block["order"]), 1):
                attempt_number += 1
                record = run_attempt(
                    binary, binary_before, block, position, label, mode,
                    attempt_number, args,
                )
                attempts.append(record)
                append_jsonl(raw, record)

    analysis = analyze(schedule, attempts, args.seed, args.bootstrap_draws)
    binary_after = sha256(binary)
    runner_after = sha256(runner)
    protocol_invalid = [record["attempt"] for record in attempts if not record["protocol_valid"]]
    analysis_invalid = [record["attempt"] for record in attempts if not record["steady_analysis_valid"]]
    summary = {
        "attempts": len(attempts),
        "protocol_invalid_attempts": protocol_invalid,
        "analysis_ineligible_attempts": analysis_invalid,
        "all_attempts_valid": not protocol_invalid and not analysis_invalid,
        "binary_sha256_before": binary_before,
        "binary_sha256_after": binary_after,
        "runner_sha256_before": runner_before,
        "runner_sha256_after": runner_after,
        "identity_unchanged": binary_before == binary_after and runner_before == runner_after,
        **analysis,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    complete = (
        summary["all_attempts_valid"]
        and summary["identity_unchanged"]
        and not summary["invalid_blocks"]
        and all(pair.get("complete_blocks") == args.blocks for pair in summary["pairs"].values())
        and summary["aa_shared_A_over_shared_B"].get("complete_blocks") == args.aa_blocks
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
