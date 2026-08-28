#!/usr/bin/env python3

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


# Two-sided 95% Student-t critical values. The interval is descriptive for the
# exact complete blocks here; it does not support architecture-wide inference.
T95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def summarize(log_contrasts):
    n = len(log_contrasts)
    mean_log = statistics.fmean(log_contrasts)
    ratio = math.exp(mean_log)
    if n > 1:
        sd_log = statistics.stdev(log_contrasts)
        critical = T95.get(n - 1)
        if critical is None:
            # 1.96 is the normal critical value; substituting it for an
            # untabulated Student-t value would narrow the reported interval.
            raise SystemExit(f"unsupported block count for the Student-t table: {n}")
        half = critical * sd_log / math.sqrt(n)
        low = math.exp(mean_log - half)
        high = math.exp(mean_log + half)
    else:
        # None serializes to JSON null; float("nan") would emit a bare NaN
        # token that strict RFC 8259 parsers such as jq reject.
        sd_log = None
        low = None
        high = None
    return {
        "blocks": n,
        "prefetch_over_demand_geomean": ratio,
        "effect_percent": (ratio - 1.0) * 100.0,
        "log_ratio_sample_sd": sd_log,
        "t95_ratio_low": low,
        "t95_ratio_high": high,
        "block_ratio_min": math.exp(min(log_contrasts)),
        "block_ratio_max": math.exp(max(log_contrasts)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()

    grouped = defaultdict(lambda: defaultdict(list))
    binary_hashes = set()
    faults = {"minor": 0, "major": 0}
    cpu_migrations = 0
    pids = set()
    nohuge_failures = 0
    phase_values = defaultdict(list)
    rows = 0
    with args.input.open(newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            rows += 1
            if int(row["returncode"]) != 0:
                raise SystemExit(f"nonzero attempt retained: {row}")
            result = json.loads(row["result_json"])
            if not result["correct"] or result["checksum"] != result["expected"]:
                raise SystemExit(f"incorrect attempt retained: {row}")
            binary_hashes.add(row["binary_sha256"])
            pids.add(result["pid"])
            faults["minor"] += result["timed_minor_faults"]
            faults["major"] += result["timed_major_faults"]
            cpu_migrations += int(result["cpu_start"] != result["cpu_end"])
            nohuge_failures += int(result["madv_nohuge_data_rc"] != 0)
            nohuge_failures += int(result["madv_nohuge_order_rc"] != 0)
            phase_values["init_seconds"].append(result["init_seconds"])
            phase_values["warmup_seconds"].append(result["warmup_seconds"])
            phase_values["timed_seconds"].append(result["elapsed_seconds"])
            key = (row["case"], int(row["distance"]), int(row["block"]))
            grouped[key][row["label"]].append(result["ns_per_access"])

    if len(binary_hashes) != 1:
        raise SystemExit(f"expected one binary hash, found {sorted(binary_hashes)}")

    contrasts = defaultdict(list)
    block_details = []
    for (case, distance, block), labels in sorted(grouped.items()):
        if len(labels["A"]) != 2 or len(labels["B"]) != 2:
            raise SystemExit(
                f"incomplete block: case={case} distance={distance} block={block}"
            )
        mean_log_a = statistics.fmean(math.log(value) for value in labels["A"])
        mean_log_b = statistics.fmean(math.log(value) for value in labels["B"])
        contrast = mean_log_b - mean_log_a
        contrasts[(case, distance)].append(contrast)
        block_details.append(
            {
                "case": case,
                "distance": distance,
                "block": block,
                "a_ns_per_access_geomean": math.exp(mean_log_a),
                "b_ns_per_access_geomean": math.exp(mean_log_b),
                "b_over_a": math.exp(contrast),
            }
        )

    summaries = []
    for (case, distance), values in sorted(contrasts.items()):
        summary = {"case": case, "distance": distance}
        summary.update(summarize(values))
        summaries.append(summary)

    phase_summary = {}
    for phase, values in sorted(phase_values.items()):
        phase_summary[phase] = {
            "min": min(values),
            "median": statistics.median(values),
            "max": max(values),
        }

    print(
        json.dumps(
            {
                "schema": 1,
                "input": args.input.name,
                "rows": rows,
                "unique_pids": len(pids),
                "binary_sha256": next(iter(binary_hashes)),
                "timed_fault_totals": faults,
                "cpu_migrations": cpu_migrations,
                "madv_nohuge_failures": nohuge_failures,
                "phase_summary": phase_summary,
                "summary": summaries,
                "blocks": block_details,
                "interval_note": (
                    "Two-sided 95% Student-t interval over complete-block log ratios; "
                    "descriptive for this host, binary, workload, and run window only."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
