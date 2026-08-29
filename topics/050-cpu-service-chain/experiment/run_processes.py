#!/usr/bin/env python3
"""Run fixed-horizon, process-replicated lock-holder-preemption blocks on Linux."""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path


SEED = 500829
BLOCKS = 8
BURN_CPU_US = 5_000
HOLDER_NICE = 19
SOURCE = Path(__file__).with_name("lock_holder_preemption.c")
OUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "run")
BINARY = OUT_DIR / "lock_holder_preemption"
BASE_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PATH": "/bin:/usr/bin", "TZ": "UTC"}
INTEGER_FIELDS = set()

HEADER = [
    "label",
    "block",
    "period",
    "mode",
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
]
INTEGER_FIELDS.update(field for field in HEADER if field not in {"label", "mode"})


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(handle, value: dict[str, object]) -> None:
    handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def command_output(argv: list[str]) -> dict[str, object]:
    try:
        completed = subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
        return {"argv": argv, "returncode": completed.returncode, "output": completed.stdout.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return {"argv": argv, "error": repr(error)}


def parse_cpu_list(text: str) -> set[int]:
    cpus: set[int] = set()
    for piece in text.split(","):
        bounds = piece.split("-", 1)
        try:
            first = int(bounds[0])
            last = int(bounds[-1])
        except ValueError as error:
            raise RuntimeError(f"malformed kernel CPU list: {text}") from error
        if first < 0 or last < first:
            raise RuntimeError(f"malformed kernel CPU range: {piece}")
        cpus.update(range(first, last + 1))
    if not cpus:
        raise RuntimeError("kernel CPU list is empty")
    return cpus


def cpu_topology() -> tuple[dict[str, object], dict[str, int]]:
    allowed = sorted(os.sched_getaffinity(0))
    groups: dict[tuple[int, int], list[int]] = {}
    records: list[dict[str, object]] = []
    for cpu in allowed:
        cpu_root = Path(f"/sys/devices/system/cpu/cpu{cpu}")
        base = cpu_root / "topology"
        online = read_text(cpu_root / "online")
        if online is not None and online != "1":
            raise RuntimeError(f"selected affinity includes offline cpu{cpu}")
        package_text = read_text(base / "physical_package_id")
        core_text = read_text(base / "core_id")
        siblings = read_text(base / "thread_siblings_list")
        if package_text is None or core_text is None or siblings is None:
            raise RuntimeError(f"cpu{cpu} lacks required package/core/sibling topology")
        try:
            package = int(package_text)
            core = int(core_text)
        except ValueError as error:
            raise RuntimeError(f"cpu{cpu} exposes non-integer package/core topology") from error
        if package < 0 or core < 0 or cpu not in parse_cpu_list(siblings):
            raise RuntimeError(f"cpu{cpu} exposes inconsistent package/core/sibling topology")
        groups.setdefault((package, core), []).append(cpu)
        records.append(
            {
                "cpu": cpu,
                "package": package,
                "core": core,
                "thread_siblings_list": siblings,
            }
        )
    ordered_groups = sorted((key, sorted(cpus)) for key, cpus in groups.items())
    if len(ordered_groups) < 3:
        raise RuntimeError("experiment requires three allowed physical-core groups")
    holder_group = ordered_groups[0]
    waiter_group = ordered_groups[1]
    control_group = ordered_groups[2]
    selected = {
        "holder": holder_group[1][0],
        "waiter": waiter_group[1][0],
        "control": control_group[1][0],
        "holder_sibling": holder_group[1][1] if len(holder_group[1]) > 1 else -1,
    }
    return {"allowed": allowed, "records": records, "groups": ordered_groups}, selected


def sysfs_snapshot(selected: dict[str, int]) -> dict[str, object]:
    cpus: dict[str, object] = {}
    for role, cpu in selected.items():
        if cpu < 0:
            continue
        base = Path(f"/sys/devices/system/cpu/cpu{cpu}")
        freq = base / "cpufreq"
        freq_fields = {}
        for name in (
            "scaling_driver",
            "scaling_governor",
            "scaling_available_governors",
            "scaling_cur_freq",
            "cpuinfo_cur_freq",
            "cpuinfo_min_freq",
            "cpuinfo_max_freq",
            "energy_performance_preference",
        ):
            freq_fields[name] = read_text(freq / name)
        idle_states = []
        for state in sorted((base / "cpuidle").glob("state*")):
            idle_states.append(
                {
                    "state": state.name,
                    "name": read_text(state / "name"),
                    "desc": read_text(state / "desc"),
                    "latency_us": read_text(state / "latency"),
                    "residency_us": read_text(state / "residency"),
                    "disabled": read_text(state / "disable"),
                    "usage_snapshot": read_text(state / "usage"),
                    "time_snapshot": read_text(state / "time"),
                }
            )
        cpus[role] = {"cpu": cpu, "cpufreq": freq_fields, "cpuidle": idle_states}
    return {
        "smt_active": read_text(Path("/sys/devices/system/cpu/smt/active")),
        "smt_control": read_text(Path("/sys/devices/system/cpu/smt/control")),
        "cpus": cpus,
    }


def cpuinfo_summary() -> dict[str, str]:
    wanted = {"model name", "vendor_id", "hardware", "processor", "features", "flags", "cpu implementer", "cpu part"}
    summary: dict[str, str] = {}
    text = read_text(Path("/proc/cpuinfo")) or ""
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = (piece.strip() for piece in line.split(":", 1))
        if key.lower() in wanted and key.lower() not in summary:
            summary[key.lower()] = value
    return summary


def metadata(topology: dict[str, object], selected: dict[str, int], build_argv: list[str]) -> dict[str, object]:
    uname = platform.uname()
    sched_paths = [
        "/proc/sys/kernel/sched_autogroup_enabled",
        "/proc/sys/kernel/sched_rr_timeslice_ms",
        "/proc/sys/kernel/sched_cfs_bandwidth_slice_us",
        "/sys/kernel/debug/sched/features",
    ]
    return {
        "schema": "topic50-campaign.v1",
        "created_utc": utc_now(),
        "target_label": os.environ.get("TOPIC50_TARGET_LABEL"),
        "expected_hostname": os.environ.get("TOPIC50_EXPECTED_HOSTNAME"),
        "expected_architecture": os.environ.get("TOPIC50_EXPECTED_ARCHITECTURE"),
        "source_commit": os.environ.get("SOURCE_COMMIT"),
        "source_archive_sha256": os.environ.get("SOURCE_ARCHIVE_SHA256"),
        "claim": "A low-priority thread holding a mutex can stretch another CPU's wait when a runnable normal-priority thread shares the holder's logical CPU.",
        "non_claims": [
            "This is not a production scheduler-latency distribution.",
            "It does not estimate variation across machines, kernels, CPU families, or workloads.",
            "It does not test priority inheritance, real-time scheduling, or lock implementation throughput.",
            "cpufreq and cpuidle values are snapshots/exposure, not proof of state throughout every run.",
        ],
        "design": {
            "seed": SEED,
            "complete_blocks": BLOCKS,
            "treatment_templates": ["ABBA", "BAAB"],
            "treatment_A": "hog pinned to the holder's logical CPU",
            "treatment_B": "same hog pinned to a third physical core",
            "aa_X": "B settings, label X",
            "aa_Y": "B settings, label Y",
            "holder_cpu_target_us": BURN_CPU_US,
            "holder_nice": HOLDER_NICE,
            "stopping": "fixed; inspect only after all complete blocks; failed invocations retained and never replaced",
            "analysis_unit": "one complete four-period block log contrast",
            "subsample_unit": "one fresh process invocation; loop iterations inside it are not samples",
            "generalization_unit": "this host and observation window only",
            "interference_boundary": "fresh PIDs reset process state, but scheduler, thermal, daemon, and host state can persist across periods",
            "assignment": "four ABBA and four BAAB primary blocks plus four XYYX and four YXXY identical-artifact A/A blocks",
        },
        "uname": {
            "system": uname.system,
            "node": uname.node,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
        },
        "hostname_f": command_output(["hostname", "-f"]),
        "cpu_count_configured": os.cpu_count(),
        "cpu_count_allowed": len(os.sched_getaffinity(0)),
        "effective_affinity": sorted(os.sched_getaffinity(0)),
        "process_scheduler_policy": os.sched_getscheduler(0),
        "process_scheduler_priority": os.sched_getparam(0).sched_priority,
        "process_nice": os.getpriority(os.PRIO_PROCESS, 0),
        "cpuinfo": cpuinfo_summary(),
        "topology": topology,
        "selected": selected,
        "sysfs": sysfs_snapshot(selected),
        "scheduler_exposure": {path: read_text(Path(path)) for path in sched_paths},
        "toolchain": {
            "cc": command_output(["cc", "--version"]),
            "clang": command_output(["clang", "--version"]),
            "rustc": command_output(["rustc", "-Vv"]),
            "python": command_output([sys.executable, "--version"]),
            "build_argv": build_argv,
        },
        "base_environment": BASE_ENVIRONMENT,
    }


def make_schedule(a: str, b: str, seed: int) -> list[str]:
    templates = [a + b + b + a] * (BLOCKS // 2) + [b + a + a + b] * (BLOCKS // 2)
    random.Random(seed).shuffle(templates)
    return templates


# Frozen images of make_schedule(SEED) and make_schedule(SEED + 1). The
# campaign refuses to start if the interpreter's shuffle diverges from these,
# so a Python-version change fails closed here instead of at receipt
# validation, which compares schedule.json against the same frozen values.
FROZEN_TREATMENT_SCHEDULE = ["BAAB", "ABBA", "ABBA", "BAAB", "BAAB", "ABBA", "BAAB", "ABBA"]
FROZEN_AA_SCHEDULE = ["YXXY", "YXXY", "XYYX", "YXXY", "XYYX", "XYYX", "XYYX", "YXXY"]


def row_acceptance_error(
    result: dict[str, object], selected: dict[str, int], experiment: str, label: str
) -> str | None:
    """Mirrors the analyzer's per-row acceptance rules so a semantically
    invalid attempt fails the campaign immediately and lands in the failure
    ledger instead of surfacing only at post-campaign analysis."""
    for role in ("holder", "waiter", "hog"):
        if result[f"{role}_pin_rc"] != 0 or result[f"{role}_affinity_exact"] != 1:
            return f"{role} affinity failure"
    if result["holder_nice_set_rc"] != 0 or result["holder_nice_observed"] != HOLDER_NICE:
        return "holder nice failure"
    if result["waiter_nice_observed"] != 0 or result["hog_nice_observed"] != 0:
        return "waiter or hog did not run at nice 0"
    for role in ("holder", "waiter", "hog"):
        if (
            result[f"{role}_sched_get_rc"] != 0
            or result[f"{role}_sched_policy"] != 0
            or result[f"{role}_sched_priority"] != 0
        ):
            return f"{role} did not run under SCHED_OTHER priority 0"
    if not 4_900_000 <= int(result["holder_cpu_ns"]) <= 6_000_000:
        return "holder CPU-time control escaped 4.9-6.0 ms"
    if int(result["waiter_voluntary_context_switches"]) < 1:
        return "waiter acquired the lock without blocking"
    if result["holder_start_cpu"] != selected["holder"] or result["holder_end_cpu"] != selected["holder"]:
        return "holder ran on unexpected CPU"
    if result["waiter_start_cpu"] != selected["waiter"] or result["waiter_end_cpu"] != selected["waiter"]:
        return "waiter ran on unexpected CPU"
    expected_hog = selected["holder"] if experiment == "treatment" and label == "A" else selected["control"]
    if result["hog_cpu_requested"] != expected_hog:
        return "wrong hog assignment"
    if result["hog_start_cpu"] != expected_hog or result["hog_end_cpu"] != expected_hog:
        return "hog ran on unexpected CPU"
    return None


def run_one(
    writer: csv.writer,
    attempts_file,
    journal_file,
    failures_file,
    raw_dir: Path,
    selected: dict[str, int],
    experiment: str,
    label: str,
    block: int,
    period: int,
    sequence: int,
) -> None:
    if experiment == "treatment" and label == "A":
        mode = "same_cpu"
        hog_cpu = selected["holder"]
    else:
        mode = "separate_core"
        hog_cpu = selected["control"]
    argv = [
        str(BINARY),
        label,
        str(block),
        str(period),
        mode,
        str(selected["holder"]),
        str(selected["waiter"]),
        str(hog_cpu),
        str(HOLDER_NICE),
        str(BURN_CPU_US),
    ]
    stem = f"{sequence:03d}-{experiment}-block{block:02d}-p{period}-{label}"
    stdout_relative = f"raw/{stem}.stdout"
    stderr_relative = f"raw/{stem}.stderr"
    status_relative = f"raw/{stem}.status.json"
    binary_before = sha256(BINARY)
    started_utc = utc_now()
    start_journal = {
        "schema": "topic50-attempt-journal.v1",
        "event": "attempt-start",
        "sequence": sequence,
        "experiment": experiment,
        "block": block,
        "period": period,
        "label": label,
        "mode": mode,
        "journaled_utc": started_utc,
        "journaled_monotonic_ns": time.monotonic_ns(),
    }
    append_jsonl(journal_file, start_journal)
    started_monotonic_ns = time.monotonic_ns()
    process = subprocess.Popen(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=BASE_ENVIRONMENT,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    ended_monotonic_ns = time.monotonic_ns()
    binary_after = sha256(BINARY)
    artifact_error = None if binary_before == binary_after else "binary mutated during attempt"
    result: dict[str, object] | None = None
    validation_error = None
    lines = stdout.splitlines()
    if process.returncode == 0 and not timed_out and artifact_error is None and len(lines) == 1 and lines[0].strip():
        try:
            values = next(csv.reader([lines[0]]))
            if len(values) != len(HEADER):
                raise ValueError(f"expected {len(HEADER)} CSV fields, got {len(values)}")
            result = dict(zip(HEADER, values))
            for field in INTEGER_FIELDS:
                result[field] = int(result[field])
            if result["pid"] != process.pid:
                raise ValueError("native PID differs from launched PID")
        except (ValueError, csv.Error) as error:
            validation_error = str(error)
    else:
        validation_error = "process failed, timed out, changed binary, or emitted non-single-line stdout"

    if result is not None and validation_error is None:
        validation_error = row_acceptance_error(result, selected, experiment, label)

    valid = (
        process.returncode == 0
        and not timed_out
        and artifact_error is None
        and result is not None
        and validation_error is None
    )
    status = {
        "schema": "topic50-attempt.v1",
        "sequence": sequence,
        "experiment": experiment,
        "block": block,
        "period": period,
        "label": label,
        "mode": mode,
        "command": argv,
        "environment": BASE_ENVIRONMENT,
        "timeout_seconds": 30,
        "stdout_path": stdout_relative,
        "stderr_path": stderr_relative,
        "status_path": status_relative,
        "started_utc": started_utc,
        "started_monotonic_ns": started_monotonic_ns,
        "ended_monotonic_ns": ended_monotonic_ns,
        "wall_ns": ended_monotonic_ns - started_monotonic_ns,
        "pid": process.pid,
        "returncode": process.returncode,
        "timed_out": timed_out,
        "binary_sha256_before": binary_before,
        "binary_sha256_after": binary_after,
        "artifact_error": artifact_error,
        "stdout": stdout,
        "stderr": stderr,
        "result": result,
        "valid": valid,
        "validation_error": validation_error,
    }
    (raw_dir / f"{stem}.stdout").write_text(stdout, encoding="utf-8")
    (raw_dir / f"{stem}.stderr").write_text(stderr, encoding="utf-8")
    (raw_dir / f"{stem}.status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    append_jsonl(attempts_file, status)
    append_jsonl(
        journal_file,
        {
            "schema": "topic50-attempt-journal.v1",
            "event": "attempt-end",
            "sequence": sequence,
            "outcome": "valid" if valid else "invalid",
            "pid": process.pid,
            "journaled_utc": utc_now(),
            "journaled_monotonic_ns": time.monotonic_ns(),
        },
    )
    if not valid:
        append_jsonl(failures_file, status)
        raise RuntimeError(f"failed invocation retained at {status_relative}")
    assert result is not None
    writer.writerow([experiment, *[result[field] for field in HEADER]])


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in {"-h", "--help"}:
        print(f"usage: {sys.argv[0]} OUTPUT_DIR", file=sys.stderr)
        return 0 if len(sys.argv) == 2 else 2
    if platform.system() != "Linux":
        raise RuntimeError("this focused experiment intentionally requires Linux")
    if os.sched_getscheduler(0) != os.SCHED_OTHER or os.sched_getparam(0).sched_priority != 0:
        raise RuntimeError("campaign controller must run under SCHED_OTHER with priority 0")
    if os.getpriority(os.PRIO_PROCESS, 0) != 0:
        raise RuntimeError("campaign controller must begin at nice 0")
    if OUT_DIR.exists():
        raise RuntimeError(f"output path already exists: {OUT_DIR}")
    for name, length in (("SOURCE_COMMIT", 40), ("SOURCE_ARCHIVE_SHA256", 64)):
        value = os.environ.get(name, "")
        if len(value) != length or any(character not in "0123456789abcdef" for character in value.lower()):
            raise RuntimeError(f"{name} is missing or malformed")
    for name in ("TOPIC50_TARGET_LABEL", "TOPIC50_EXPECTED_HOSTNAME", "TOPIC50_EXPECTED_ARCHITECTURE"):
        if not os.environ.get(name):
            raise RuntimeError(f"{name} is required")
    OUT_DIR.mkdir(parents=True, exist_ok=False)
    topology, selected = cpu_topology()
    build_argv = [
        "cc",
        "-O2",
        "-g",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pthread",
        str(SOURCE),
        "-o",
        str(BINARY),
    ]
    build_started_ns = time.monotonic_ns()
    build = subprocess.run(
        build_argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=BASE_ENVIRONMENT,
        check=False,
    )
    build_ended_ns = time.monotonic_ns()
    (OUT_DIR / "build.stdout").write_text(build.stdout, encoding="utf-8")
    (OUT_DIR / "build.stderr").write_text(build.stderr, encoding="utf-8")
    (OUT_DIR / "build.status.json").write_text(
        json.dumps(
            {
                "schema": "topic50-build.v1",
                "command": build_argv,
                "environment": BASE_ENVIRONMENT,
                "returncode": build.returncode,
                "started_monotonic_ns": build_started_ns,
                "ended_monotonic_ns": build_ended_ns,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if build.returncode != 0:
        raise RuntimeError("native build failed; retained build receipts")
    digest = sha256(BINARY)
    meta = metadata(topology, selected, build_argv)
    meta["binary_sha256"] = digest
    meta["source_sha256"] = sha256(SOURCE)
    (OUT_DIR / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    treatment_schedule = make_schedule("A", "B", SEED)
    aa_schedule = make_schedule("X", "Y", SEED + 1)
    if treatment_schedule != FROZEN_TREATMENT_SCHEDULE or aa_schedule != FROZEN_AA_SCHEDULE:
        raise RuntimeError("interpreter-derived schedule diverged from the frozen assignment")
    (OUT_DIR / "schedule.json").write_text(
        json.dumps({"seed": SEED, "treatment": treatment_schedule, "aa": aa_schedule}, indent=2) + "\n",
        encoding="utf-8",
    )

    raw_dir = OUT_DIR / "raw"
    raw_dir.mkdir()
    sequence = 0
    with (
        (OUT_DIR / "raw.csv").open("w", newline="", encoding="utf-8") as raw_file,
        (OUT_DIR / "attempts.jsonl").open("x", encoding="utf-8") as attempts_file,
        (OUT_DIR / "attempt-journal.jsonl").open("x", encoding="utf-8") as journal_file,
        (OUT_DIR / "failures.jsonl").open("w", encoding="utf-8") as failures_file,
    ):
        writer = csv.writer(raw_file)
        writer.writerow(["experiment", *HEADER])
        for experiment, schedule in (("treatment", treatment_schedule), ("aa", aa_schedule)):
            for block, template in enumerate(schedule, start=1):
                for period, label in enumerate(template, start=1):
                    sequence += 1
                    run_one(
                        writer,
                        attempts_file,
                        journal_file,
                        failures_file,
                        raw_dir,
                        selected,
                        experiment,
                        label,
                        block,
                        period,
                        sequence,
                    )
                    raw_file.flush()
                    os.fsync(raw_file.fileno())
    if sequence != 64:
        raise RuntimeError(f"campaign produced {sequence} attempts, expected 64")
    print(json.dumps({"out_dir": str(OUT_DIR), "binary_sha256": digest, "selected": selected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
