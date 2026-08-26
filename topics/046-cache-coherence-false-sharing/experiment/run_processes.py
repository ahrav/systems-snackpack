#!/usr/bin/env python3
"""Run fixed, order-balanced process blocks for the Topic 46 probe."""

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--iterations", required=True, type=int)
    parser.add_argument("--cpu0", required=True, type=int)
    parser.add_argument("--cpu1", required=True, type=int)
    parser.add_argument("--blocks", default=8, type=int)
    parser.add_argument("--aa-blocks", default=4, type=int)
    parser.add_argument("--seed", default=20260825, type=int)
    parser.add_argument("--timeout-seconds", default=60.0, type=float)
    parser.add_argument("--bootstrap-draws", default=20_000, type=int)
    args = parser.parse_args()
    if (
        args.iterations <= 0
        or args.cpu0 < 0
        or args.cpu1 < 0
        or args.cpu0 == args.cpu1
        or args.blocks < 2
        or args.blocks % 2
        or args.aa_blocks < 2
        or args.aa_blocks % 2
        or args.timeout_seconds <= 0
        or args.bootstrap_draws <= 0
    ):
        parser.error("use distinct CPUs, positive values, and even block counts of at least two")
    return args


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def templates(count, rng):
    result = ["ABBA"] * (count // 2) + ["BAAB"] * (count // 2)
    rng.shuffle(result)
    return result


def make_schedule(blocks, aa_blocks, seed):
    rng = random.Random(seed)
    schedule = []
    for index, template in enumerate(templates(blocks, rng), 1):
        schedule.append(
            {
                "pair": "packed_over_padded",
                "block": f"primary-{index:02d}",
                "template": template,
                "A": "packed",
                "B": "padded",
                "aa": False,
            }
        )
    for index, template in enumerate(templates(aa_blocks, rng), 1):
        schedule.append(
            {
                "pair": "padded_A_over_padded_B",
                "block": f"aa-{index:02d}",
                "template": template,
                "A": "padded",
                "B": "padded",
                "aa": True,
            }
        )
    rng.shuffle(schedule)
    return schedule


def append_jsonl(handle, record):
    handle.write(json.dumps(record, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def strict_result(result, mode, args):
    expected = {
        "mode": mode,
        "iterations_per_thread": args.iterations,
        "cpu0": args.cpu0,
        "cpu1": args.cpu1,
        "first": args.iterations,
        "second": args.iterations,
        "address0_mod_128": 0,
        "slot_bytes": 128,
        "layout_ok": True,
        "affinity_ok": True,
        "correct": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        return False
    expected_delta = 8 if mode == "packed" else 128
    return (
        result.get("address_delta") == expected_delta
        and result.get("packed_size") == 128
        and result.get("padded_size") == 256
        and isinstance(result.get("elapsed_ns"), int)
        and not isinstance(result.get("elapsed_ns"), bool)
        and result["elapsed_ns"] > 0
        and result.get("start_cpu0") == args.cpu0
        and result.get("start_cpu1") == args.cpu1
        and result.get("end_cpu0") == args.cpu0
        and result.get("end_cpu1") == args.cpu1
    )


def run_attempt(binary, block, position, label, args, attempt_number):
    mode = block[label]
    command = [str(binary), mode, str(args.iterations), str(args.cpu0), str(args.cpu1)]
    record = {
        "attempt": attempt_number,
        "block": block["block"],
        "pair": block["pair"],
        "template": block["template"],
        "position": position,
        "label": label,
        "mode": mode,
        "command": command,
    }
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.timeout_seconds,
        )
        record.update(
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timed_out": False,
            }
        )
        try:
            lines = completed.stdout.splitlines()
            if len(lines) != 1:
                raise ValueError("probe must emit exactly one output record")
            result = json.loads(lines[0])
            if not isinstance(result, dict):
                raise ValueError("probe output record must be a JSON object")
            record["result"] = result
            record["valid"] = completed.returncode == 0 and strict_result(result, mode, args)
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as error:
            record["parse_error"] = repr(error)
            record["valid"] = False
    except subprocess.TimeoutExpired as error:
        record.update(
            {
                "returncode": None,
                "stdout": (error.stdout or "").decode() if isinstance(error.stdout, bytes) else error.stdout or "",
                "stderr": (error.stderr or "").decode() if isinstance(error.stderr, bytes) else error.stderr or "",
                "timed_out": True,
                "valid": False,
            }
        )
    except OSError as error:
        record.update(
            {
                "returncode": None,
                "stdout": "",
                "stderr": repr(error),
                "timed_out": False,
                "valid": False,
            }
        )
    return record


def log_contrast(records):
    if len(records) != 4 or not all(record.get("valid") for record in records):
        return None
    by_label = {"A": [], "B": []}
    for record in records:
        by_label[record["label"]].append(math.log(record["result"]["elapsed_ns"]))
    return statistics.fmean(by_label["A"]) - statistics.fmean(by_label["B"])


def percentile(values, probability):
    ordered = sorted(values)
    location = probability * (len(ordered) - 1)
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return ordered[lower]
    weight = location - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(contrasts, seed, draws):
    if len(contrasts) < 2:
        return {"complete_blocks": len(contrasts), "estimable": False}
    mean_log = statistics.fmean(contrasts)
    rng = random.Random(seed)
    bootstrap = [
        math.exp(statistics.fmean(rng.choice(contrasts) for _ in contrasts))
        for _ in range(draws)
    ]
    return {
        "complete_blocks": len(contrasts),
        "estimable": True,
        "geometric_mean_ratio": math.exp(mean_log),
        "median_block_ratio": math.exp(statistics.median(contrasts)),
        "log_contrast_sd": statistics.stdev(contrasts),
        "min_block_ratio": math.exp(min(contrasts)),
        "max_block_ratio": math.exp(max(contrasts)),
        "bootstrap_95pct_ratio": [
            percentile(bootstrap, 0.025),
            percentile(bootstrap, 0.975),
        ],
        "bootstrap_draws": draws,
        "interval_scope": (
            "descriptive percentile bootstrap over complete four-process blocks "
            "from this host, binary, CPU placement, and run window"
        ),
    }


def main():
    args = parse_args()
    binary = Path(args.binary).resolve()
    output = Path(args.out).resolve()
    runner = Path(__file__).resolve()
    if not binary.is_file() or output.exists():
        raise SystemExit("binary must exist and output path must not exist")
    output.mkdir(parents=True)

    binary_before = sha256(binary)
    runner_before = sha256(runner)
    schedule = make_schedule(args.blocks, args.aa_blocks, args.seed)
    metadata = {
        "binary": str(binary),
        "binary_sha256": binary_before,
        "runner_sha256": runner_before,
        "iterations_per_thread": args.iterations,
        "cpu0": args.cpu0,
        "cpu1": args.cpu1,
        "blocks": args.blocks,
        "aa_blocks": args.aa_blocks,
        "seed": args.seed,
        "timeout_seconds": args.timeout_seconds,
        "schedule": schedule,
        "stopping_rule": "fixed schedule; no retries, replacement, or early stopping",
        "analysis_unit": "one complete four-process ABBA or BAAB block",
        "subsamples": "threads and loop iterations within one process",
        "aa_scope": "mechanical label and position check, not a noise floor",
        "python": sys.version,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    attempts = []
    with (output / "attempts.jsonl").open("x") as raw:
        attempt_number = 0
        for block in schedule:
            for position, label in enumerate(block["template"], 1):
                attempt_number += 1
                record = run_attempt(binary, block, position, label, args, attempt_number)
                attempts.append(record)
                append_jsonl(raw, record)

    by_block = {}
    for record in attempts:
        by_block.setdefault(record["block"], []).append(record)
    contrasts = {}
    invalid_blocks = []
    for block in schedule:
        contrast = log_contrast(by_block.get(block["block"], []))
        if contrast is None:
            invalid_blocks.append(block["block"])
        else:
            contrasts.setdefault(block["pair"], []).append(contrast)

    binary_after = sha256(binary)
    runner_after = sha256(runner)
    summary = {
        "attempts": len(attempts),
        "invalid_blocks": invalid_blocks,
        "all_attempts_valid": not invalid_blocks,
        "binary_sha256_before": binary_before,
        "binary_sha256_after": binary_after,
        "runner_sha256_before": runner_before,
        "runner_sha256_after": runner_after,
        "identity_unchanged": binary_before == binary_after and runner_before == runner_after,
        "pairs": {
            pair: summarize(values, args.seed + index + 1, args.bootstrap_draws)
            for index, (pair, values) in enumerate(sorted(contrasts.items()))
        },
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if not invalid_blocks and summary["identity_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
