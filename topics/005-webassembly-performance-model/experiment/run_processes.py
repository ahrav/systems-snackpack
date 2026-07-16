#!/usr/bin/env python3
import argparse
import json
import os
import statistics
import subprocess
import sys
import time


def run_one(bench, wat, iterations, order, cpu):
    command = ["taskset", "-c", str(cpu), bench, wat, str(iterations), order]
    start = time.perf_counter_ns()
    proc = subprocess.run(command, text=True, capture_output=True)
    wall_ns = time.perf_counter_ns() - start
    if proc.returncode != 0:
        print(json.dumps({
            "event": "failure", "command": command, "returncode": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr,
        }), flush=True)
        raise SystemExit(proc.returncode)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"expected one JSON line, got {lines!r}")
    record = json.loads(lines[0])
    if record.get("schema") != 1:
        raise RuntimeError(f"unsupported child schema: {record}")
    if record.get("iterations") != iterations:
        raise RuntimeError(f"child reported different iterations: {record}")
    if record.get("callback_calls") != iterations:
        raise RuntimeError(f"child callback count mismatch: {record}")
    if record.get("order") != order:
        raise RuntimeError(
            f"child reported order {record.get('order')!r} for a {order!r} invocation: {record}"
        )
    if record.get("correct") is not True:
        raise RuntimeError(f"child correctness failure: {record}")
    # Summaries consume these directly; JSON permits booleans, floats, and
    # NaN where the harness contract promises unsigned integers, so require
    # finite non-negative ints (bool is an int subclass and is excluded).
    for field in ("guest_ns", "host_ns", "compile_ns", "instantiate_ns",
                  "cold_ready_ns", "warmup_ns"):
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RuntimeError(
                f"child field {field} is not a non-negative integer: {record}"
            )
    if record["guest_ns"] == 0:
        raise RuntimeError(f"child guest_ns is zero: {record}")
    record.update({
        "external_wall_ns": wall_ns,
        "command": command,
        "stderr": proc.stderr,
    })
    return record


def median_mad(values):
    median = statistics.median(values)
    mad = statistics.median(abs(value - median) for value in values)
    return median, mad


def exact_sign_interval_96_1(values):
    # For n=12 independent iid continuous samples, [X_(3), X_(10)] has
    # exact coverage 1 - 2*P(Binomial(12, 0.5) <= 2) = 0.96142578125.
    # The runner alternates GH/HG deterministically, so the pooled sample
    # mixes both order strata; under an order effect the stated coverage
    # holds only within the iid idealization. The summary also reports
    # per-order medians so order sensitivity stays visible.
    if len(values) != 12:
        return None
    ordered = sorted(values)
    return ordered[2], ordered[9]


def summarize(records):
    ratios = [record["host_ns"] / record["guest_ns"] for record in records]
    added_ns = [
        (record["host_ns"] - record["guest_ns"]) / record["iterations"]
        for record in records
    ]
    guest_per_iter = [record["guest_ns"] / record["iterations"] for record in records]
    host_per_iter = [record["host_ns"] / record["iterations"] for record in records]
    summary = {
        "event": "summary",
        "experimental_unit": "fresh benchmark process containing one measured pair",
        "n_processes": len(records),
        "n_pairs": len(records),
        "orders": {order: sum(r["order"] == order for r in records) for order in ("GH", "HG")},
        "all_correct": all(record["correct"] is True for record in records),
    }
    for name, values in (
        ("host_over_guest_ratio", ratios),
        ("added_host_boundary_ns_per_iteration", added_ns),
        ("guest_ns_per_iteration", guest_per_iter),
        ("host_ns_per_iteration", host_per_iter),
        ("compile_ns", [r["compile_ns"] for r in records]),
        ("instantiate_ns", [r["instantiate_ns"] for r in records]),
        ("cold_ready_ns", [r["cold_ready_ns"] for r in records]),
        ("warmup_ns", [r["warmup_ns"] for r in records]),
        ("external_wall_ns", [r["external_wall_ns"] for r in records]),
    ):
        median, mad = median_mad(values)
        summary[name] = {
            "median": median,
            "mad": mad,
            "min": min(values),
            "max": max(values),
        }
        interval = exact_sign_interval_96_1(values)
        if interval is not None:
            summary[name]["exact_96_1pct_median_interval"] = list(interval)
    for order in ("GH", "HG"):
        order_ratios = [r["host_ns"] / r["guest_ns"] for r in records if r["order"] == order]
        if not order_ratios:
            summary[f"ratio_by_order_{order}"] = {"n": 0}
            continue
        summary[f"ratio_by_order_{order}"] = {
            "n": len(order_ratios), "median": statistics.median(order_ratios),
            "min": min(order_ratios), "max": max(order_ratios),
        }
    return summary


def positive_int(text):
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from error
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {text!r}")
    return value


def non_negative_int(text):
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from error
    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a non-negative integer, got {text!r}")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True)
    parser.add_argument("--wat", required=True)
    parser.add_argument("--iterations", type=positive_int, required=True)
    parser.add_argument("--runs", type=positive_int, default=12)
    parser.add_argument("--cpu", type=non_negative_int, default=0)
    parser.add_argument("--warmup-processes", type=non_negative_int, default=2)
    args = parser.parse_args()

    manifest = {
        "event": "manifest",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runner_pid": os.getpid(),
        "bench": os.path.realpath(args.bench),
        "wat": os.path.realpath(args.wat),
        "iterations": args.iterations,
        "runs": args.runs,
        "cpu": args.cpu,
        "warmup_processes": args.warmup_processes,
    }
    print(json.dumps(manifest, sort_keys=True), flush=True)

    for index in range(args.warmup_processes):
        order = "GH" if index % 2 == 0 else "HG"
        record = run_one(args.bench, args.wat, args.iterations, order, args.cpu)
        print(json.dumps({**record, "event": "process_warmup",
                          "index": index + 1}, sort_keys=True), flush=True)

    records = []
    for index in range(args.runs):
        order = "GH" if index % 2 == 0 else "HG"
        record = run_one(args.bench, args.wat, args.iterations, order, args.cpu)
        # Spread the child record first so runner-owned labels always win;
        # a wrapper emitting its own "event" or "run" key must not be able
        # to relabel an archived measurement.
        record = {**record, "event": "measurement", "run": index + 1}
        records.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)
    print(json.dumps(summarize(records), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
