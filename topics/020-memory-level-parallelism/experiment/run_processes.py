#!/usr/bin/env python3
"""Run and summarize fixed fresh-process Topic 20 comparisons."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import statistics
import subprocess
import time
from pathlib import Path
from typing import NoReturn

AB_PAIRS = 8
AA_PAIRS = 4
WORKLOAD_SEED = 0xD1B5_4A32_D192_ED03
SCHEDULE_SEED = 20_200_730
TOKEN = re.compile(r"^([a-z_]+)=([0-9.]+)$")
INTEGER_FIELDS = {
    "lanes",
    "nodes",
    "bytes",
    "loads",
    "seed",
    "setup_ns",
    "warm_ns",
    "steady_ns",
    "sink",
}
FLOAT_FIELDS = {"ns_per_load"}
PAYLOAD_FIELDS = INTEGER_FIELDS | FLOAT_FIELDS


def fail(message: str) -> NoReturn:
    """Exit without a traceback when retained evidence violates its contract."""

    raise SystemExit(message)


def sha256(path: Path) -> str:
    """Return one file's lowercase SHA-256 digest."""

    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_payload(
    payload: str,
    expected_lanes: int,
    expected_nodes: int,
    expected_loads: int,
) -> dict[str, int | float]:
    """Parse one exact probe line and enforce its output schema."""

    if not payload or "\n" in payload:
        fail("probe must emit exactly one non-empty line")
    parsed: dict[str, int | float] = {}
    for raw in payload.split():
        match = TOKEN.fullmatch(raw)
        if match is None:
            fail(f"malformed probe token: {raw}")
        key, value = match.groups()
        if key not in PAYLOAD_FIELDS:
            fail(f"unexpected probe field: {key}")
        if key in parsed:
            fail(f"duplicate probe field: {key}")
        parsed[key] = int(value) if key in INTEGER_FIELDS else float(value)
    if set(parsed) != PAYLOAD_FIELDS:
        fail(f"probe fields differ: {sorted(set(parsed) ^ PAYLOAD_FIELDS)}")
    if parsed["lanes"] != expected_lanes:
        fail(f"requested {expected_lanes} lanes, probe reported {parsed['lanes']}")
    if parsed["nodes"] != expected_nodes:
        fail(f"requested {expected_nodes} nodes, probe reported {parsed['nodes']}")
    if parsed["loads"] != expected_loads:
        fail(f"requested {expected_loads} loads, probe reported {parsed['loads']}")
    if parsed["bytes"] != expected_nodes * 64:
        fail("probe bytes disagree with nodes * 64")
    if parsed["seed"] != WORKLOAD_SEED:
        fail(f"probe reported unexpected seed: {parsed['seed']}")
    if parsed["steady_ns"] <= 0 or parsed["loads"] <= 0:
        fail("steady time and useful loads must be positive")
    expected = parsed["steady_ns"] / parsed["loads"]
    if not math.isclose(parsed["ns_per_load"], expected, rel_tol=1e-8):
        fail("ns_per_load disagrees with steady_ns / loads")
    return parsed


def invoke(
    binary: Path,
    cpu: int,
    lanes: int,
    nodes: int,
    loads: int,
    identity: dict[str, int | str],
    attempt_writer: csv.DictWriter,
    attempt_stream,
) -> dict[str, int | float | str]:
    """Run one fresh pinned process and retain its whole-process boundary."""

    command = [
        "taskset",
        "-c",
        str(cpu),
        str(binary),
        "--lanes",
        str(lanes),
        "--nodes",
        str(nodes),
        "--loads",
        str(loads),
        "--seed",
        str(WORKLOAD_SEED),
    ]
    started = time.monotonic_ns()
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    process_ns = time.monotonic_ns() - started
    parse_status = "ok"
    parse_error = ""
    parsed: dict[str, int | float] | None = None
    try:
        if completed.returncode != 0:
            fail(f"probe exited {completed.returncode}")
        if completed.stderr:
            fail("probe wrote to stderr")
        parsed = parse_payload(completed.stdout.strip(), lanes, nodes, loads)
    except SystemExit as error:
        parse_status = "error"
        parse_error = str(error)
    attempt_writer.writerow(
        {
            **identity,
            "lanes": lanes,
            "command": json.dumps(command, separators=(",", ":")),
            "returncode": completed.returncode,
            "process_ns": process_ns,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "parse_status": parse_status,
            "parse_error": parse_error,
        }
    )
    attempt_stream.flush()
    if parsed is None:
        fail(
            f"{parse_error}; stderr={completed.stderr.strip() or '<empty>'}; "
            "failed attempt retained in attempts.csv"
        )
    if process_ns <= parsed["steady_ns"]:
        fail("whole-process time must exceed steady time")
    return {
        **parsed,
        "process_ns": process_ns,
        "outside_ns": process_ns - int(parsed["steady_ns"]),
        "stdout": completed.stdout.strip(),
    }


def quantile(values: list[float], probability: float) -> float:
    """Return a type-7 sample quantile."""

    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def ratio_summary(ratios: list[float], critical: float) -> dict[str, float | int]:
    """Summarize paired ratios with a fixed Student-t interval in log space."""

    if len(ratios) < 2 or any(value <= 0 for value in ratios):
        fail("paired ratios must contain at least two positive values")
    logs = [math.log(value) for value in ratios]
    mean = statistics.fmean(logs)
    half_width = critical * statistics.stdev(logs) / math.sqrt(len(logs))
    return {
        "n_pairs": len(ratios),
        "geometric_mean": math.exp(mean),
        "log_t_95_low": math.exp(mean - half_width),
        "log_t_95_high": math.exp(mean + half_width),
        "median": quantile(ratios, 0.5),
        "q1": quantile(ratios, 0.25),
        "q3": quantile(ratios, 0.75),
        "log_sd": statistics.stdev(logs),
    }


def treatment_median(
    rows: list[dict[str, int | float | str]], family: str, label: str
) -> float:
    """Return the median steady nanoseconds per load for one treatment."""

    values = [
        float(row["ns_per_load"])
        for row in rows
        if row["family"] == family and row["label"] == label
    ]
    return statistics.median(values)


def arguments() -> argparse.Namespace:
    """Parse the fixed-design runner arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--nodes", type=int, default=1 << 22)
    parser.add_argument("--loads", type=int, default=1 << 25)
    return parser.parse_args()


def main() -> None:
    """Execute the predeclared A/B and A/A schedules."""

    args = arguments()
    if not args.binary.is_file():
        fail(f"binary is unavailable: {args.binary}")
    if args.nodes < 16 or args.nodes > 0xFFFF_FFFF:
        fail("nodes must fit the Cycle contract")
    if args.loads <= 0 or args.loads % 8:
        fail("loads must be positive and divisible by eight")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        fail("output directory must be absent or empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, int | float | str]] = []
    sequence = 0
    schedule_rng = random.Random(SCHEDULE_SEED)
    ab_orders = ["AB"] * (AB_PAIRS // 2) + ["BA"] * (AB_PAIRS // 2)
    aa_orders = ["A0A1"] * (AA_PAIRS // 2) + ["A1A0"] * (AA_PAIRS // 2)
    schedule_rng.shuffle(ab_orders)
    schedule_rng.shuffle(aa_orders)

    attempt_fields = [
        "family",
        "pair",
        "order",
        "position",
        "sequence",
        "label",
        "lanes",
        "command",
        "returncode",
        "process_ns",
        "stdout",
        "stderr",
        "parse_status",
        "parse_error",
    ]
    attempts_path = args.output_dir / "attempts.csv"
    with attempts_path.open("w", newline="", encoding="utf-8") as attempt_stream:
        attempt_writer = csv.DictWriter(attempt_stream, fieldnames=attempt_fields)
        attempt_writer.writeheader()
        attempt_stream.flush()

        for pair, order in enumerate(ab_orders, start=1):
            schedule = [("A", 1), ("B", 8)]
            if order == "BA":
                schedule.reverse()
            for position, (label, lanes) in enumerate(schedule, start=1):
                identity: dict[str, int | str] = {
                    "family": "ab",
                    "pair": pair,
                    "order": order,
                    "position": position,
                    "sequence": sequence,
                    "label": label,
                }
                observation = invoke(
                    args.binary.resolve(),
                    args.cpu,
                    lanes,
                    args.nodes,
                    args.loads,
                    identity,
                    attempt_writer,
                    attempt_stream,
                )
                rows.append({**identity, **observation})
                sequence += 1

        for pair, order in enumerate(aa_orders, start=1):
            schedule = ["A0", "A1"]
            if order == "A1A0":
                schedule.reverse()
            for position, label in enumerate(schedule, start=1):
                identity = {
                    "family": "aa",
                    "pair": pair,
                    "order": order,
                    "position": position,
                    "sequence": sequence,
                    "label": label,
                }
                observation = invoke(
                    args.binary.resolve(),
                    args.cpu,
                    1,
                    args.nodes,
                    args.loads,
                    identity,
                    attempt_writer,
                    attempt_stream,
                )
                rows.append({**identity, **observation})
                sequence += 1

    raw_path = args.output_dir / "raw.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def paired(family: str, numerator: str, denominator: str, field: str) -> list[float]:
        pairs = AB_PAIRS if family == "ab" else AA_PAIRS
        ratios = []
        for pair in range(1, pairs + 1):
            block = {
                str(row["label"]): row
                for row in rows
                if row["family"] == family and row["pair"] == pair
            }
            ratios.append(float(block[numerator][field]) / float(block[denominator][field]))
        return ratios

    summary = {
        "binary_sha256": sha256(args.binary),
        "nodes": args.nodes,
        "working_set_bytes": args.nodes * 64,
        "loads_per_process": args.loads,
        "ab_processes": AB_PAIRS * 2,
        "aa_processes": AA_PAIRS * 2,
        "analysis_unit": "one complete fresh-process pair",
        "assignment": "seed-recorded restricted randomization with equal order templates",
        "schedule_seed": SCHEDULE_SEED,
        "ab_orders": ab_orders,
        "aa_orders": aa_orders,
        "stopping": "fixed eight A/B pairs and four A/A pairs",
        "estimand": "one-chain time divided by eight-chain time",
        "steady": ratio_summary(paired("ab", "A", "B", "steady_ns"), 2.364624251),
        "whole_process": ratio_summary(
            paired("ab", "A", "B", "process_ns"), 2.364624251
        ),
        "outside_steady": ratio_summary(
            paired("ab", "A", "B", "outside_ns"), 2.364624251
        ),
        "one_chain_median_ns_per_load": treatment_median(rows, "ab", "A"),
        "eight_chain_median_ns_per_load": treatment_median(rows, "ab", "B"),
        "aa_steady": ratio_summary(paired("aa", "A0", "A1", "steady_ns"), 3.182446305),
        "interval_scope": (
            "two-sided 95% Student-t interval over paired log contrasts; "
            "covers process and time-window variation in this run"
        ),
        "aa_scope": (
            "mechanical path-asymmetry diagnostic; four pairs do not establish "
            "long-run null calibration"
        ),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
