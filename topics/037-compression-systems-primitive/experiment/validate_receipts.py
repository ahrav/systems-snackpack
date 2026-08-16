#!/usr/bin/env python3
"""Independently validate Topic 37 schedules, process receipts, and contrasts."""

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
import sys
from typing import Any, Optional


CODECS = ("identity", "lz4", "zstd")
CORPORA = ("structured", "random")
SHAPES = ("independent", "batch")
PHASES = ("encode", "decode")
BLOCKS = 12
AA_BLOCKS = 4
STARTUP_PER_PHASE = 12
SEED = 370037
TARGET_MS = 200
RECORD_COUNT = 1_024
RECORD_BYTES = 256
UNIT_HEADER_BYTES = 13
T_CRITICAL = {12: 2.200985160082949, 4: 3.182446305284263}
CANONICAL_SCHEDULE_SHA256 = "ea16029b55127247c0538b7e2f7e7689d05cb9090081186333011aae2e1ea70b"
PUBLIC_RECEIPT_FIELDS = {
    "argv",
    "child_pid",
    "cwd",
    "effective_environment_sha256",
    "exit_code",
    "external_wall_ns",
    "pinned_cpu",
    "spawn_error",
    "stderr_bytes",
    "stderr_sha256",
    "stdout_bytes",
    "stdout_sha256",
    "timed_out",
}
CORE_FIELDS = {
    "affinity_count_after",
    "affinity_count_before",
    "black_box_checksum",
    "candidate_payload_bytes",
    "codec",
    "compressed_units",
    "corpus",
    "cpu_after",
    "cpu_before",
    "decode_elapsed_ns",
    "decode_mib_s",
    "decode_ns_per_input_byte",
    "decode_reps",
    "decoded_checksum",
    "encode_elapsed_ns",
    "encode_mib_s",
    "encode_ns_per_input_byte",
    "encode_reps",
    "encoded_checksum",
    "framing_bytes",
    "identity_kind",
    "input_bytes",
    "input_checksum",
    "lz4_declarations",
    "lz4_raw_framing",
    "lz4_version",
    "payload_bytes",
    "pid",
    "raw_units",
    "record_bytes",
    "record_count",
    "setup_ns",
    "shape",
    "stored_bytes",
    "unit_bytes",
    "units",
    "verified",
    "zstd_level",
    "zstd_version",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_special_files(root: Path) -> None:
    for directory, directories, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in directories + files:
            path = base / name
            if path.is_symlink():
                raise ValueError(f"receipt tree contains a symlink: {path}")
            if not path.is_dir() and not path.is_file():
                raise ValueError(f"receipt tree contains a special file: {path}")


def expected_schedule() -> list[dict[str, object]]:
    rng = random.Random(SEED)
    templates = list(
        itertools.product(itertools.permutations(CODECS), itertools.permutations(SHAPES))
    )
    rng.shuffle(templates)
    corpus_orders = [CORPORA] * (BLOCKS // 2) + [tuple(reversed(CORPORA))] * (BLOCKS // 2)
    rng.shuffle(corpus_orders)
    if len(templates) != len(corpus_orders):
        raise ValueError("frozen template and corpus-order counts differ")
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


def expected_startup_schedule() -> list[dict[str, object]]:
    result = []
    for phase in ("before", "after"):
        for index in range(STARTUP_PER_PHASE):
            result.append({"index": index, "phase": phase, "sequence": len(result)})
    return result


def read_calibration(path: Path) -> dict[tuple[str, str, str, str], int]:
    expected_fields = ["codec", "corpus", "shape", "phase", "reps"]
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != expected_fields:
            raise ValueError("calibration header changed")
        rows = list(reader)
    if any(
        set(row) != set(expected_fields)
        or any(value is None for value in row.values())
        for row in rows
    ):
        raise ValueError("calibration row has missing or unexpected fields")
    expected_keys = [
        (codec, corpus, shape, phase)
        for codec in CODECS
        for corpus in CORPORA
        for shape in SHAPES
        for phase in PHASES
    ]
    observed_keys = [
        (row["codec"], row["corpus"], row["shape"], row["phase"]) for row in rows
    ]
    if observed_keys != expected_keys:
        raise ValueError("calibration rows do not follow the frozen 24-cell order")
    result = {}
    for key, row in zip(expected_keys, rows):
        repetitions = int(row["reps"])
        if not 1 <= repetitions <= 0xFFFF_FFFF:
            raise ValueError(f"calibration is outside the uint32 range: {key}")
        result[key] = repetitions
    return result


def splitmix64(state: int) -> tuple[int, int]:
    mask = (1 << 64) - 1
    state = (state + 0x9E3779B97F4A7C15) & mask
    value = state
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return state, value ^ (value >> 31)


def corpora() -> dict[str, bytes]:
    pattern = b" service=checkout level=INFO route=/v1/orders status=200 tenant=acme "
    structured = bytearray(RECORD_COUNT * RECORD_BYTES)
    for record in range(RECORD_COUNT):
        start = record * RECORD_BYTES
        for index in range(RECORD_BYTES):
            structured[start + index] = pattern[index % len(pattern)]
        structured[start : start + 16] = f"{record:016x}".encode()

    random_bytes = bytearray(RECORD_COUNT * RECORD_BYTES)
    state = 0x4D595DF4D0F33173
    for offset in range(0, len(random_bytes), 8):
        state, value = splitmix64(state)
        random_bytes[offset : offset + 8] = value.to_bytes(8, "little")
    return {"structured": bytes(structured), "random": bytes(random_bytes)}


def fnv1a64(data: bytes) -> str:
    value = 14695981039346656037
    mask = (1 << 64) - 1
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & mask
    return f"{value:016x}"


def validate_calibration_attempts(
    root: Path,
    binary: str,
    cwd: str,
    environment_sha256: str,
    pinned_cpu: int,
    repetitions: dict[tuple[str, str, str, str], int],
) -> None:
    attempts = load_jsonl(root / "calibration_attempts.jsonl")
    if len(attempts) != 24:
        raise ValueError("calibration attempt count is not 24")
    if len(attempts) != len(repetitions):
        raise ValueError("calibration attempt and repetition counts differ")
    for record, key in zip(attempts, repetitions):
        codec, corpus, shape, phase = key
        if set(record) != PUBLIC_RECEIPT_FIELDS | {
            "codec",
            "corpus",
            "phase",
            "shape",
            "stderr",
            "stdout",
        }:
            raise ValueError(f"calibration receipt fields changed: {key}")
        command = [binary, "calibrate", codec, corpus, shape, phase, str(TARGET_MS)]
        if record["argv"] != command or record["cwd"] != cwd:
            raise ValueError(f"calibration command boundary changed: {key}")
        if record["effective_environment_sha256"] != environment_sha256:
            raise ValueError(f"calibration environment changed: {key}")
        if int(record["pinned_cpu"]) != pinned_cpu:
            raise ValueError(f"calibration pin changed: {key}")
        if (
            int(record["exit_code"]) != 0
            or record["timed_out"]
            or record["spawn_error"] is not None
            or record["stderr"]
            or int(record["stderr_bytes"]) != 0
        ):
            raise ValueError(f"calibration failed: {key}")
        stdout = str(record["stdout"]).encode()
        if (
            int(record["stdout_bytes"]) != len(stdout)
            or record["stdout_sha256"] != sha256_bytes(stdout)
            or record["stderr_sha256"] != sha256_bytes(b"")
        ):
            raise ValueError(f"calibration byte receipt changed: {key}")
        if stdout != f"reps={repetitions[key]}\n".encode():
            raise ValueError(f"calibration output disagrees with frozen TSV: {key}")


def verify_public_receipt(
    record: dict[str, Any],
    stdout: bytes,
    stderr: bytes,
    environment_sha256: str,
    expected_cwd: str,
    pinned_cpu: int,
) -> None:
    if (
        int(record["exit_code"]) != 0
        or record["timed_out"]
        or "spawn_error" not in record
        or record["spawn_error"] is not None
        or int(record["external_wall_ns"]) <= 0
    ):
        raise ValueError("a retained process did not succeed")
    if (
        int(record["stdout_bytes"]) != len(stdout)
        or record["stdout_sha256"] != sha256_bytes(stdout)
        or int(record["stderr_bytes"]) != len(stderr)
        or record["stderr_sha256"] != sha256_bytes(stderr)
        or stderr
    ):
        raise ValueError("a process byte receipt does not match its retained streams")
    if record["effective_environment_sha256"] != environment_sha256:
        raise ValueError("a process used a different effective environment")
    if record["cwd"] != expected_cwd or int(record["pinned_cpu"]) != pinned_cpu:
        raise ValueError("a process changed its working directory or CPU pin")
    if int(record["child_pid"]) != int(record.get("pid", record["child_pid"])):
        raise ValueError("a process PID receipt disagrees")


def validate_row(
    row: dict[str, Any],
    repetitions: dict[tuple[str, str, str, str], int],
    checksums: dict[str, str],
    pinned_cpu: int,
) -> None:
    codec = str(row["codec"])
    corpus = str(row["corpus"])
    shape = str(row["shape"])
    key = (codec, corpus, shape)
    if (codec not in CODECS) or (corpus not in CORPORA) or (shape not in SHAPES):
        raise ValueError(f"invalid row identity: {key}")
    input_bytes = RECORD_COUNT * RECORD_BYTES
    expected_units = RECORD_COUNT if shape == "independent" else 1
    expected_unit_bytes = RECORD_BYTES if shape == "independent" else input_bytes
    if (
        int(row["record_count"]) != RECORD_COUNT
        or int(row["record_bytes"]) != RECORD_BYTES
        or int(row["input_bytes"]) != input_bytes
        or int(row["units"]) != expected_units
        or int(row["unit_bytes"]) != expected_unit_bytes
        or expected_units * expected_unit_bytes != input_bytes
    ):
        raise ValueError(f"logical unit contract changed: {key}")
    if int(row["encode_reps"]) != repetitions[(*key, "encode")]:
        raise ValueError(f"encode calibration changed: {key}")
    if int(row["decode_reps"]) != repetitions[(*key, "decode")]:
        raise ValueError(f"decode calibration changed: {key}")
    for phase in PHASES:
        elapsed = int(row[f"{phase}_elapsed_ns"])
        reps = int(row[f"{phase}_reps"])
        if elapsed <= 0:
            raise ValueError(f"non-positive {phase} interval: {key}")
        ns_per_byte = elapsed / (reps * input_bytes)
        mib_s = 1_000_000_000 / ns_per_byte / 1_048_576
        if not math.isclose(
            float(row[f"{phase}_ns_per_input_byte"]), ns_per_byte, rel_tol=1e-10
        ):
            raise ValueError(f"{phase} ns/byte arithmetic changed: {key}")
        if not math.isclose(float(row[f"{phase}_mib_s"]), mib_s, rel_tol=1e-8):
            raise ValueError(f"{phase} throughput arithmetic changed: {key}")
    if (
        int(row["cpu_before"]) != pinned_cpu
        or int(row["cpu_after"]) != pinned_cpu
        or int(row["affinity_count_before"]) != 1
        or int(row["affinity_count_after"]) != 1
    ):
        raise ValueError(f"timed process escaped its pinned CPU: {key}")
    if not row["verified"] or row["input_checksum"] != checksums[corpus]:
        raise ValueError(f"input verification failed: {key}")
    if row["decoded_checksum"] != checksums[corpus]:
        raise ValueError(f"decoded bytes disagree with independent corpus: {key}")
    if (
        row["identity_kind"] != "memcpy-control"
        or row["lz4_raw_framing"]
        != "13-byte-C37U-tag-encoded_len-decoded_len"
        or row["lz4_declarations"]
        not in ("system-lz4-header", "documented-lz4-1.x-abi-shim")
        or int(row["zstd_level"]) != 1
        or not str(row["lz4_version"])
        or not str(row["zstd_version"])
    ):
        raise ValueError(f"codec contract metadata changed: {key}")
    payload = int(row["payload_bytes"])
    candidate = int(row["candidate_payload_bytes"])
    framing = int(row["framing_bytes"])
    stored = int(row["stored_bytes"])
    compressed_units = int(row["compressed_units"])
    raw_units = int(row["raw_units"])
    if (
        framing != UNIT_HEADER_BYTES * expected_units
        or stored != payload + framing
        or compressed_units + raw_units != expected_units
        or not 0 < payload <= input_bytes
        or candidate < payload
        or not 0 <= compressed_units <= expected_units
        or not 0 <= raw_units <= expected_units
        or payload > input_bytes
        or candidate <= 0
    ):
        raise ValueError(f"serialized storage accounting changed: {key}")
    if codec == "identity" and (
        candidate != input_bytes
        or payload != input_bytes
        or compressed_units != 0
        or raw_units != expected_units
    ):
        raise ValueError(f"identity memcpy control changed: {key}")
    if compressed_units == 0 and payload != input_bytes:
        raise ValueError(f"all-raw fallback does not carry all input bytes: {key}")
    if int(row["setup_ns"]) <= 0 or not str(row["encoded_checksum"]):
        raise ValueError(f"setup or encoded checksum missing: {key}")


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)


def validate_analysis_fixture() -> None:
    fixture = contrast_summary(
        "fixture",
        "two/one",
        [math.log(2.0)] * AA_BLOCKS,
        {"fixture": True},
        "constant two-to-one fixture",
    )
    if (
        not close(float(fixture["geometric_mean_ratio"]), 2.0)
        or not close(float(fixture["ratio_interval_low"]), 2.0)
        or not close(float(fixture["ratio_interval_high"]), 2.0)
        or not close(float(fixture["sample_sd_log_ratio"]), 0.0)
        or fixture["ratio_direction"] != "two/one"
    ):
        raise ValueError("synthetic contrast fixture failed")


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
                by_block = {
                    block: {
                        str(row["codec"]): row
                        for row in selected
                        if row["corpus"] == corpus
                        and row["shape"] == shape
                        and int(row["block"]) == block
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
                        if row["codec"] == codec
                        and row["corpus"] == corpus
                        and int(row["block"]) == block
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
                    values = {
                        str(row["label"]): metric(row, phase)
                        for row in selected
                        if row["corpus"] == corpus
                        and row["shape"] == shape
                        and int(row["block"]) == block
                    }
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
    fields = (
        "input_bytes",
        "candidate_payload_bytes",
        "payload_bytes",
        "framing_bytes",
        "stored_bytes",
        "compressed_units",
        "raw_units",
    )
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
                values = {}
                for field in fields:
                    observed = {int(row[field]) for row in cells}
                    if len(observed) != 1:
                        raise ValueError(f"unstable {field} for {codec}/{corpus}/{shape}")
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


def compare_json(left: Any, right: Any, path: str = "root") -> None:
    if isinstance(left, float) or isinstance(right, float):
        if not close(float(left), float(right)):
            raise ValueError(f"summary float mismatch at {path}")
    elif isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            raise ValueError(f"summary keys mismatch at {path}")
        for key in left:
            compare_json(left[key], right[key], f"{path}.{key}")
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(f"summary length mismatch at {path}")
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            compare_json(left_item, right_item, f"{path}[{index}]")
    elif left != right:
        raise ValueError(f"summary value mismatch at {path}")


def validate(root: Path, binary: Optional[Path]) -> None:
    validate_analysis_fixture()
    reject_special_files(root)
    expected_top = {
        "artifacts",
        "attempts",
        "calibration.tsv",
        "calibration_attempts.jsonl",
        "effective_environment.json",
        "post_run_hashes.json",
        "processes.jsonl",
        "raw_rows.jsonl",
        "run_metadata.json",
        "schedule.json",
        "startup_attempts",
        "startup_processes.jsonl",
        "startup_schedule.json",
        "summary.json",
    }
    if {path.name for path in root.iterdir()} != expected_top:
        raise ValueError("benchmark root has missing or unexpected receipts")

    metadata = load_json(root / "run_metadata.json")
    frozen = {
        "aa_blocks": AA_BLOCKS,
        "blocks": BLOCKS,
        "design_frozen_before_execution": True,
        "record_bytes": RECORD_BYTES,
        "record_count": RECORD_COUNT,
        "schema_version": 2,
        "seed": SEED,
        "startup_per_phase": STARTUP_PER_PHASE,
        "target_ms": TARGET_MS,
    }
    for field, value in frozen.items():
        if metadata.get(field) != value:
            raise ValueError(f"run metadata changed frozen field {field}")
    pinned_cpu = int(metadata["pinned_cpu"])
    if pinned_cpu not in [int(cpu) for cpu in metadata["allowed_cpus"]]:
        raise ValueError("pinned CPU was not in the allowed affinity set")
    if metadata["interval_multiplicity"] != (
        "marginal intervals; no correction across codec, corpus, shape, and phase cells"
    ):
        raise ValueError("interval multiplicity boundary is missing")
    if metadata["interval_scope"] != (
        "working-model descriptive intervals only; sequential shared-host blocks do "
        "not establish independent approximately normal contrasts or future-run coverage"
    ):
        raise ValueError("interval assumption boundary is missing")
    output_root = Path(str(metadata["output_root"]))
    if not output_root.is_absolute():
        raise ValueError("recorded benchmark output root is not absolute")

    environment_bytes = (root / "effective_environment.json").read_bytes()
    environment_sha256 = sha256_bytes(environment_bytes)
    environment = json.loads(environment_bytes)
    if metadata["effective_environment_sha256"] != environment_sha256:
        raise ValueError("effective environment digest mismatch")
    if not {"LC_ALL", "PATH", "TZ"}.issubset(environment) or set(environment) - {
        "LC_ALL",
        "PATH",
        "TZ",
        "LD_LIBRARY_PATH",
    }:
        raise ValueError("child environment is incomplete or contains an unexpected variable")
    if environment["LC_ALL"] != "C" or environment["TZ"] != "UTC":
        raise ValueError("child locale or time zone changed")
    if not isinstance(environment["PATH"], str) or not environment["PATH"]:
        raise ValueError("child PATH is missing")

    expected_artifacts = {
        "binary_sha256": "artifacts/timing-binary",
        "probe_source_sha256": "artifacts/compression_probe.c",
        "runner_sha256": "artifacts/run_processes.py",
        "validator_sha256": "artifacts/validate_receipts.py",
    }
    if metadata["retained_artifacts"] != expected_artifacts:
        raise ValueError("retained artifact paths changed")
    artifacts = root / "artifacts"
    if {path.name for path in artifacts.iterdir()} != {
        "timing-binary",
        "compression_probe.c",
        "run_processes.py",
        "validate_receipts.py",
    }:
        raise ValueError("retained artifact set changed")
    paths = {field: root / relative for field, relative in expected_artifacts.items()}
    post_hashes = load_json(root / "post_run_hashes.json")
    if post_hashes != {field: metadata[field] for field in expected_artifacts}:
        raise ValueError("post-run artifact hashes changed")
    for field, path in paths.items():
        if sha256_file(path) != metadata[field] or post_hashes[field] != metadata[field]:
            raise ValueError(f"pre/post/retained artifact hash mismatch: {field}")
    current_validator = Path(__file__).resolve(strict=True)
    if sha256_file(current_validator) != metadata["validator_sha256"]:
        raise ValueError("current validator differs from the retained validator")
    if binary is not None and sha256_file(binary) != metadata["binary_sha256"]:
        raise ValueError("supplied timing binary digest mismatch")

    schedule = load_json(root / "schedule.json")
    if sha256_file(root / "schedule.json") != CANONICAL_SCHEDULE_SHA256:
        raise ValueError("canonical schedule digest changed")
    expected = expected_schedule()
    if schedule != expected:
        raise ValueError("timed schedule does not match the frozen seeded schedule")
    startups = load_json(root / "startup_schedule.json")
    if startups != expected_startup_schedule():
        raise ValueError("startup schedule does not match the frozen design")
    main_schedule = [item for item in schedule if item["family"] == "codec-grid"]
    aa_schedule = [item for item in schedule if item["family"] == "identity-AA"]
    if len(main_schedule) != 144 or len(aa_schedule) != 32:
        raise ValueError("main or A/A process count changed")
    expected_cells = {
        (codec, corpus, shape)
        for codec in CODECS
        for corpus in CORPORA
        for shape in SHAPES
    }
    for block in range(BLOCKS):
        block_cells = {
            (str(item["codec"]), str(item["corpus"]), str(item["shape"]))
            for item in main_schedule
            if int(item["block"]) == block
        }
        if block_cells != expected_cells:
            raise ValueError(f"main block {block} is not a complete treatment grid")
    for corpus in CORPORA:
        for shape in SHAPES:
            cells = [
                item
                for item in aa_schedule
                if item["corpus"] == corpus and item["shape"] == shape
            ]
            templates = [
                str(cells[index * 2]["template"])
                for index in range(AA_BLOCKS)
            ]
            if (
                len(cells) != 2 * AA_BLOCKS
                or templates.count("AB") != 2
                or templates.count("BA") != 2
            ):
                raise ValueError(f"A/A schedule is incomplete for {corpus}/{shape}")
    round_orders = {
        block: {item["codec_order"] for item in main_schedule if item["block"] == block}.pop()
        for block in range(BLOCKS)
    }
    order_counts = {order: list(round_orders.values()).count(order) for order in set(round_orders.values())}
    if len(order_counts) != 6 or set(order_counts.values()) != {2}:
        raise ValueError("six codec orders were not each used twice")
    shape_first = [
        {item["shape_order"] for item in main_schedule if item["block"] == block}.pop().split(",")[0]
        for block in range(BLOCKS)
    ]
    if shape_first.count("independent") != 6 or shape_first.count("batch") != 6:
        raise ValueError("shape-first order is not balanced 6:6")

    repetitions = read_calibration(root / "calibration.tsv")
    validate_calibration_attempts(
        root,
        str(metadata["binary"]),
        str(metadata["cwd"]),
        environment_sha256,
        pinned_cpu,
        repetitions,
    )
    processes = load_jsonl(root / "processes.jsonl")
    rows = load_jsonl(root / "raw_rows.jsonl")
    if len(processes) != len(schedule) or len(rows) != len(schedule):
        raise ValueError("process, schedule, and row counts differ")
    expected_attempts = {f"{index:04d}" for index in range(len(schedule))}
    if {path.name for path in (root / "attempts").iterdir()} != expected_attempts:
        raise ValueError("timed attempt directory set changed")
    corpus_checksums = {name: fnv1a64(value) for name, value in corpora().items()}
    seen_pids: set[int] = set()
    stable: dict[tuple[str, str, str], tuple[Any, ...]] = {}
    for sequence, (item, process, row) in enumerate(
        zip(schedule, processes, rows)
    ):
        if int(item["sequence"]) != sequence or int(process["sequence"]) != sequence:
            raise ValueError("timed process sequence is not contiguous")
        for field, value in item.items():
            if process.get(field) != value or row.get(field) != value:
                raise ValueError(f"schedule field changed at {sequence}/{field}")
        if set(process) != set(item) | PUBLIC_RECEIPT_FIELDS | {"pid"}:
            raise ValueError(f"process receipt fields changed at {sequence}")
        attempt = root / "attempts" / f"{sequence:04d}"
        if {path.name for path in attempt.iterdir()} != {
            "calibration.tsv",
            "stderr.txt",
            "stdout.jsonl",
        }:
            raise ValueError(f"attempt {sequence} file set changed")
        if (attempt / "calibration.tsv").read_bytes() != (root / "calibration.tsv").read_bytes():
            raise ValueError(f"attempt {sequence} changed the frozen calibration")
        stdout = (attempt / "stdout.jsonl").read_bytes()
        stderr = (attempt / "stderr.txt").read_bytes()
        verify_public_receipt(
            process,
            stdout,
            stderr,
            environment_sha256,
            str(metadata["cwd"]),
            pinned_cpu,
        )
        recorded_attempt = output_root / "attempts" / f"{sequence:04d}"
        expected_argv = [
            str(metadata["binary"]),
            "process",
            str(item["codec"]),
            str(item["corpus"]),
            str(item["shape"]),
            str(recorded_attempt / "calibration.tsv"),
        ]
        if process["argv"] != expected_argv or process["cwd"] != metadata["cwd"]:
            raise ValueError(f"process command boundary changed at {sequence}")
        emitted = json.loads(stdout)
        if set(emitted) != CORE_FIELDS:
            raise ValueError(f"process {sequence} emitted an unexpected field set")
        if row != {**emitted, **item}:
            raise ValueError(f"aggregate row differs from attempt {sequence}")
        if int(process["external_wall_ns"]) < (
            int(row["setup_ns"])
            + int(row["encode_elapsed_ns"])
            + int(row["decode_elapsed_ns"])
        ):
            raise ValueError(f"external wall time is impossible at {sequence}")
        pid = int(process["pid"])
        if pid <= 0 or pid in seen_pids or pid != int(row["pid"]):
            raise ValueError(f"fresh process identity failed at {sequence}")
        seen_pids.add(pid)
        validate_row(row, repetitions, corpus_checksums, pinned_cpu)
        stable_key = (str(row["codec"]), str(row["corpus"]), str(row["shape"]))
        stable_values = tuple(
            row[field]
            for field in (
                "candidate_payload_bytes",
                "payload_bytes",
                "framing_bytes",
                "stored_bytes",
                "compressed_units",
                "raw_units",
                "input_checksum",
                "decoded_checksum",
                "encoded_checksum",
                "lz4_version",
                "zstd_version",
            )
        )
        if stable.setdefault(stable_key, stable_values) != stable_values:
            raise ValueError(f"stable representation metadata changed for {stable_key}")

    startup_records = load_jsonl(root / "startup_processes.jsonl")
    if len(startup_records) != 2 * STARTUP_PER_PHASE:
        raise ValueError("startup receipt count changed")
    expected_startup_attempts = {f"{index:04d}" for index in range(2 * STARTUP_PER_PHASE)}
    if {path.name for path in (root / "startup_attempts").iterdir()} != expected_startup_attempts:
        raise ValueError("startup attempt directory set changed")
    if len(startups) != len(startup_records):
        raise ValueError("startup schedule and record counts differ")
    for scheduled, record in zip(startups, startup_records):
        for field, value in scheduled.items():
            if record.get(field) != value:
                raise ValueError(f"startup schedule changed at {scheduled['sequence']}")
        if set(record) != set(scheduled) | PUBLIC_RECEIPT_FIELDS:
            raise ValueError(f"startup receipt fields changed at {scheduled['sequence']}")
        attempt = root / "startup_attempts" / f"{int(scheduled['sequence']):04d}"
        if {path.name for path in attempt.iterdir()} != {
            "receipt.json",
            "stderr.txt",
            "stdout.txt",
        }:
            raise ValueError("startup attempt file set changed")
        stdout = (attempt / "stdout.txt").read_bytes()
        stderr = (attempt / "stderr.txt").read_bytes()
        verify_public_receipt(
            record,
            stdout,
            stderr,
            environment_sha256,
            str(metadata["cwd"]),
            pinned_cpu,
        )
        if load_json(attempt / "receipt.json") != record:
            raise ValueError("startup attempt receipt differs from aggregate record")
        if stdout != b"CHECK=PASS\n" or record["argv"] != [metadata["binary"], "startup"]:
            raise ValueError("startup control output or command changed")
        pid = int(record["child_pid"])
        if pid <= 0 or pid in seen_pids:
            raise ValueError("startup process did not have a fresh PID")
        seen_pids.add(pid)

    expected_summary = {
        "aa_analyses": analyse_aa(rows),
        "codec_analyses": analyse_codec_grid(rows),
        "run_metadata": metadata,
        "startup": startup_summary(startup_records),
        "storage": storage_summary(rows),
    }
    compare_json(expected_summary, load_json(root / "summary.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--binary", type=Path)
    args = parser.parse_args()
    root = args.output.resolve(strict=True)
    binary = args.binary.resolve(strict=True) if args.binary else None
    validate(root, binary)
    print(
        "CHECK=PASS timed_processes=176 main_blocks=12 aa_blocks=4 "
        "startup_processes=24 rows=176"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR={error}", file=sys.stderr)
        raise
