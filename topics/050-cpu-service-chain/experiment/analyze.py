#!/usr/bin/env python3
"""Analyze complete process-level blocks without treating inner work as samples."""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


# Two-sided 95% Student-t critical values, fixed before observing the run.
T975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.364624251,
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


INTEGER_FIELDS = {
    "block",
    "period",
    "pid",
    "started_realtime_ns",
    "holder_cpu_requested",
    "waiter_cpu_requested",
    "hog_cpu_requested",
    "holder_nice_requested",
    "holder_nice_set_rc",
    "holder_nice_set_errno",
    "holder_nice_observed",
    "waiter_nice_observed",
    "hog_nice_observed",
    "holder_sched_get_rc",
    "holder_sched_policy",
    "holder_sched_priority",
    "waiter_sched_get_rc",
    "waiter_sched_policy",
    "waiter_sched_priority",
    "hog_sched_get_rc",
    "hog_sched_policy",
    "hog_sched_priority",
    "holder_pin_rc",
    "waiter_pin_rc",
    "hog_pin_rc",
    "holder_affinity_exact",
    "waiter_affinity_exact",
    "hog_affinity_exact",
    "holder_wall_ns",
    "holder_cpu_ns",
    "holder_start_cpu",
    "holder_end_cpu",
    "waiter_wait_ns",
    "waiter_start_cpu",
    "waiter_end_cpu",
    "hog_wall_ns",
    "hog_cpu_ns",
    "hog_start_cpu",
    "hog_end_cpu",
    "holder_voluntary_context_switches",
    "holder_involuntary_context_switches",
    "waiter_voluntary_context_switches",
    "waiter_involuntary_context_switches",
    "hog_voluntary_context_switches",
    "hog_involuntary_context_switches",
}


def load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, object] = dict(raw)
            for field in INTEGER_FIELDS:
                row[field] = int(raw[field])
            rows.append(row)
    return rows


def describe(values: list[int], scale: float = 1.0) -> dict[str, float | int]:
    scaled = [value / scale for value in values]
    return {
        "n_processes": len(scaled),
        "median": statistics.median(scaled),
        "min": min(scaled),
        "max": max(scaled),
    }


def label_summaries(rows: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["experiment"]), str(row["label"]))].append(row)
    output: dict[str, object] = {}
    for (experiment, label), group in sorted(grouped.items()):
        output[f"{experiment}:{label}"] = {
            "holder_wall_ms": describe([int(row["holder_wall_ns"]) for row in group], 1e6),
            "holder_cpu_ms": describe([int(row["holder_cpu_ns"]) for row in group], 1e6),
            "waiter_wait_ms": describe([int(row["waiter_wait_ns"]) for row in group], 1e6),
            "holder_involuntary_context_switches": describe(
                [int(row["holder_involuntary_context_switches"]) for row in group]
            ),
        }
    return output


def block_interval(
    rows: list[dict[str, object]], experiment: str, numerator: str, denominator: str, metric: str
) -> dict[str, object]:
    selected = [row for row in rows if row["experiment"] == experiment]
    blocks: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in selected:
        blocks[int(row["block"])].append(row)
    contrasts = []
    block_rows = []
    for block in sorted(blocks):
        group = blocks[block]
        num = [int(row[metric]) for row in group if row["label"] == numerator]
        den = [int(row[metric]) for row in group if row["label"] == denominator]
        if len(group) != 4 or len(num) != 2 or len(den) != 2:
            raise RuntimeError(f"incomplete block {experiment}:{block}")
        if min(num + den) <= 0:
            raise RuntimeError(f"non-positive metric in block {experiment}:{block}")
        contrast = statistics.fmean(math.log(value) for value in num) - statistics.fmean(
            math.log(value) for value in den
        )
        contrasts.append(contrast)
        block_rows.append({"block": block, "log_contrast": contrast, "ratio": math.exp(contrast)})
    n = len(contrasts)
    if n < 2 or n - 1 not in T975:
        raise RuntimeError("unsupported number of complete blocks")
    mean = statistics.fmean(contrasts)
    sd = statistics.stdev(contrasts)
    half_width = T975[n - 1] * sd / math.sqrt(n)
    return {
        "metric": metric,
        "ratio": f"{numerator}/{denominator}",
        "complete_blocks": n,
        "point_estimate_geometric_ratio": math.exp(mean),
        "two_sided_95pct_t_interval": [math.exp(mean - half_width), math.exp(mean + half_width)],
        "sample_sd_log_contrast": sd,
        "block_contrasts": block_rows,
        "boundary": "interval covers dispersion across complete four-period blocks on this host/window; it does not cover host, kernel, build, or workload populations",
    }


def validate(rows: list[dict[str, object]], metadata: dict[str, object], failures_path: Path) -> dict[str, object]:
    selected = metadata["selected"]
    errors = []
    for index, row in enumerate(rows, start=2):
        for role in ("holder", "waiter", "hog"):
            if int(row[f"{role}_pin_rc"]) != 0 or int(row[f"{role}_affinity_exact"]) != 1:
                errors.append(f"row {index}: {role} affinity failure")
        if int(row["holder_nice_set_rc"]) != 0 or int(row["holder_nice_observed"]) != 19:
            errors.append(f"row {index}: holder nice failure")
        if int(row["waiter_nice_observed"]) != 0 or int(row["hog_nice_observed"]) != 0:
            errors.append(f"row {index}: waiter or hog did not run at nice 0")
        for role in ("holder", "waiter", "hog"):
            if (
                int(row[f"{role}_sched_get_rc"]) != 0
                or int(row[f"{role}_sched_policy"]) != 0
                or int(row[f"{role}_sched_priority"]) != 0
            ):
                errors.append(f"row {index}: {role} did not run under SCHED_OTHER priority 0")
        if not 4_900_000 <= int(row["holder_cpu_ns"]) <= 6_000_000:
            errors.append(f"row {index}: holder CPU-time control escaped 4.9-6.0 ms")
        if int(row["holder_start_cpu"]) != int(selected["holder"]) or int(row["holder_end_cpu"]) != int(
            selected["holder"]
        ):
            errors.append(f"row {index}: holder ran on unexpected CPU")
        if int(row["waiter_start_cpu"]) != int(selected["waiter"]) or int(row["waiter_end_cpu"]) != int(
            selected["waiter"]
        ):
            errors.append(f"row {index}: waiter ran on unexpected CPU")
        expected_hog = int(selected["holder"]) if row["experiment"] == "treatment" and row["label"] == "A" else int(
            selected["control"]
        )
        if int(row["hog_cpu_requested"]) != expected_hog:
            errors.append(f"row {index}: wrong hog assignment")
        if int(row["hog_start_cpu"]) != expected_hog or int(row["hog_end_cpu"]) != expected_hog:
            errors.append(f"row {index}: hog ran on unexpected CPU")
    failure_text = failures_path.read_text(encoding="utf-8") if failures_path.exists() else ""
    expected_rows = 2 * 8 * 4
    pids = [int(row["pid"]) for row in rows]
    return {
        "pass": not errors and not failure_text.strip() and len(rows) == expected_rows and len(set(pids)) == expected_rows,
        "row_count": len(rows),
        "expected_row_count": expected_rows,
        "unique_pid_count": len(set(pids)),
        "failed_attempt_file_empty": not failure_text.strip(),
        "errors": errors,
        "aa_mechanical_identity": {
            "binary_sha256": metadata["binary_sha256"],
            "X_and_Y_both_use": "separate_core with identical CPU, nice, duration, binary, and schedule paths; only label differs",
        },
    }


def main() -> int:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "run")
    rows = load_rows(run_dir / "raw.csv")
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    result = {
        "schema": "topic50-analysis.v1",
        "validation": validate(rows, metadata, run_dir / "failures.jsonl"),
        "process_descriptives": label_summaries(rows),
        "treatment_holder_wall": block_interval(rows, "treatment", "A", "B", "holder_wall_ns"),
        "treatment_waiter_wait": block_interval(rows, "treatment", "A", "B", "waiter_wait_ns"),
        "aa_holder_wall": block_interval(rows, "aa", "X", "Y", "holder_wall_ns"),
        "aa_waiter_wait": block_interval(rows, "aa", "X", "Y", "waiter_wait_ns"),
        "interpretation_fence": {
            "measured": "wall time, per-thread CPU time, requested/observed affinity, nice result, and getrusage context-switch counts for each fresh PID",
            "observed_codegen": "the summary does not infer mechanisms from code generation; the sealed receipt records linked disassembly from the exact campaign binary separately",
            "inferred": "a large A/B wall-time ratio with nearly unchanged holder CPU time is consistent with descheduling of the low-priority lock holder; context-switch counts support but do not uniquely identify that mechanism",
            "aa": "one fixed eight-block A/A is a harness-asymmetry diagnostic, not null calibration or a universal noise floor",
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["validation"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
