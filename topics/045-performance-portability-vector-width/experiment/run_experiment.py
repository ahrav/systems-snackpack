#!/usr/bin/env python3
"""Run complete ABBA/BAAB blocks and retain every process attempt."""

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import statistics
import subprocess
import time
from pathlib import Path


T_CRITICAL_975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201,
    12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120,
    17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080,
    22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

PROBE_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": os.defpath,
    "TZ": "UTC",
}
PROCESS_TIMEOUT_SECONDS = 120


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def output_text(value):
    """Normalize timeout output so every failed attempt remains JSON-serializable."""

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def read_cpu_stat(cpu):
    wanted = f"cpu{cpu}"
    with open("/proc/stat", "r", encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if fields and fields[0] == wanted:
                values = [int(value) for value in fields[1:]]
                return {
                    "user": values[0], "nice": values[1], "system": values[2],
                    "idle": values[3], "iowait": values[4], "irq": values[5],
                    "softirq": values[6], "steal": values[7] if len(values) > 7 else 0,
                }
    raise RuntimeError(f"missing {wanted} in /proc/stat")


def parse_perf(stderr):
    metrics = {}
    for line in stderr.splitlines():
        fields = line.strip().split(",")
        if len(fields) < 3:
            continue
        event = fields[2].removesuffix(":u")
        if event not in {"task-clock", "cycles", "ref-cycles", "instructions", "context-switches", "cpu-migrations"}:
            continue
        raw = fields[0].strip()
        try:
            value = float(raw)
        except ValueError:
            value = None
        try:
            time_running_ns = int(fields[3])
        except (ValueError, IndexError):
            time_running_ns = None
        try:
            running_pct = float(fields[4])
        except (ValueError, IndexError):
            running_pct = None
        metrics[event] = {
            "value": value,
            "time_running_ns": time_running_ns,
            "running_pct": running_pct,
        }
    return metrics


def parse_result(stdout):
    result_lines = [line for line in stdout.splitlines() if line.startswith("RESULT\t")]
    if len(result_lines) != 1:
        return None
    fields = result_lines[0].split("\t")
    if len(fields) != 7:
        return None
    try:
        return {
            "mode": fields[1], "steps": int(fields[2]),
            "warmup_ns": int(fields[3]), "main_ns": int(fields[4]),
            "checksum": float(fields[5]), "observed_cpu": int(fields[6]),
        }
    except ValueError:
        return None


def invoke(binary, mode, steps, warmup_steps, cpu, label):
    events = "{cycles:u,ref-cycles:u}" if platform.machine() == "x86_64" else "cycles:u"
    command = [
        "perf", "stat", "--no-big-num", "-x,", "-e", events,
        "--", "taskset", "-c", str(cpu), str(binary), mode, str(steps), str(warmup_steps),
    ]
    cpu_before = read_cpu_stat(cpu)
    wall_start = time.monotonic_ns()
    binary_sha256_before = file_sha256(binary)
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            env=PROBE_ENVIRONMENT,
            timeout=PROCESS_TIMEOUT_SECONDS,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as error:
        returncode = 124
        stdout = output_text(error.stdout)
        stderr = output_text(error.stderr)
        timed_out = True
    wall_end = time.monotonic_ns()
    cpu_after = read_cpu_stat(cpu)
    parsed = parse_result(stdout)
    perf = parse_perf(stderr)
    binary_sha256_after = file_sha256(binary)
    return {
        "label": label,
        "mode": mode,
        "command": command,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "probe_environment": PROBE_ENVIRONMENT,
        "timeout_seconds": PROCESS_TIMEOUT_SECONDS,
        "binary_sha256_before": binary_sha256_before,
        "binary_sha256_after": binary_sha256_after,
        "wall_ns": wall_end - wall_start,
        "result": parsed,
        "perf": perf,
        "cpu_stat_before": cpu_before,
        "cpu_stat_after": cpu_after,
        "cpu_stat_delta": {key: cpu_after[key] - cpu_before[key] for key in cpu_before},
    }


def run_is_valid(run, cpu, steps, expected_checksum):
    result = run.get("result")
    if run.get("returncode") != 0 or run.get("timed_out") or result is None:
        return False
    if result["mode"] != run["mode"] or result["steps"] != steps or result["observed_cpu"] != cpu:
        return False
    tolerance = 64.0 * 2.0 ** -52 * max(1.0, abs(expected_checksum))
    if not math.isfinite(result["checksum"]) or abs(result["checksum"] - expected_checksum) > tolerance:
        return False
    if result["main_ns"] <= 0 or result["warmup_ns"] < 0:
        return False
    if run["binary_sha256_before"] != run["binary_sha256_after"]:
        return False
    cycles = run["perf"].get("cycles", {})
    cycles_value = cycles.get("value")
    cycles_running = cycles.get("running_pct")
    cycles_time = cycles.get("time_running_ns")
    if (
        not isinstance(cycles_value, (int, float))
        or not math.isfinite(cycles_value)
        or cycles_value <= 0.0
        or not isinstance(cycles_running, (int, float))
        or not math.isfinite(cycles_running)
        or not 99.0 <= cycles_running <= 100.0
        or not isinstance(cycles_time, int)
        or cycles_time <= 0
    ):
        return False
    if platform.machine() == "x86_64":
        reference = run["perf"].get("ref-cycles", {})
        reference_value = reference.get("value")
        reference_running = reference.get("running_pct")
        reference_time = reference.get("time_running_ns")
        if (
            not isinstance(reference_value, (int, float))
            or not math.isfinite(reference_value)
            or reference_value <= 0.0
            or not isinstance(reference_running, (int, float))
            or not math.isfinite(reference_running)
            or not 99.0 <= reference_running <= 100.0
            or not isinstance(reference_time, int)
            or reference_time <= 0
        ):
            return False
        if cycles_time != reference_time:
            return False
    return True


def contrast_for_block(template, runs, baseline_label, candidate_label,
                       cpu, steps, expected_checksum):
    if len(runs) != 4 or any(
        not run_is_valid(run, cpu, steps, expected_checksum) for run in runs
    ):
        return None
    observed = "".join(run["label"] for run in runs)
    if observed != template:
        return None
    logs = [math.log(run["result"]["main_ns"]) for run in runs]
    if template == "ABBA":
        value = ((logs[1] + logs[2]) - (logs[0] + logs[3])) / 2.0
    elif template == "BAAB":
        value = ((logs[0] + logs[3]) - (logs[1] + logs[2])) / 2.0
    else:
        raise ValueError(template)
    return {
        "log_ratio": value,
        "ratio": math.exp(value),
        "baseline_label": baseline_label,
        "candidate_label": candidate_label,
    }


def summarize_contrasts(contrasts):
    values = [item["log_ratio"] for item in contrasts if item is not None]
    if not values:
        return {"complete_blocks": 0}
    mean_log = statistics.mean(values)
    summary = {
        "complete_blocks": len(values),
        "geomean_ratio": math.exp(mean_log),
        "log_contrast_mean": mean_log,
    }
    if len(values) >= 2:
        sd = statistics.stdev(values)
        df = len(values) - 1
        tcrit = T_CRITICAL_975.get(df, 1.96)
        half = tcrit * sd / math.sqrt(len(values))
        summary.update({
            "log_contrast_sd": sd,
            "multiplicative_sd": math.exp(sd),
            "ci95_ratio_low": math.exp(mean_log - half),
            "ci95_ratio_high": math.exp(mean_log + half),
            "ci_method": "two-sided paired-t interval over complete-block log contrasts",
        })
    return summary


def summarize_run_metrics(runs, mode, cpu, steps, expected_checksum):
    selected = [
        run for run in runs
        if run["mode"] == mode and run_is_valid(run, cpu, steps, expected_checksum)
    ]
    output = {"process_runs": len(selected)}
    for key in ["main_ns", "warmup_ns"]:
        values = [run["result"][key] for run in selected]
        if values:
            output[f"{key}_median"] = statistics.median(values)
            output[f"{key}_min"] = min(values)
            output[f"{key}_max"] = max(values)
    for event in ["cycles", "ref-cycles"]:
        values = [run["perf"].get(event, {}).get("value") for run in selected]
        values = [value for value in values if value is not None]
        if values:
            output[f"perf_{event}_median"] = statistics.median(values)
        running = [run["perf"].get(event, {}).get("running_pct") for run in selected]
        running = [value for value in running if value is not None]
        if running:
            output[f"perf_{event}_running_pct_min"] = min(running)
            output[f"perf_{event}_running_pct_median"] = statistics.median(running)
    ratios = []
    for run in selected:
        cycles = run["perf"].get("cycles", {}).get("value")
        reference = run["perf"].get("ref-cycles", {}).get("value")
        if cycles is not None and reference not in (None, 0):
            ratios.append(cycles / reference)
    if ratios:
        output["cycles_per_ref_cycle_median"] = statistics.median(ratios)
    output["steal_ticks_total"] = sum(run["cpu_stat_delta"]["steal"] for run in selected)
    output["cpu_mismatch_count"] = sum(run["result"]["observed_cpu"] != cpu for run in selected)
    return output


def schedule_templates(blocks, seed):
    templates = ["ABBA"] * (blocks // 2) + ["BAAB"] * (blocks // 2)
    if blocks % 2:
        templates.append("ABBA" if seed % 2 == 0 else "BAAB")
    random.Random(seed).shuffle(templates)
    return templates


def run_comparison(binary, outdir, baseline_mode, candidate_mode, name, blocks, seed,
                   steps, warmup_steps, cpu, washout_seconds, expected_checksum, aa=False):
    templates = schedule_templates(blocks, seed)
    all_runs = []
    contrasts = []
    raw_path = outdir / f"{name}-raw.jsonl"
    with raw_path.open("w", encoding="utf-8") as raw:
        for block_index, template in enumerate(templates):
            block_runs = []
            for position, label in enumerate(template, start=1):
                mode = baseline_mode if label == "A" else candidate_mode
                run = invoke(binary, mode, steps, warmup_steps, cpu, label)
                run.update({
                    "comparison": name, "block": block_index,
                    "position": position, "template": template,
                    "aa_identical_mode": aa,
                })
                raw.write(json.dumps(run, sort_keys=True) + "\n")
                raw.flush()
                os.fsync(raw.fileno())
                all_runs.append(run)
                block_runs.append(run)
                time.sleep(washout_seconds)
            contrast = contrast_for_block(
                template, block_runs, "A", "B", cpu, steps, expected_checksum
            )
            if contrast is not None:
                contrast.update({"comparison": name, "block": block_index, "template": template})
            contrasts.append(contrast)

    summary = {
        "name": name,
        "baseline_mode": baseline_mode,
        "candidate_mode": candidate_mode,
        "aa_identical_mode": aa,
        "templates": templates,
        "seed": seed,
        "requested_blocks": blocks,
        "attempted_processes": len(all_runs),
        "failed_processes": sum(
            not run_is_valid(run, cpu, steps, expected_checksum) for run in all_runs
        ),
        "contrast": summarize_contrasts(contrasts),
        "baseline_metrics": summarize_run_metrics(
            all_runs, baseline_mode, cpu, steps, expected_checksum
        ),
        "candidate_metrics": summarize_run_metrics(
            all_runs, candidate_mode, cpu, steps, expected_checksum
        ),
    }
    with (outdir / f"{name}-contrasts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["comparison", "block", "template", "log_ratio", "ratio"])
        writer.writeheader()
        for contrast in contrasts:
            if contrast is not None:
                writer.writerow({key: contrast[key] for key in writer.fieldnames})
    with (outdir / f"{name}-summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return summary


def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--steps", type=int, default=20_000_000)
    parser.add_argument("--warmup-steps", type=int, default=2_000_000)
    parser.add_argument("--blocks", type=int, default=8)
    parser.add_argument("--aa-blocks", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--washout-seconds", type=float, default=0.2)
    args = parser.parse_args()

    if args.outdir.exists():
        raise SystemExit(f"output directory already exists: {args.outdir}")
    args.outdir.mkdir(parents=True)
    binary = args.binary.resolve()
    listed = subprocess.run([str(binary), "--list"], text=True, capture_output=True, check=True)
    modes = listed.stdout.split()
    correctness_command = [str(binary), "--check", str(args.steps)]
    check = subprocess.run(
        correctness_command,
        text=True,
        capture_output=True,
        check=False,
        env=PROBE_ENVIRONMENT,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )
    if check.returncode != 0:
        raise SystemExit(f"correctness check failed:\n{check.stdout}\n{check.stderr}")
    scalar_checks = [
        line.split("\t") for line in check.stdout.splitlines()
        if line.startswith("CHECK\tscalar\t")
    ]
    if len(scalar_checks) != 1:
        raise SystemExit("correctness output has no unique scalar oracle")
    expected_checksum = float(scalar_checks[0][2])
    if not math.isfinite(expected_checksum):
        raise SystemExit("same-step scalar oracle is not finite")
    binary_sha256_start = file_sha256(binary)

    manifest = {
        "schema": 1,
        "hostname": platform.node(),
        "machine": platform.machine(),
        "binary": str(binary),
        "binary_sha256": file_sha256(binary),
        "binary_sha256_start": binary_sha256_start,
        "modes": modes,
        "correctness_stdout": check.stdout,
        "correctness_stderr": check.stderr,
        "correctness_command": correctness_command,
        "expected_checksum": expected_checksum,
        "cpu": args.cpu,
        "steps": args.steps,
        "warmup_steps": args.warmup_steps,
        "blocks": args.blocks,
        "aa_blocks": args.aa_blocks,
        "seed": args.seed,
        "washout_seconds": args.washout_seconds,
        "assignment": "equal-count ABBA/BAAB templates, seed-shuffled; each letter is a fresh process",
        "analysis_unit": "one complete four-process block log contrast",
        "timing_boundary": "CLOCK_MONOTONIC_RAW around main fixed-work kernel after same-mode warmup",
        "perf_boundary": "perf stat child boundary includes taskset, process startup, warmup, and main kernel",
        "perf_frequency_witness": "x86 cycles and ref-cycles are one minimal simultaneous group; Arm records cycles only because ref-cycles is unsupported",
        "probe_environment": PROBE_ENVIRONMENT,
        "process_timeout_seconds": PROCESS_TIMEOUT_SECONDS,
        "interval_scope": "marginal unadjusted 95% interval for each named comparison; no joint family coverage claim",
    }
    with (args.outdir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    summaries = []
    comparison_index = 0
    for candidate in (mode for mode in modes if mode != "scalar"):
        summaries.append(run_comparison(
            binary, args.outdir, "scalar", candidate, f"scalar-vs-{candidate}",
            args.blocks, args.seed + comparison_index, args.steps, args.warmup_steps,
            args.cpu, args.washout_seconds, expected_checksum,
        ))
        comparison_index += 1
    if platform.machine() == "x86_64":
        for baseline, candidate in [("v128", "v256"), ("v256", "v512")]:
            if baseline in modes and candidate in modes:
                summaries.append(run_comparison(
                    binary, args.outdir, baseline, candidate, f"{baseline}-vs-{candidate}",
                    args.blocks, args.seed + comparison_index, args.steps, args.warmup_steps,
                    args.cpu, args.washout_seconds, expected_checksum,
                ))
                comparison_index += 1
    aa_mode = "v256" if "v256" in modes else "v128"
    summaries.append(run_comparison(
        binary, args.outdir, aa_mode, aa_mode, f"aa-{aa_mode}",
        args.aa_blocks, args.seed + 100, args.steps, args.warmup_steps,
        args.cpu, args.washout_seconds, expected_checksum, aa=True,
    ))
    with (args.outdir / "all-summaries.json").open("w", encoding="utf-8") as handle:
        json.dump(summaries, handle, indent=2, sort_keys=True)
        handle.write("\n")
    binary_sha256_end = file_sha256(binary)
    if binary_sha256_end != binary_sha256_start:
        raise SystemExit("binary changed during the fixed schedule")
    with (args.outdir / "binary-final.sha256").open("w", encoding="utf-8") as handle:
        handle.write(binary_sha256_end + "\n")
    print(json.dumps(summaries, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
