#!/usr/bin/env python3
"""Run the frozen Topic 37 fresh-process compression experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from typing import Any


CODECS = ("identity", "lz4", "zstd")
CORPORA = ("structured", "random")
SHAPES = ("independent", "batch")
PHASES = ("encode", "decode")
BLOCKS = 12
AA_BLOCKS = 4
STARTUP_PER_PHASE = 12
SEED = 370037
TARGET_MS = 200
PROCESS_TIMEOUT_SECONDS = 1_800
RECORD_COUNT = 1_024
RECORD_BYTES = 256
T_CRITICAL = {12: 2.200985160082949, 4: 3.182446305284263}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--validator", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--blocks", type=int, default=BLOCKS)
    parser.add_argument("--aa-blocks", type=int, default=AA_BLOCKS)
    parser.add_argument("--startup-per-phase", type=int, default=STARTUP_PER_PHASE)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--target-ms", type=int, default=TARGET_MS)
    args = parser.parse_args()
    frozen = (
        ("--blocks", args.blocks, BLOCKS),
        ("--aa-blocks", args.aa_blocks, AA_BLOCKS),
        ("--startup-per-phase", args.startup_per_phase, STARTUP_PER_PHASE),
        ("--seed", args.seed, SEED),
        ("--target-ms", args.target_ms, TARGET_MS),
    )
    for name, observed, expected in frozen:
        if observed != expected:
            parser.error(f"{name} must be {expected} for the frozen design")
    return args


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json(path: Path, value: object) -> None:
    write_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def append_jsonl(stream: Any, value: object) -> None:
    stream.write(json.dumps(value, sort_keys=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def effective_child_environment() -> dict[str, str]:
    environment = {
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TZ": "UTC",
    }
    if value := os.environ.get("LD_LIBRARY_PATH"):
        environment["LD_LIBRARY_PATH"] = value
    return environment


def first_allowed_cpu() -> tuple[int, list[int]]:
    if not hasattr(os, "sched_getaffinity") or not hasattr(os, "sched_setaffinity"):
        raise RuntimeError("Linux CPU-affinity APIs are required")
    allowed = sorted(os.sched_getaffinity(0))
    if not allowed:
        raise RuntimeError("the process affinity mask is empty")
    return allowed[0], allowed


def child_affinity(cpu: int):
    def pin() -> None:
        os.sched_setaffinity(0, {cpu})

    return pin


def run_command(
    command: list[str], cpu: int, cwd: Path, environment: dict[str, str]
) -> dict[str, object]:
    started = time.monotonic_ns()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=child_affinity(cpu),
        )
    except Exception as error:
        return {
            "child_pid": 0,
            "exit_code": 126,
            "external_wall_ns": time.monotonic_ns() - started,
            "spawn_error": f"{type(error).__name__}: {error}",
            "stderr": b"",
            "stdout": b"",
            "timed_out": False,
        }
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=PROCESS_TIMEOUT_SECONDS)
        exit_code = process.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
        exit_code = 124
    return {
        "child_pid": process.pid,
        "exit_code": exit_code,
        "external_wall_ns": time.monotonic_ns() - started,
        "spawn_error": None,
        "stderr": stderr,
        "stdout": stdout,
        "timed_out": timed_out,
    }


def public_receipt(
    result: dict[str, object],
    command: list[str],
    cpu: int,
    cwd: Path,
    environment_sha256: str,
) -> dict[str, object]:
    stdout = bytes(result["stdout"])
    stderr = bytes(result["stderr"])
    return {
        "argv": command,
        "child_pid": result["child_pid"],
        "cwd": str(cwd),
        "effective_environment_sha256": environment_sha256,
        "exit_code": result["exit_code"],
        "external_wall_ns": result["external_wall_ns"],
        "pinned_cpu": cpu,
        "spawn_error": result["spawn_error"],
        "stderr_bytes": len(stderr),
        "stderr_sha256": sha256_bytes(stderr),
        "stdout_bytes": len(stdout),
        "stdout_sha256": sha256_bytes(stdout),
        "timed_out": result["timed_out"],
    }


def calibration(
    binary: Path,
    output: Path,
    cpu: int,
    cwd: Path,
    environment: dict[str, str],
    environment_sha256: str,
) -> dict[tuple[str, str, str, str], int]:
    repetitions: dict[tuple[str, str, str, str], int] = {}
    attempts_path = output / "calibration_attempts.jsonl"
    with attempts_path.open("x", encoding="utf-8") as attempts:
        for codec in CODECS:
            for corpus in CORPORA:
                for shape in SHAPES:
                    for phase in PHASES:
                        command = [
                            str(binary),
                            "calibrate",
                            codec,
                            corpus,
                            shape,
                            phase,
                            str(TARGET_MS),
                        ]
                        result = run_command(command, cpu, cwd, environment)
                        stdout = bytes(result["stdout"])
                        stderr = bytes(result["stderr"])
                        receipt = {
                            "codec": codec,
                            "corpus": corpus,
                            "phase": phase,
                            "shape": shape,
                            **public_receipt(
                                result, command, cpu, cwd, environment_sha256
                            ),
                            "stderr": stderr.decode(errors="backslashreplace"),
                            "stdout": stdout.decode(errors="backslashreplace"),
                        }
                        append_jsonl(attempts, receipt)
                        if (
                            result["exit_code"] != 0
                            or result["timed_out"]
                            or result["spawn_error"]
                            or stderr
                        ):
                            raise RuntimeError(
                                f"calibration failed for {codec}/{corpus}/{shape}/{phase}"
                            )
                        lines = stdout.decode().splitlines()
                        if len(lines) != 1 or not lines[0].startswith("reps="):
                            raise RuntimeError("calibration did not emit exactly one reps line")
                        value = int(lines[0].split("=", 1)[1])
                        if value < 1:
                            raise RuntimeError("calibration returned a non-positive count")
                        repetitions[(codec, corpus, shape, phase)] = value

    path = output / "calibration.tsv"
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(("codec", "corpus", "shape", "phase", "reps"))
        for codec in CODECS:
            for corpus in CORPORA:
                for shape in SHAPES:
                    for phase in PHASES:
                        writer.writerow(
                            (
                                codec,
                                corpus,
                                shape,
                                phase,
                                repetitions[(codec, corpus, shape, phase)],
                            )
                        )
        stream.flush()
        os.fsync(stream.fileno())
    return repetitions


def make_schedule() -> list[dict[str, object]]:
    rng = random.Random(SEED)
    templates = list(
        itertools.product(itertools.permutations(CODECS), itertools.permutations(SHAPES))
    )
    rng.shuffle(templates)
    corpus_orders = [CORPORA] * (BLOCKS // 2) + [tuple(reversed(CORPORA))] * (BLOCKS // 2)
    rng.shuffle(corpus_orders)
    if len(templates) != len(corpus_orders):
        raise RuntimeError("frozen template and corpus-order counts differ")
    schedule: list[dict[str, object]] = []
    for block, ((codec_order, shape_order), corpus_order) in enumerate(
        zip(templates, corpus_orders)
    ):
        for corpus_period, corpus in enumerate(corpus_order, start=1):
            for shape_period, shape in enumerate(shape_order, start=1):
                for codec_period, codec in enumerate(codec_order, start=1):
                    schedule.append(
                        {
                            "block": block,
                            "codec": codec,
                            "codec_order": ",".join(codec_order),
                            "codec_period": codec_period,
                            "corpus": corpus,
                            "corpus_order": ",".join(corpus_order),
                            "corpus_period": corpus_period,
                            "family": "codec-grid",
                            "label": codec,
                            "sequence": len(schedule),
                            "shape": shape,
                            "shape_order": ",".join(shape_order),
                            "shape_period": shape_period,
                        }
                    )

    for corpus in CORPORA:
        for shape in SHAPES:
            patterns = ["AB", "AB", "BA", "BA"]
            rng.shuffle(patterns)
            for block, pattern in enumerate(patterns):
                for period, label in enumerate(pattern, start=1):
                    schedule.append(
                        {
                            "block": block,
                            "codec": "identity",
                            "corpus": corpus,
                            "family": "identity-AA",
                            "label": label,
                            "period": period,
                            "sequence": len(schedule),
                            "shape": shape,
                            "template": pattern,
                        }
                    )
    return schedule


def startup_schedule() -> list[dict[str, object]]:
    schedule = []
    for phase in ("before", "after"):
        for index in range(STARTUP_PER_PHASE):
            schedule.append(
                {"index": index, "phase": phase, "sequence": len(schedule)}
            )
    return schedule


def execute_startup_phase(
    phase: str,
    binary: Path,
    output: Path,
    cpu: int,
    cwd: Path,
    environment: dict[str, str],
    environment_sha256: str,
    seen_pids: set[int],
) -> list[dict[str, object]]:
    root = output / "startup_attempts"
    records = []
    offset = 0 if phase == "before" else STARTUP_PER_PHASE
    for index in range(STARTUP_PER_PHASE):
        sequence = offset + index
        attempt = root / f"{sequence:04d}"
        attempt.mkdir()
        command = [str(binary), "startup"]
        result = run_command(command, cpu, cwd, environment)
        stdout = bytes(result["stdout"])
        stderr = bytes(result["stderr"])
        write_bytes(attempt / "stdout.txt", stdout)
        write_bytes(attempt / "stderr.txt", stderr)
        record = {
            "index": index,
            "phase": phase,
            "sequence": sequence,
            **public_receipt(result, command, cpu, cwd, environment_sha256),
        }
        write_json(attempt / "receipt.json", record)
        records.append(record)
        if (
            result["exit_code"] != 0
            or result["timed_out"]
            or result["spawn_error"]
            or stderr
            or stdout != b"CHECK=PASS\n"
        ):
            raise RuntimeError(f"startup control {phase}/{index} failed")
        pid = int(record["child_pid"])
        if pid in seen_pids:
            raise RuntimeError(f"fresh-process PID was reused: {pid}")
        seen_pids.add(pid)
    return records


def execute_schedule(
    binary: Path,
    output: Path,
    schedule: list[dict[str, object]],
    repetitions: dict[tuple[str, str, str, str], int],
    cpu: int,
    cwd: Path,
    environment: dict[str, str],
    environment_sha256: str,
    seen_pids: set[int],
) -> list[dict[str, object]]:
    attempts_root = output / "attempts"
    calibration_bytes = (output / "calibration.tsv").read_bytes()
    rows = []
    with (output / "processes.jsonl").open("x", encoding="utf-8") as processes, (
        output / "raw_rows.jsonl"
    ).open("x", encoding="utf-8") as raw_rows:
        for item in schedule:
            sequence = int(item["sequence"])
            attempt = attempts_root / f"{sequence:04d}"
            attempt.mkdir()
            calibration_path = attempt / "calibration.tsv"
            write_bytes(calibration_path, calibration_bytes)
            codec = str(item["codec"])
            corpus = str(item["corpus"])
            shape = str(item["shape"])
            command = [
                str(binary),
                "process",
                codec,
                corpus,
                shape,
                str(calibration_path),
            ]
            result = run_command(command, cpu, cwd, environment)
            stdout = bytes(result["stdout"])
            stderr = bytes(result["stderr"])
            write_bytes(attempt / "stdout.jsonl", stdout)
            write_bytes(attempt / "stderr.txt", stderr)
            process_record = {
                **item,
                **public_receipt(result, command, cpu, cwd, environment_sha256),
                "pid": result["child_pid"],
            }
            append_jsonl(processes, process_record)
            if (
                result["exit_code"] != 0
                or result["timed_out"]
                or result["spawn_error"]
                or stderr
            ):
                raise RuntimeError(f"process {sequence} failed; receipt retained")
            pid = int(process_record["pid"])
            if pid in seen_pids:
                raise RuntimeError(f"fresh-process PID was reused: {pid}")
            seen_pids.add(pid)
            lines = stdout.decode().splitlines()
            if len(lines) != 1:
                raise RuntimeError(f"process {sequence} emitted {len(lines)} rows")
            row = json.loads(lines[0])
            if (
                row.get("pid") != pid
                or row.get("codec") != codec
                or row.get("corpus") != corpus
                or row.get("shape") != shape
            ):
                raise RuntimeError(f"process {sequence} misreported its identity")
            if (
                int(row["cpu_before"]) != cpu
                or int(row["cpu_after"]) != cpu
                or int(row["affinity_count_before"]) != 1
                or int(row["affinity_count_after"]) != 1
            ):
                raise RuntimeError(f"process {sequence} escaped pinned affinity")
            if int(row["encode_reps"]) != repetitions[(codec, corpus, shape, "encode")]:
                raise RuntimeError(f"process {sequence} changed encode calibration")
            if int(row["decode_reps"]) != repetitions[(codec, corpus, shape, "decode")]:
                raise RuntimeError(f"process {sequence} changed decode calibration")
            enriched = {**row, **item}
            append_jsonl(raw_rows, enriched)
            rows.append(enriched)
    return rows


def contrast_summary(
    name: str,
    direction: str,
    contrasts: list[float],
    identity: dict[str, object],
    interpretation: str,
) -> dict[str, object]:
    count = len(contrasts)
    mean_log = statistics.fmean(contrasts)
    sample_sd = statistics.stdev(contrasts)
    half_width = T_CRITICAL[count] * sample_sd / math.sqrt(count)
    return {
        **identity,
        "contrast": name,
        "geometric_mean_ratio": math.exp(mean_log),
        "interval_kind": "working-model-marginal-two-sided-95%-t-on-mean-log-ratio",
        "interval_multiplicity": "no multiplicity correction across reported cells",
        "interval_assumptions": (
            "complete-block log contrasts are independent and approximately normal; "
            "these assumptions are not established by this sequential shared-host run"
        ),
        "interpretation": interpretation,
        "log_contrasts": contrasts,
        "mean_log_ratio": mean_log,
        "n_complete_blocks": count,
        "ratio_direction": direction,
        "ratio_interval_high": math.exp(mean_log + half_width),
        "ratio_interval_low": math.exp(mean_log - half_width),
        "sample_sd_log_ratio": sample_sd,
    }


def metric(row: dict[str, object], phase: str) -> float:
    return float(row[f"{phase}_ns_per_input_byte"])


def analyse_codec_grid(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    selected = [row for row in rows if row["family"] == "codec-grid"]
    for corpus in CORPORA:
        for shape in SHAPES:
            for phase in PHASES:
                cells = [
                    row
                    for row in selected
                    if row["corpus"] == corpus and row["shape"] == shape
                ]
                by_block = {
                    block: {
                        str(row["codec"]): row
                        for row in cells
                        if int(row["block"]) == block
                    }
                    for block in range(BLOCKS)
                }
                for numerator, denominator in (
                    ("lz4", "identity"),
                    ("zstd", "identity"),
                    ("zstd", "lz4"),
                ):
                    contrasts = [
                        math.log(metric(by_block[block][numerator], phase))
                        - math.log(metric(by_block[block][denominator], phase))
                        for block in range(BLOCKS)
                    ]
                    result.append(
                        contrast_summary(
                            "codec-time",
                            f"{numerator}/{denominator}",
                            contrasts,
                            {"corpus": corpus, "phase": phase, "shape": shape},
                            "ratio below one means the numerator used less timed CPU-path time per input byte",
                        )
                    )

    for codec in CODECS:
        for corpus in CORPORA:
            for phase in PHASES:
                by_block = {
                    block: {
                        str(row["shape"]): row
                        for row in selected
                        if int(row["block"]) == block
                        and row["codec"] == codec
                        and row["corpus"] == corpus
                    }
                    for block in range(BLOCKS)
                }
                contrasts = [
                    math.log(metric(by_block[block]["batch"], phase))
                    - math.log(metric(by_block[block]["independent"], phase))
                    for block in range(BLOCKS)
                ]
                result.append(
                    contrast_summary(
                        "unit-shape-time",
                        "batch/independent",
                        contrasts,
                        {"codec": codec, "corpus": corpus, "phase": phase},
                        "ratio below one means one batched unit used less timed CPU-path time per input byte",
                    )
                )
    return result


def analyse_aa(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    selected = [row for row in rows if row["family"] == "identity-AA"]
    for corpus in CORPORA:
        for shape in SHAPES:
            for phase in PHASES:
                contrasts = []
                for block in range(AA_BLOCKS):
                    block_rows = [
                        row
                        for row in selected
                        if row["corpus"] == corpus
                        and row["shape"] == shape
                        and int(row["block"]) == block
                    ]
                    values = {str(row["label"]): metric(row, phase) for row in block_rows}
                    contrasts.append(math.log(values["B"]) - math.log(values["A"]))
                result.append(
                    contrast_summary(
                        "identity-AA-plumbing",
                        "label-B/label-A",
                        contrasts,
                        {"corpus": corpus, "phase": phase, "shape": shape},
                        "mechanical label, schedule, and receipt control only; not a noise floor",
                    )
                )
    return result


def storage_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    selected = [row for row in rows if row["family"] == "codec-grid"]
    for codec in CODECS:
        for corpus in CORPORA:
            for shape in SHAPES:
                cells = [
                    row
                    for row in selected
                    if row["codec"] == codec
                    and row["corpus"] == corpus
                    and row["shape"] == shape
                ]
                stable_fields = (
                    "input_bytes",
                    "candidate_payload_bytes",
                    "payload_bytes",
                    "framing_bytes",
                    "stored_bytes",
                    "compressed_units",
                    "raw_units",
                )
                values = {}
                for field in stable_fields:
                    observed = {int(row[field]) for row in cells}
                    if len(observed) != 1:
                        raise RuntimeError(f"unstable {field} for {codec}/{corpus}/{shape}")
                    values[field] = observed.pop()
                result.append(
                    {
                        "codec": codec,
                        "corpus": corpus,
                        "shape": shape,
                        **values,
                        "input_over_stored_ratio": values["input_bytes"]
                        / values["stored_bytes"],
                    }
                )
    return result


def startup_summary(records: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for phase in ("before", "after"):
        values = [
            int(record["external_wall_ns"])
            for record in records
            if record["phase"] == phase
        ]
        result.append(
            {
                "max_external_wall_ns": max(values),
                "mean_external_wall_ns": statistics.fmean(values),
                "median_external_wall_ns": statistics.median(values),
                "min_external_wall_ns": min(values),
                "n_processes": len(values),
                "phase": phase,
                "scope": "fork-exec-loader-program-stdio-exit; never subtracted from in-process timing",
            }
        )
    return result


def main() -> int:
    args = parse_args()
    binary = args.binary.resolve(strict=True)
    source = args.source.resolve(strict=True)
    validator = args.validator.resolve(strict=True)
    runner = Path(__file__).resolve(strict=True)
    output = args.output.resolve()
    cwd = Path.cwd().resolve(strict=True)
    if output.exists():
        raise RuntimeError(f"output already exists: {output}")
    output.mkdir(parents=True)
    (output / "attempts").mkdir()
    artifacts = output / "artifacts"
    artifacts.mkdir()
    (output / "startup_attempts").mkdir()

    cpu, allowed_cpus = first_allowed_cpu()
    environment = effective_child_environment()
    environment_bytes = (json.dumps(environment, indent=2, sort_keys=True) + "\n").encode()
    environment_sha256 = sha256_bytes(environment_bytes)
    write_bytes(output / "effective_environment.json", environment_bytes)
    initial_hashes = {
        "binary_sha256": sha256_file(binary),
        "probe_source_sha256": sha256_file(source),
        "runner_sha256": sha256_file(runner),
        "validator_sha256": sha256_file(validator),
    }
    retained_artifacts = {
        "binary_sha256": "artifacts/timing-binary",
        "probe_source_sha256": "artifacts/compression_probe.c",
        "runner_sha256": "artifacts/run_processes.py",
        "validator_sha256": "artifacts/validate_receipts.py",
    }
    artifact_sources = {
        "binary_sha256": binary,
        "probe_source_sha256": source,
        "runner_sha256": runner,
        "validator_sha256": validator,
    }
    for field, relative in retained_artifacts.items():
        write_bytes(output / relative, artifact_sources[field].read_bytes())
    os.chmod(output / retained_artifacts["binary_sha256"], 0o555)
    metadata = {
        **initial_hashes,
        "aa_blocks": AA_BLOCKS,
        "allowed_cpus": allowed_cpus,
        "binary": str(binary),
        "blocks": BLOCKS,
        "cwd": str(cwd),
        "design_frozen_before_execution": True,
        "effective_environment_sha256": environment_sha256,
        "interval_multiplicity": "marginal intervals; no correction across codec, corpus, shape, and phase cells",
        "interval_scope": (
            "working-model descriptive intervals only; sequential shared-host blocks do "
            "not establish independent approximately normal contrasts or future-run coverage"
        ),
        "output_root": str(output),
        "pid": os.getpid(),
        "pinned_cpu": cpu,
        "probe_source": str(source),
        "python": sys.version,
        "record_bytes": RECORD_BYTES,
        "record_count": RECORD_COUNT,
        "retained_artifacts": retained_artifacts,
        "runner": str(runner),
        "schema_version": 2,
        "seed": SEED,
        "startup_per_phase": STARTUP_PER_PHASE,
        "target_ms": TARGET_MS,
        "validator": str(validator),
    }
    write_json(output / "run_metadata.json", metadata)

    schedule = make_schedule()
    startups = startup_schedule()
    write_json(output / "schedule.json", schedule)
    write_json(output / "startup_schedule.json", startups)
    repetitions = calibration(
        binary, output, cpu, cwd, environment, environment_sha256
    )
    seen_pids: set[int] = set()
    startup_records = execute_startup_phase(
        "before",
        binary,
        output,
        cpu,
        cwd,
        environment,
        environment_sha256,
        seen_pids,
    )
    rows = execute_schedule(
        binary,
        output,
        schedule,
        repetitions,
        cpu,
        cwd,
        environment,
        environment_sha256,
        seen_pids,
    )
    startup_records.extend(
        execute_startup_phase(
            "after",
            binary,
            output,
            cpu,
            cwd,
            environment,
            environment_sha256,
            seen_pids,
        )
    )
    with (output / "startup_processes.jsonl").open("x", encoding="utf-8") as stream:
        for record in startup_records:
            append_jsonl(stream, record)

    write_json(
        output / "summary.json",
        {
            "aa_analyses": analyse_aa(rows),
            "codec_analyses": analyse_codec_grid(rows),
            "run_metadata": metadata,
            "startup": startup_summary(startup_records),
            "storage": storage_summary(rows),
        },
    )
    final_hashes = {
        "binary_sha256": sha256_file(binary),
        "probe_source_sha256": sha256_file(source),
        "runner_sha256": sha256_file(runner),
        "validator_sha256": sha256_file(validator),
    }
    write_json(output / "post_run_hashes.json", final_hashes)
    if final_hashes != initial_hashes:
        raise RuntimeError("binary, source, runner, or validator changed during execution")
    for field, relative in retained_artifacts.items():
        if sha256_file(output / relative) != initial_hashes[field]:
            raise RuntimeError(f"retained artifact changed during execution: {field}")
    print(
        f"CHECK=PASS timed_processes={len(schedule)} rows={len(rows)} "
        f"startup_processes={len(startup_records)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR={error}", file=sys.stderr)
        raise
