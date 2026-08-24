#!/usr/bin/env python3
"""Reject incomplete or internally inconsistent Topic 45 host evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import statistics
import subprocess
import tarfile
from pathlib import PurePosixPath
from pathlib import Path


T_CRITICAL_975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201,
    12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120,
    17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080,
    22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

REQUIRED = (
    "source-archive.tar.gz",
    "source-manifest-before.sha256",
    "source-manifest-after.sha256",
    "source-manifest.diff",
    "host.txt",
    "correctness.txt",
    "build.txt",
    "modes.txt",
    "binary/width_bench",
    "binary.sha256",
    "protocol-self-test.json",
    "experiment/binary-final.sha256",
    "codegen/all.asm",
    "codegen/symbols.txt",
    "codegen/kernel_scalar.asm",
    "codegen/kernel_v128.asm",
    "codegen/codegen-check.json",
    "codegen/sha256sums.txt",
    "experiment/manifest.json",
    "experiment/all-summaries.json",
)

CRITICAL_HOST_KEYS = {
    "captured_utc",
    "source_commit",
    "source_archive_sha256",
    "ssh_target_label",
    "ssh_resolved_hostname",
    "runtime_hostname",
    "architecture",
    "kernel_release",
    "cpu",
    "available_cpu_count",
    "allowed_affinity",
    "smt_active",
    "thread_siblings",
    "perf_event_paranoid",
    "cpufreq_available",
    "turbostat_available",
    "steps",
    "warmup_steps",
    "build_flags",
}

# One stable marker per tool section that run_host.sh appends after the
# key/value block. A receipt truncated after the keys would otherwise pass
# even though the CPU identity, toolchain versions, target features, and
# perf event sections are part of the acceptance contract.
CRITICAL_HOST_SECTIONS = (
    "Architecture:",  # lscpu CPU identity and topology
    "gcc (",  # gcc --version banner
    "Python 3.",  # python3 --version
    "GNU objdump",  # objdump --version
    "GNU nm",  # nm --version
    "rustc 1.",  # rustc -Vv
    "cargo 1.",  # cargo -Vv
    "perf version",  # perf version
    "Features supported by",  # rustc --print target-features
    "The following options",  # gcc -march=native -Q --help=target
    "cpu-cycles",  # perf list hw
)


def sha256(path: Path) -> str:
    """Return one file's SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def key_values(path: Path) -> dict[str, str]:
    """Read the unambiguous key-value lines from a mixed host receipt."""

    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key.replace("_", "").isalnum():
                if key in CRITICAL_HOST_KEYS and key in result:
                    raise ValueError(f"host receipt repeats critical field {key}")
                result[key] = value
    return result


def parse_sha256_manifest(path: Path) -> dict[str, str]:
    """Parse GNU `sha256sum` output with two-space filename separation."""

    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if len(digest) != 64 or name in result:
            raise ValueError(f"invalid SHA-256 manifest entry in {path}")
        result[name] = digest
    return result


def verify_source_archive(root: Path, host: dict[str, str]) -> None:
    """Bind the retained archive, embedded commit, and extracted-tree manifest."""

    archive_path = root / "source-archive.tar.gz"
    if sha256(archive_path) != host.get("source_archive_sha256"):
        raise ValueError("source archive digest differs from host receipt")
    expected_commit = host.get("source_commit", "")
    if len(expected_commit) != 40:
        raise ValueError("host receipt has no full source commit")
    with tarfile.open(archive_path, "r:gz") as archive:
        embedded_commit = archive.pax_headers.get("comment")
        members = archive.getmembers()
        if embedded_commit != expected_commit:
            raise ValueError("Git archive commit does not match host receipt")
        names = set()
        roots = set()
        for member in members:
            path = PurePosixPath(member.name)
            if member.name in names:
                raise ValueError(f"source archive repeats member {member.name}")
            names.add(member.name)
            if (
                not path.parts
                or path.parts[0] in ("", ".")
                or path.is_absolute()
                or ".." in path.parts
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError(f"source archive has unsafe member {member.name}")
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError("source archive must contain exactly one top-level root")
        archive_root = next(iter(roots))
        root_entries = [
            member for member in members
            if PurePosixPath(member.name).parts == (archive_root,)
        ]
        if len(root_entries) != 1 or not root_entries[0].isdir():
            raise ValueError("source archive lacks one directory entry for its root")
        anchors = [
            member.name for member in members
            if member.name.endswith("/topics/045-performance-portability-vector-width/experiment/run_host.sh")
        ]
        if len(anchors) != 1:
            raise ValueError("source archive lacks one unique Topic 45 runner")
        prefix = anchors[0].removesuffix("topics/045-performance-portability-vector-width/experiment/run_host.sh")
        archived = {}
        for member in members:
            if not member.isfile():
                continue
            if not member.name.startswith(prefix):
                raise ValueError("archive member lies outside the source prefix")
            relative = member.name[len(prefix):]
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"cannot read archive member {member.name}")
            archived[relative] = hashlib.sha256(handle.read()).hexdigest()
    retained = parse_sha256_manifest(root / "source-manifest-before.sha256")
    if archived != retained:
        raise ValueError("archive contents differ from the retained source manifest")


def close(actual: float, expected: float, name: str) -> None:
    """Require a serialized summary value to match its raw recomputation."""

    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15):
        raise ValueError(f"{name}: {actual} != recomputed {expected}")


def parse_result_output(stdout: str) -> dict | None:
    """Independently parse one benchmark result line."""

    lines = [line for line in stdout.splitlines() if line.startswith("RESULT\t")]
    if len(lines) != 1:
        return None
    fields = lines[0].split("\t")
    if len(fields) != 7:
        return None
    return {
        "mode": fields[1],
        "steps": int(fields[2]),
        "warmup_ns": int(fields[3]),
        "main_ns": int(fields[4]),
        "checksum": float(fields[5]),
        "observed_cpu": int(fields[6]),
    }


def parse_perf_output(stderr: str) -> dict[str, dict]:
    """Independently parse the retained comma-separated `perf stat` rows."""

    metrics = {}
    for line in stderr.splitlines():
        fields = line.strip().split(",")
        if len(fields) < 3:
            continue
        event = fields[2].removesuffix(":u")
        if event not in {"cycles", "ref-cycles"}:
            continue
        try:
            value = float(fields[0].strip())
            time_running_ns = int(fields[3])
            running_pct = float(fields[4])
        except (ValueError, IndexError):
            value = None
            time_running_ns = None
            running_pct = None
        metrics[event] = {
            "value": value,
            "time_running_ns": time_running_ns,
            "running_pct": running_pct,
        }
    return metrics


def recompute_metrics(rows: list[dict], mode: str, cpu: int) -> dict:
    """Recompute the runner's per-mode medians and placement canaries."""

    selected = [row for row in rows if row["mode"] == mode]
    output = {"process_runs": len(selected)}
    for key in ("main_ns", "warmup_ns"):
        values = [row["result"][key] for row in selected]
        output[f"{key}_median"] = statistics.median(values)
        output[f"{key}_min"] = min(values)
        output[f"{key}_max"] = max(values)
    for event in ("cycles", "ref-cycles"):
        values = [row["perf"].get(event, {}).get("value") for row in selected]
        values = [value for value in values if value is not None]
        if values:
            output[f"perf_{event}_median"] = statistics.median(values)
        running = [row["perf"].get(event, {}).get("running_pct") for row in selected]
        running = [value for value in running if value is not None]
        if running:
            output[f"perf_{event}_running_pct_min"] = min(running)
            output[f"perf_{event}_running_pct_median"] = statistics.median(running)
    frequency_witness = []
    for row in selected:
        cycles = row["perf"].get("cycles", {}).get("value")
        reference = row["perf"].get("ref-cycles", {}).get("value")
        if cycles is not None and reference not in (None, 0):
            frequency_witness.append(cycles / reference)
    if frequency_witness:
        output["cycles_per_ref_cycle_median"] = statistics.median(frequency_witness)
    output["steal_ticks_total"] = sum(row["cpu_stat_delta"]["steal"] for row in selected)
    output["cpu_mismatch_count"] = sum(row["result"]["observed_cpu"] != cpu for row in selected)
    return output


def valid_counter(counter: dict) -> bool:
    """Return whether one retained counter is finite, positive, and unscheduled by at most 1%."""

    value = counter.get("value")
    running = counter.get("running_pct")
    time_running = counter.get("time_running_ns")
    return (
        isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0.0
        and isinstance(running, (int, float))
        and math.isfinite(running)
        and 99.0 <= running <= 100.0
        and isinstance(time_running, int)
        and time_running > 0
    )


def recompute(raw_path: Path, summary: dict, manifest: dict, architecture: str) -> dict:
    """Validate process rows and recompute block-level statistics."""

    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    requested = summary["requested_blocks"]
    if len(rows) != requested * 4 or summary["attempted_processes"] != len(rows):
        raise ValueError(f"{raw_path.name}: wrong process count")

    by_block: dict[int, list[dict]] = {}
    checksums = []
    expected_templates = ["ABBA"] * (requested // 2) + ["BAAB"] * (requested // 2)
    random.Random(summary["seed"]).shuffle(expected_templates)
    if summary["templates"] != expected_templates:
        raise ValueError(f"{raw_path.name}: schedule does not match its fixed seed")
    binary_digest = manifest["binary_sha256_start"]
    expected_environment = {"LANG": "C", "LC_ALL": "C", "PATH": os.defpath, "TZ": "UTC"}
    expected_events = "{cycles:u,ref-cycles:u}" if architecture == "x86_64" else "cycles:u"
    expected_checksum = manifest["expected_checksum"]
    if not isinstance(expected_checksum, (int, float)) or not math.isfinite(expected_checksum):
        raise ValueError("manifest scalar oracle is not finite")
    tolerance = 64.0 * 2.0 ** -52 * max(1.0, abs(expected_checksum))
    for row_index, row in enumerate(rows):
        result = row.get("result")
        if row.get("returncode") != 0 or result is None:
            raise ValueError(f"{raw_path.name}: failed process retained")
        if result["mode"] != row["mode"] or result["steps"] != manifest["steps"]:
            raise ValueError(f"{raw_path.name}: result identity mismatch")
        if result["observed_cpu"] != manifest["cpu"]:
            raise ValueError(f"{raw_path.name}: CPU placement mismatch")
        if result["main_ns"] <= 0 or result["warmup_ns"] < 0 or not math.isfinite(result["checksum"]):
            raise ValueError(f"{raw_path.name}: invalid result values")
        if parse_result_output(row["stdout"]) != result:
            raise ValueError(f"{raw_path.name}: parsed stdout differs from retained result")
        if parse_perf_output(row["stderr"]) != row["perf"]:
            raise ValueError(f"{raw_path.name}: parsed perf stderr differs from retained counters")
        expected_delta = {
            key: row["cpu_stat_after"][key] - row["cpu_stat_before"][key]
            for key in row["cpu_stat_before"]
        }
        if row["cpu_stat_delta"] != expected_delta or any(value < 0 for value in expected_delta.values()):
            raise ValueError(f"{raw_path.name}: CPU-stat delta is inconsistent")
        checksums.append(result["checksum"])
        if abs(result["checksum"] - expected_checksum) > tolerance:
            raise ValueError(f"{raw_path.name}: checksum differs from scalar oracle")
        block = row_index // 4
        position = row_index % 4 + 1
        template = expected_templates[block]
        expected_label = template[position - 1]
        expected_mode = summary["baseline_mode"] if expected_label == "A" else summary["candidate_mode"]
        expected_command = [
            "perf", "stat", "--no-big-num", "-x,", "-e", expected_events,
            "--", "taskset", "-c", str(manifest["cpu"]), manifest["binary"],
            expected_mode, str(manifest["steps"]), str(manifest["warmup_steps"]),
        ]
        if (row["comparison"], row["block"], row["position"], row["template"], row["label"], row["mode"]) != (
            summary["name"], block, position, template, expected_label, expected_mode
        ):
            raise ValueError(f"{raw_path.name}: row {row_index} violates the fixed schedule")
        if row["aa_identical_mode"] != summary["aa_identical_mode"]:
            raise ValueError(f"{raw_path.name}: row {row_index} has the wrong A/A flag")
        if row["command"] != expected_command or row["probe_environment"] != expected_environment:
            raise ValueError(f"{raw_path.name}: row {row_index} command or environment drifted")
        if row["timeout_seconds"] != manifest["process_timeout_seconds"] or row.get("timed_out"):
            raise ValueError(f"{raw_path.name}: row {row_index} timed out or changed timeout")
        if row["binary_sha256_before"] != binary_digest or row["binary_sha256_after"] != binary_digest:
            raise ValueError(f"{raw_path.name}: row {row_index} binary identity changed")
        cycles = row.get("perf", {}).get("cycles", {})
        if not valid_counter(cycles):
            raise ValueError(f"{raw_path.name}: cycles missing or multiplexed")
        if architecture == "x86_64":
            reference = row.get("perf", {}).get("ref-cycles", {})
            if not valid_counter(reference):
                raise ValueError(f"{raw_path.name}: reference cycles missing or multiplexed")
            if cycles.get("time_running_ns") != reference.get("time_running_ns"):
                raise ValueError(f"{raw_path.name}: grouped counters have different running time")
            witness = cycles["value"] / reference["value"]
            if not math.isfinite(witness) or witness <= 0.0:
                raise ValueError(f"{raw_path.name}: cycle/reference-cycle ratio is invalid")
        by_block.setdefault(row["block"], []).append(row)

    if max(checksums) - min(checksums) > tolerance:
        raise ValueError(f"{raw_path.name}: vector paths disagree with the scalar oracle")

    log_contrasts = []
    contrast_rows = []
    for block in range(requested):
        block_rows = sorted(by_block.get(block, []), key=lambda row: row["position"])
        if len(block_rows) != 4:
            raise ValueError(f"{raw_path.name}: incomplete block {block}")
        template = block_rows[0]["template"]
        if template not in {"ABBA", "BAAB"} or "".join(row["label"] for row in block_rows) != template:
            raise ValueError(f"{raw_path.name}: invalid template in block {block}")
        if any(row["template"] != template for row in block_rows):
            raise ValueError(f"{raw_path.name}: mixed template in block {block}")
        logs = [math.log(row["result"]["main_ns"]) for row in block_rows]
        if template == "ABBA":
            contrast = ((logs[1] + logs[2]) - (logs[0] + logs[3])) / 2.0
        else:
            contrast = ((logs[0] + logs[3]) - (logs[1] + logs[2])) / 2.0
        log_contrasts.append(contrast)
        contrast_rows.append({
            "comparison": summary["name"],
            "block": block,
            "template": template,
            "log_ratio": contrast,
            "ratio": math.exp(contrast),
        })

    mean_log = statistics.mean(log_contrasts)
    standard_deviation = statistics.stdev(log_contrasts)
    half_width = T_CRITICAL_975[len(log_contrasts) - 1] * standard_deviation / math.sqrt(len(log_contrasts))
    recomputed = {
        "complete_blocks": len(log_contrasts),
        "geomean_ratio": math.exp(mean_log),
        "log_contrast_mean": mean_log,
        "log_contrast_sd": standard_deviation,
        "multiplicative_sd": math.exp(standard_deviation),
        "ci95_ratio_low": math.exp(mean_log - half_width),
        "ci95_ratio_high": math.exp(mean_log + half_width),
        "ci_method": "two-sided paired-t interval over complete-block log contrasts",
    }
    if summary["aa_identical_mode"] and not 0.90 <= recomputed["geomean_ratio"] <= 1.10:
        raise ValueError(f"{raw_path.name}: A/A point estimate is outside [0.90, 1.10]")
    retained = summary["contrast"]
    if set(retained) != set(recomputed):
        raise ValueError(f"{raw_path.name}: contrast summary fields differ")
    for key, value in recomputed.items():
        if isinstance(value, str):
            if not isinstance(retained[key], str) or retained[key] != value:
                raise ValueError(f"{raw_path.name}:{key}: method label differs")
        elif isinstance(value, int):
            if isinstance(retained[key], bool) or not isinstance(retained[key], int):
                raise ValueError(f"{raw_path.name}:{key}: integer field has the wrong type")
            if retained[key] != value:
                raise ValueError(f"{raw_path.name}:{key}: integer field differs")
        else:
            if isinstance(retained[key], bool) or not isinstance(retained[key], (int, float)):
                raise ValueError(f"{raw_path.name}:{key}: numeric field has the wrong type")
            if not math.isfinite(float(retained[key])):
                raise ValueError(f"{raw_path.name}:{key}: numeric field is not finite")
            close(float(retained[key]), float(value), f"{raw_path.name}:{key}")
    with raw_path.with_name(raw_path.name.replace("-raw.jsonl", "-contrasts.csv")).open(
        newline="", encoding="utf-8"
    ) as handle:
        retained_contrasts = list(csv.DictReader(handle))
    if len(retained_contrasts) != len(contrast_rows):
        raise ValueError(f"{raw_path.name}: contrast CSV has the wrong row count")
    for retained_row, expected_row in zip(retained_contrasts, contrast_rows):
        for key in ("comparison", "template"):
            if retained_row[key] != str(expected_row[key]):
                raise ValueError(f"{raw_path.name}: contrast CSV {key} differs")
        if int(retained_row["block"]) != expected_row["block"]:
            raise ValueError(f"{raw_path.name}: contrast CSV block differs")
        close(float(retained_row["log_ratio"]), expected_row["log_ratio"], f"{raw_path.name}:csv-log")
        close(float(retained_row["ratio"]), expected_row["ratio"], f"{raw_path.name}:csv-ratio")
    baseline_metrics = recompute_metrics(rows, summary["baseline_mode"], manifest["cpu"])
    candidate_metrics = recompute_metrics(rows, summary["candidate_mode"], manifest["cpu"])
    if summary["baseline_metrics"] != baseline_metrics:
        raise ValueError(f"{raw_path.name}: baseline metrics differ from raw rows")
    if summary["candidate_metrics"] != candidate_metrics:
        raise ValueError(f"{raw_path.name}: candidate metrics differ from raw rows")
    if summary["failed_processes"] != 0:
        raise ValueError(f"{raw_path.name}: summary records failed processes")
    # The independent arithmetic above can differ by one binary64 unit across
    # libm implementations. Return the retained values only after validating
    # them so the digest-bound report is byte-stable across architectures.
    return dict(retained)


def main() -> None:
    """Validate a host receipt directory and write a digest-bound report."""

    parser = argparse.ArgumentParser()
    parser.add_argument("receipt_dir", type=Path)
    parser.add_argument("--expected-label", required=True)
    parser.add_argument("--expected-resolved-host", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.receipt_dir.resolve()
    if args.output.exists():
        raise ValueError(f"validation output already exists: {args.output}")

    for relative in REQUIRED:
        if not (root / relative).is_file():
            raise ValueError(f"missing required receipt: {relative}")
    if (root / "source-manifest.diff").read_bytes():
        raise ValueError("source manifest changed during the run")
    if (root / "source-manifest-before.sha256").read_bytes() != (root / "source-manifest-after.sha256").read_bytes():
        raise ValueError("before and after source manifests differ")

    host = key_values(root / "host.txt")
    missing_fields = sorted(CRITICAL_HOST_KEYS - host.keys())
    if missing_fields:
        raise ValueError(f"host receipt lacks critical fields: {', '.join(missing_fields)}")
    host_text = (root / "host.txt").read_text(encoding="utf-8")
    missing_sections = [marker for marker in CRITICAL_HOST_SECTIONS if marker not in host_text]
    if missing_sections:
        raise ValueError(f"host receipt lacks tool sections: {', '.join(missing_sections)}")
    architecture = host.get("architecture")
    target = host.get("ssh_target_label")
    if target == "xxl" and architecture != "x86_64":
        raise ValueError("xxl did not report x86_64")
    if target == "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com" and architecture not in {"aarch64", "arm64"}:
        raise ValueError("authorized Arm host did not report AArch64")
    if target not in {"xxl", "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com"}:
        raise ValueError("unexpected SSH target label")
    if target != args.expected_label or host.get("ssh_resolved_hostname") != args.expected_resolved_host:
        raise ValueError("host receipt differs from the caller's expected target")
    if host.get("source_commit") != args.expected_source_commit.lower():
        raise ValueError("host receipt differs from the expected source commit")
    if host.get("source_archive_sha256") != args.expected_archive_sha256.lower():
        raise ValueError("host receipt differs from the expected archive digest")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_source_commit.lower()):
        raise ValueError("expected source commit must contain 40 hexadecimal digits")
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_archive_sha256.lower()):
        raise ValueError("expected archive digest must contain 64 hexadecimal digits")
    if host.get("ssh_resolved_hostname") != host.get("runtime_hostname"):
        raise ValueError("resolved and runtime hostnames differ")
    verify_source_archive(root, host)
    if json.loads((root / "protocol-self-test.json").read_text(encoding="utf-8")).get("status") != "pass":
        raise ValueError("forced-timeout protocol self-test did not pass")

    build_text = (root / "build.txt").read_text(encoding="utf-8")
    expected_build = "COMMAND=gcc -O3 -std=c11 -Wall -Wextra -Werror -fno-tree-vectorize -ffp-contract=fast -fno-omit-frame-pointer width_bench.c -lm -o width_bench\nBUILD_STATUS=pass\n"
    if build_text != expected_build:
        raise ValueError("C build receipt differs from the sealed command")
    correctness_text = (root / "correctness.txt").read_text(encoding="utf-8")
    if "CORRECTNESS_STATUS=pass\n" not in correctness_text:
        raise ValueError("Rust correctness receipt lacks its success marker")

    expected_binary_digest = (root / "binary.sha256").read_text(encoding="utf-8").strip().split()[0]
    actual_binary_digest = sha256(root / "binary/width_bench")
    if expected_binary_digest != actual_binary_digest:
        raise ValueError("binary digest mismatch")

    codegen = json.loads((root / "codegen/codegen-check.json").read_text(encoding="utf-8"))
    if codegen.get("status") != "pass" or codegen.get("architecture") != architecture:
        raise ValueError("generated-code gate did not pass for this architecture")
    codegen_script = Path(__file__).resolve().parent / "codegen_checks.py"
    checked = subprocess.run(
        ["python3", "-I", "-B", str(codegen_script), "--codegen-dir", str(root / "codegen"),
         "--architecture", architecture],
        text=True, capture_output=True, check=True,
        env={"LANG": "C", "LC_ALL": "C", "PATH": os.defpath, "TZ": "UTC"},
    )
    if json.loads(checked.stdout) != codegen:
        raise ValueError("retained codegen result differs from independent recheck")
    if architecture == "x86_64":
        for relative in ("codegen/kernel_v256.asm", "codegen/kernel_v512.asm"):
            if not (root / relative).is_file():
                raise ValueError(f"missing x86 code generation: {relative}")
    expected_codegen_files = ["all.asm", "kernel_scalar.asm", "kernel_v128.asm", "symbols.txt"]
    if architecture == "x86_64":
        expected_codegen_files.extend(("kernel_v256.asm", "kernel_v512.asm"))
    codegen_digests = parse_sha256_manifest(root / "codegen/sha256sums.txt")
    if set(codegen_digests) != set(expected_codegen_files):
        raise ValueError("codegen SHA-256 manifest has the wrong file set")
    for name in expected_codegen_files:
        if codegen_digests[name] != sha256(root / "codegen" / name):
            raise ValueError(f"codegen digest mismatch for {name}")

    manifest = json.loads((root / "experiment/manifest.json").read_text(encoding="utf-8"))
    if manifest["machine"] != architecture:
        raise ValueError("experiment manifest architecture differs from the host receipt")
    if manifest["hostname"] != host.get("runtime_hostname"):
        raise ValueError("experiment manifest hostname differs from the host receipt")
    if (
        manifest["cpu"], manifest["steps"], manifest["warmup_steps"]
    ) != (
        int(host.get("cpu", "-1")),
        int(host.get("steps", "-1")),
        int(host.get("warmup_steps", "-1")),
    ):
        raise ValueError("experiment inputs differ from the host receipt")
    if (
        manifest["binary_sha256"] != actual_binary_digest
        or manifest["binary_sha256_start"] != actual_binary_digest
    ):
        raise ValueError("experiment manifest binary identity differs from the retained binary")
    expected_correctness_command = [manifest["binary"], "--check", str(manifest["steps"])]
    if manifest.get("correctness_command") != expected_correctness_command:
        raise ValueError("same-step correctness command differs from the fixed workload")
    same_step_rows = [
        line.split("\t") for line in manifest["correctness_stdout"].splitlines()
        if line.startswith("CHECK\t")
    ]
    if not same_step_rows or any(len(row) != 5 for row in same_step_rows):
        raise ValueError("same-step correctness output is malformed")
    try:
        same_step_numbers = [tuple(float(value) for value in row[2:5]) for row in same_step_rows]
    except ValueError as error:
        raise ValueError("same-step correctness output contains a non-number") from error
    if any(not all(math.isfinite(value) for value in numbers) for numbers in same_step_numbers):
        raise ValueError("same-step correctness output contains a non-finite number")
    scalar_same_step = [row for row in same_step_rows if row[1] == "scalar"]
    if len(scalar_same_step) != 1 or float(scalar_same_step[0][2]) != manifest["expected_checksum"]:
        raise ValueError("manifest checksum is not the same-step scalar oracle")
    if manifest["blocks"] != 8 or manifest["aa_blocks"] != 8:
        raise ValueError("publication schedule requires eight treatment and eight A/A blocks")
    if (manifest["steps"], manifest["warmup_steps"], manifest["seed"], manifest["washout_seconds"]) != (
        20_000_000, 2_000_000, 20_260_824, 0.2
    ):
        raise ValueError("experiment settings differ from the publication contract")
    if manifest["probe_environment"] != {"LANG": "C", "LC_ALL": "C", "PATH": os.defpath, "TZ": "UTC"}:
        raise ValueError("probe environment is not the sealed allowlist")
    if (root / "experiment/binary-final.sha256").read_text(encoding="utf-8").strip() != actual_binary_digest:
        raise ValueError("final schedule binary digest mismatch")
    expected_modes = ["scalar", "v128", "v256", "v512"] if architecture == "x86_64" else ["scalar", "v128"]
    if manifest["modes"] != expected_modes or (root / "modes.txt").read_text(encoding="utf-8").split() != expected_modes:
        raise ValueError("supported mode set differs from the architecture contract")
    if manifest["correctness_stderr"] or [row[1] for row in same_step_rows] != expected_modes:
        raise ValueError("same-step correctness output does not cover the exact mode set")
    if any(float(row[3]) != manifest["expected_checksum"] for row in same_step_rows):
        raise ValueError("same-step correctness rows do not share the scalar reference")
    if any(float(row[4]) > 64.0 * 2.0 ** -52 * max(1.0, abs(float(row[3]))) for row in same_step_rows):
        raise ValueError("same-step correctness row exceeds its scalar-oracle tolerance")
    check_rows = [line.split("\t") for line in correctness_text.splitlines() if line.startswith("CHECK\t")]
    if [row[1] for row in check_rows] != expected_modes:
        raise ValueError("correctness receipt does not cover the exact mode set")
    try:
        check_numbers = [tuple(float(value) for value in row[2:5]) for row in check_rows]
    except ValueError as error:
        raise ValueError("correctness receipt contains a non-number") from error
    if any(not all(math.isfinite(value) for value in numbers) for numbers in check_numbers):
        raise ValueError("correctness receipt contains a non-finite number")
    if any(float(row[4]) > 64.0 * 2.0 ** -52 * max(1.0, abs(float(row[3]))) for row in check_rows):
        raise ValueError("a correctness row exceeds its scalar-oracle tolerance")

    summaries = json.loads((root / "experiment/all-summaries.json").read_text(encoding="utf-8"))
    expected_order = (["scalar-vs-v128", "scalar-vs-v256", "scalar-vs-v512",
                       "v128-vs-v256", "v256-vs-v512", "aa-v256"]
                      if architecture == "x86_64" else ["scalar-vs-v128", "aa-v128"])
    if [summary["name"] for summary in summaries] != expected_order:
        raise ValueError("comparison set does not match the architecture contract")
    expected_identities = (
        [
            ("scalar", "v128", False, manifest["seed"]),
            ("scalar", "v256", False, manifest["seed"] + 1),
            ("scalar", "v512", False, manifest["seed"] + 2),
            ("v128", "v256", False, manifest["seed"] + 3),
            ("v256", "v512", False, manifest["seed"] + 4),
            ("v256", "v256", True, manifest["seed"] + 100),
        ]
        if architecture == "x86_64"
        else [
            ("scalar", "v128", False, manifest["seed"]),
            ("v128", "v128", True, manifest["seed"] + 100),
        ]
    )
    if len(summaries) != len(expected_identities):
        raise ValueError("comparison identities have the wrong row count")
    for summary, (baseline, candidate, aa, seed) in zip(summaries, expected_identities):
        expected_blocks = manifest["aa_blocks"] if aa else manifest["blocks"]
        if (
            summary["baseline_mode"], summary["candidate_mode"],
            summary["aa_identical_mode"], summary["seed"], summary["requested_blocks"]
        ) != (baseline, candidate, aa, seed, expected_blocks):
            raise ValueError(f"{summary['name']}: mode, A/A, seed, or block identity differs")

    validated_contrasts = {}
    for summary in summaries:
        name = summary["name"]
        retained = json.loads((root / f"experiment/{name}-summary.json").read_text(encoding="utf-8"))
        if retained != summary:
            raise ValueError(f"{name}: individual and aggregate summaries differ")
        validated_contrasts[name] = recompute(
            root / f"experiment/{name}-raw.jsonl", summary, manifest, architecture
        )

    digest_paths = [root / relative for relative in REQUIRED]
    if architecture == "x86_64":
        digest_paths.extend((root / "codegen/kernel_v256.asm", root / "codegen/kernel_v512.asm"))
    for summary in summaries:
        digest_paths.extend((
            root / f"experiment/{summary['name']}-raw.jsonl",
            root / f"experiment/{summary['name']}-summary.json",
            root / f"experiment/{summary['name']}-contrasts.csv",
        ))
    report = {
        "status": "pass",
        "architecture": architecture,
        "ssh_target_label": target,
        "binary_sha256": actual_binary_digest,
        "validated_contrasts": validated_contrasts,
        "input_sha256": {
            str(path.relative_to(root)): sha256(path) for path in sorted(digest_paths)
        },
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
