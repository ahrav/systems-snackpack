#!/usr/bin/env python3
"""Run and validate the Topic 19 timing, layout, and PMU experiment."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import subprocess
from typing import Any

T_975_DF11 = 2.200985
TIMING_BLOCKS = 12
PERF_BLOCKS = 4
WARM_ROUNDS = 512
MEASURE_ROUNDS = 8192
EXPECTED_LEAVES = 512


def checked_run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def parse_program_output(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"expected one output line, received {len(lines)}")
    fields = dict(item.split("=", 1) for item in lines[0].split())
    required = {
        "variant",
        "align",
        "nfun",
        "pid",
        "warm_rounds",
        "measure_rounds",
        "calls",
        "elapsed_ns",
        "ns_per_call",
        "checksum",
        "expected",
        "ok",
    }
    if set(fields) != required:
        raise RuntimeError(f"unexpected output fields: {sorted(fields)}")
    if fields["ok"] != "1" or fields["checksum"] != fields["expected"]:
        raise RuntimeError(f"correctness failure: {output.strip()}")
    if int(fields["nfun"]) != EXPECTED_LEAVES:
        raise RuntimeError(f"unexpected leaf count: {fields['nfun']}")
    if int(fields["elapsed_ns"]) <= 0 or float(fields["ns_per_call"]) <= 0.0:
        raise RuntimeError(f"non-positive timing: {output.strip()}")
    return fields


def arm_order(block: int) -> str:
    return "ABBA" if block % 2 == 1 else "BAAB"


def run_timing(
    name: str,
    arms: dict[str, Path],
    output_dir: Path,
    cpu: int,
) -> list[dict[str, str]]:
    process_dir = output_dir / "processes"
    process_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for block in range(1, TIMING_BLOCKS + 1):
        order = arm_order(block)
        for position, arm in enumerate(order, start=1):
            command = [
                "taskset",
                "-c",
                str(cpu),
                str(arms[arm]),
                str(WARM_ROUNDS),
                str(MEASURE_ROUNDS),
            ]
            completed = subprocess.run(command, text=True, capture_output=True)
            stem = f"{name}-block-{block:02d}-position-{position}-{arm}"
            (process_dir / f"{stem}.stdout").write_text(
                completed.stdout, encoding="utf-8"
            )
            (process_dir / f"{stem}.stderr").write_text(
                completed.stderr, encoding="utf-8"
            )
            (process_dir / f"{stem}.status").write_text(
                f"returncode={completed.returncode}\n"
                f"command={json.dumps(command)}\n",
                encoding="utf-8",
            )
            if completed.returncode != 0:
                raise RuntimeError(f"{stem} exited {completed.returncode}")
            fields = parse_program_output(completed.stdout)
            row = {
                "experiment": name,
                "block": str(block),
                "position": str(position),
                "order": order,
                "arm": arm,
                "executable": arms[arm].name,
                **fields,
            }
            rows.append(row)
    return rows


def analyze_timing(
    rows: list[dict[str, str]], name: str, ratio_name: str
) -> dict[str, Any]:
    if len(rows) != TIMING_BLOCKS * 4:
        raise RuntimeError(f"{name}: expected 48 rows, received {len(rows)}")
    per_arm: dict[str, list[float]] = {"A": [], "B": []}
    contrasts: list[float] = []
    blocks: list[dict[str, Any]] = []

    for block in range(1, TIMING_BLOCKS + 1):
        block_rows = [row for row in rows if int(row["block"]) == block]
        block_rows.sort(key=lambda row: int(row["position"]))
        observed_order = "".join(row["arm"] for row in block_rows)
        if observed_order != arm_order(block):
            raise RuntimeError(
                f"{name}: block {block} order {observed_order}, "
                f"expected {arm_order(block)}"
            )
        values: dict[str, list[float]] = {"A": [], "B": []}
        for row in block_rows:
            value = float(row["ns_per_call"])
            values[row["arm"]].append(value)
            per_arm[row["arm"]].append(value)
        if len(values["A"]) != 2 or len(values["B"]) != 2:
            raise RuntimeError(f"{name}: block {block} is incomplete")
        log_a = statistics.fmean(math.log(value) for value in values["A"])
        log_b = statistics.fmean(math.log(value) for value in values["B"])
        contrast = log_b - log_a
        contrasts.append(contrast)
        blocks.append(
            {
                "block": block,
                "order": observed_order,
                "a_geomean_ns_per_call": math.exp(log_a),
                "b_geomean_ns_per_call": math.exp(log_b),
                "b_over_a_ratio": math.exp(contrast),
            }
        )

    mean_log = statistics.fmean(contrasts)
    sd_log = statistics.stdev(contrasts)
    half = T_975_DF11 * sd_log / math.sqrt(len(contrasts))
    ratios = [math.exp(value) for value in contrasts]
    q1, _, q3 = statistics.quantiles(ratios, n=4, method="inclusive")
    return {
        "name": name,
        "ratio_name": ratio_name,
        "analysis_units": len(contrasts),
        "process_invocations": len(rows),
        "a_median_ns_per_call": statistics.median(per_arm["A"]),
        "b_median_ns_per_call": statistics.median(per_arm["B"]),
        "geomean_ratio": math.exp(mean_log),
        "log_t95_interval": [
            math.exp(mean_log - half),
            math.exp(mean_log + half),
        ],
        "sd_log_contrast": sd_log,
        "block_ratio_median": statistics.median(ratios),
        "block_ratio_iqr": [q1, q3],
        "blocks": blocks,
    }


def write_timing_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_symbols(executable: Path) -> dict[str, tuple[int, int]]:
    completed = checked_run(["nm", "-nS", "--defined-only", str(executable)])
    symbols: dict[str, tuple[int, int]] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        address, size, _kind, name = parts
        try:
            symbols[name] = (int(address, 16), int(size, 16))
        except ValueError:
            continue
    return symbols


def validate_layout(dense: Path, sparse: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    all_sizes: dict[str, list[int]] = {}
    for name, executable, expected_spacing in (
        ("dense16", dense, 16),
        ("sparse4096", sparse, 4096),
    ):
        symbols = parse_symbols(executable)
        leaves = []
        for index in range(EXPECTED_LEAVES):
            symbol = f"leaf_{index}"
            if symbol not in symbols:
                raise RuntimeError(f"{name}: missing {symbol}")
            leaves.append(symbols[symbol])
        if "run_rounds" not in symbols:
            raise RuntimeError(f"{name}: missing run_rounds")
        addresses = [address for address, _size in leaves]
        sizes = [size for _address, size in leaves]
        spacing = [
            addresses[index + 1] - addresses[index]
            for index in range(len(addresses) - 1)
        ]
        if any(delta != expected_spacing for delta in spacing):
            raise RuntimeError(f"{name}: leaf spacing is not {expected_spacing}")
        if len(set(sizes)) != 1:
            raise RuntimeError(f"{name}: leaf symbol sizes differ")
        all_sizes[name] = sizes
        result[name] = {
            "leaf_count": len(leaves),
            "leaf_symbol_size": sizes[0],
            "spacing_bytes": expected_spacing,
            "leaf_0_address": addresses[0],
            "leaf_511_address": addresses[-1],
            "run_rounds_address": symbols["run_rounds"][0],
            "run_rounds_size": symbols["run_rounds"][1],
        }
    if all_sizes["dense16"] != all_sizes["sparse4096"]:
        raise RuntimeError("leaf symbol sizes differ across variants")
    # Scoped to leaf symbols: the guard above only compares leaf sizes. The
    # alignment treatment can move non-leaf code generation, so report the
    # caller separately instead of implying every code symbol stayed equal.
    result["leaf_code_size_equal"] = True
    result["run_rounds_size_equal"] = (
        result["dense16"]["run_rounds_size"]
        == result["sparse4096"]["run_rounds_size"]
    )
    return result


def perf_passes(architecture: str, perf_list: str) -> list[tuple[str, str]]:
    if architecture == "aarch64":
        return [
            ("anchor", "{cpu_cycles:u,inst_retired:u}"),
            ("l1i", "{l1i_cache:u,l1i_cache_refill:u}"),
            ("itlb", "{itlb_walk:u,inst_retired:u}"),
        ]
    passes = [
        ("anchor", "{cycles:u,instructions:u}"),
        ("generic_l1i", "{L1-icache-loads:u,L1-icache-load-misses:u}"),
        ("generic_itlb", "{iTLB-loads:u,iTLB-load-misses:u}"),
    ]
    if all(
        event in perf_list
        for event in (
            "idq.dsb_uops",
            "idq.mite_uops",
            "dsb2mite_switches.penalty_cycles",
        )
    ):
        passes.append(
            (
                "intel_delivery",
                "{idq.dsb_uops:u,idq.mite_uops:u,"
                "dsb2mite_switches.penalty_cycles:u}",
            )
        )
    if all(
        event in perf_list
        for event in ("frontend_retired.l1i_miss", "frontend_retired.itlb_miss")
    ):
        passes.append(
            (
                "intel_retired_misses",
                "{frontend_retired.l1i_miss:u,"
                "frontend_retired.itlb_miss:u}",
            )
        )
    return passes


def parse_perf_csv(path: Path) -> list[dict[str, Any]]:
    # perf stat -x field order (no -I/-a/-A/-r, so no leading fields):
    #   0 counter value, 1 unit, 2 event name,
    #   3 run time of counter, 4 percent of measurement time counter was running.
    # Field 3 is running time, not enabled time; enabled = field 3 / (field 4 / 100).
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.reader(handle, delimiter=";"):
            if not raw or not raw[0] or raw[0].startswith("#") or len(raw) < 5:
                continue
            count_text = raw[0].strip()
            try:
                count = float(count_text)
            except ValueError:
                count = None
            try:
                percent_running = float(raw[4]) if raw[4].strip() else None
            except ValueError:
                percent_running = None
            rows.append(
                {
                    "event": raw[2].strip(),
                    "count_text": count_text,
                    "count": count,
                    "time_running_ns": raw[3].strip(),
                    "percent_running": percent_running,
                }
            )
    return rows


def run_perf(
    dense: Path,
    sparse: Path,
    output_dir: Path,
    cpu: int,
    architecture: str,
    perf_list: str,
) -> dict[str, Any]:
    perf_dir = output_dir / "perf"
    perf_dir.mkdir(parents=True, exist_ok=True)
    passes = perf_passes(architecture, perf_list)
    attempts: list[dict[str, Any]] = []
    binaries = {"A": dense, "B": sparse}
    for pass_name, events in passes:
        for block in range(1, PERF_BLOCKS + 1):
            order = arm_order(block)
            for position, arm in enumerate(order, start=1):
                stem = (
                    f"{pass_name}-block-{block:02d}-"
                    f"position-{position}-{arm}"
                )
                csv_path = perf_dir / f"{stem}.csv"
                command = [
                    "perf",
                    "stat",
                    "-x",
                    ";",
                    "--no-big-num",
                    "-o",
                    str(csv_path),
                    "-e",
                    events,
                    "--",
                    "taskset",
                    "-c",
                    str(cpu),
                    str(binaries[arm]),
                    str(WARM_ROUNDS),
                    str(MEASURE_ROUNDS),
                ]
                completed = subprocess.run(command, text=True, capture_output=True)
                (perf_dir / f"{stem}.stdout").write_text(
                    completed.stdout, encoding="utf-8"
                )
                (perf_dir / f"{stem}.stderr").write_text(
                    completed.stderr, encoding="utf-8"
                )
                parsed = parse_perf_csv(csv_path) if csv_path.exists() else []
                attempt = {
                    "pass": pass_name,
                    "events": events,
                    "block": block,
                    "position": position,
                    "order": order,
                    "arm": arm,
                    "returncode": completed.returncode,
                    "rows": parsed,
                }
                attempts.append(attempt)
                (perf_dir / f"{stem}.status.json").write_text(
                    json.dumps(attempt, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                if completed.returncode == 0:
                    parse_program_output(completed.stdout)

    anchor_attempts = [item for item in attempts if item["pass"] == "anchor"]
    if len(anchor_attempts) != PERF_BLOCKS * 4:
        raise RuntimeError("anchor PMU matrix is incomplete")
    for attempt in anchor_attempts:
        if attempt["returncode"] != 0 or len(attempt["rows"]) != 2:
            raise RuntimeError("anchor PMU pass failed")
        for row in attempt["rows"]:
            if row["count"] is None or row["percent_running"] is None:
                raise RuntimeError("anchor PMU row is not numeric")
            if row["percent_running"] < 99.0:
                raise RuntimeError("anchor PMU group ran for less than 99 percent")

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    failed_attempts = 0
    for attempt in attempts:
        # perf stat exits with the workload's status, so a non-zero attempt can
        # still have written valid counter rows. Those rows describe a run that
        # did not complete as intended, so they must not enter the quantitative
        # summaries; the raw attempt records below retain them either way.
        if attempt["returncode"] != 0:
            failed_attempts += 1
            continue
        for row in attempt["rows"]:
            key = (attempt["pass"], attempt["arm"], row["event"])
            groups.setdefault(key, []).append(row)
    summaries = []
    for (pass_name, arm, event), rows in sorted(groups.items()):
        counts = [row["count"] for row in rows if row["count"] is not None]
        fractions = [
            row["percent_running"]
            for row in rows
            if row["percent_running"] is not None
        ]
        summaries.append(
            {
                "pass": pass_name,
                "arm": arm,
                "event": event,
                "attempts": len(rows),
                "numeric_attempts": len(counts),
                "median_count": statistics.median(counts) if counts else None,
                "count_range": [min(counts), max(counts)] if counts else None,
                "percent_running_range": (
                    [min(fractions), max(fractions)] if fractions else None
                ),
                "all_numeric_counts_zero": bool(counts)
                and all(count == 0.0 for count in counts),
            }
        )
    result = {
        "protocol": {
            "blocks_per_pass": PERF_BLOCKS,
            "processes_per_pass": PERF_BLOCKS * 4,
            "order": "odd ABBA; even BAAB",
            "scope": "whole process including startup and warm-up",
            "summaries_exclude_failed_attempts": True,
            "failed_attempts": failed_attempts,
        },
        "passes": [{"name": name, "events": events} for name, events in passes],
        "attempts": attempts,
        "event_summaries": summaries,
    }
    (output_dir / "perf-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def format_timing(summary: dict[str, Any]) -> str:
    low, high = summary["log_t95_interval"]
    return (
        f"{summary['name']}: {summary['ratio_name']}="
        f"{summary['geomean_ratio']:.9f} "
        f"95%=[{low:.9f},{high:.9f}] "
        f"blocks={summary['analysis_units']} "
        f"processes={summary['process_invocations']} "
        f"A_median_ns={summary['a_median_ns_per_call']:.9f} "
        f"B_median_ns={summary['b_median_ns_per_call']:.9f} "
        f"sd_log={summary['sd_log_contrast']:.9f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", type=Path, required=True)
    parser.add_argument("--sparse", type=Path, required=True)
    parser.add_argument("--aa-a", type=Path, required=True)
    parser.add_argument("--aa-b", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    layout = validate_layout(args.dense, args.sparse)
    (args.output_dir / "layout.json").write_text(
        json.dumps(layout, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    smoke_records = []
    smoke_output = args.output_dir / "smoke-tests.json"

    def persist_smoke() -> None:
        smoke_output.write_text(
            json.dumps(smoke_records, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    for executable in (args.dense, args.sparse, args.aa_a, args.aa_b):
        command = [
            "taskset",
            "-c",
            str(args.cpu),
            str(executable),
            str(WARM_ROUNDS),
            "1",
        ]
        # Recorded before it is judged, and flushed after every attempt, so a
        # failing smoke test leaves its command, status, and streams behind
        # instead of aborting before any of it reaches the evidence directory.
        smoke = subprocess.run(command, text=True, capture_output=True)
        record: dict[str, Any] = {
            "command": command,
            "returncode": smoke.returncode,
            "stdout": smoke.stdout,
            "stderr": smoke.stderr,
            "fields": None,
        }
        smoke_records.append(record)
        persist_smoke()
        if smoke.returncode != 0:
            raise RuntimeError(
                f"smoke test failed with status {smoke.returncode}: {command}"
            )
        record["fields"] = parse_program_output(smoke.stdout)
        persist_smoke()

    ab_rows = run_timing(
        "layout",
        {"A": args.dense, "B": args.sparse},
        args.output_dir,
        args.cpu,
    )
    aa_rows = run_timing(
        "identical-artifact",
        {"A": args.aa_a, "B": args.aa_b},
        args.output_dir,
        args.cpu,
    )
    write_timing_csv(args.output_dir / "timing-layout.csv", ab_rows)
    write_timing_csv(args.output_dir / "timing-identical-artifact.csv", aa_rows)
    ab_summary = analyze_timing(ab_rows, "layout", "sparse4096/dense16")
    aa_summary = analyze_timing(
        aa_rows, "identical-artifact", "dense-hardlink-B/dense-hardlink-A"
    )

    perf_list = checked_run(["perf", "list"]).stdout
    perf_summary = run_perf(
        args.dense,
        args.sparse,
        args.output_dir,
        args.cpu,
        checked_run(["uname", "-m"]).stdout.strip(),
        perf_list,
    )
    summary = {
        "timing_scope": (
            "CLOCK_MONOTONIC_RAW around the measured region after same-process "
            "warm-up; process startup excluded"
        ),
        "interval_scope": (
            "95% Student-t confidence interval for the geometric-mean ratio, "
            "from between-block log-contrast dispersion in this host, binary, "
            "workload, and single run window; not a prediction interval for an "
            "individual block"
        ),
        "layout": ab_summary,
        "identical_artifact": aa_summary,
        "null_calibration": "not_estimated",
        "final_layout": layout,
        "perf": {
            "pass_count": len(perf_summary["passes"]),
            "attempt_count": len(perf_summary["attempts"]),
            "scope": perf_summary["protocol"]["scope"],
        },
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_text = "\n".join(
        [
            format_timing(ab_summary),
            format_timing(aa_summary),
            "null_calibration=not_estimated",
            f"perf_passes={len(perf_summary['passes'])}",
            f"perf_attempts={len(perf_summary['attempts'])}",
            "causal_attribution=not_established",
        ]
    )
    (args.output_dir / "summary.txt").write_text(
        summary_text + "\n", encoding="utf-8"
    )
    print(summary_text)


if __name__ == "__main__":
    main()
