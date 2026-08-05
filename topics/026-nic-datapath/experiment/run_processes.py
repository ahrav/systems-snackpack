#!/usr/bin/env python3
"""Run Topic 26 as retained, counterbalanced fresh-process blocks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

SEGMENT_BYTES = 1200
SEGMENTS_PER_BATCH = 32
MEASURED_ROUNDS = 1000
WARMUP_ROUNDS = 100
GRO_CONTROL_ROUNDS = 4
AB_BLOCKS_PER_COMPARISON = 8
AA_BLOCKS = 4
SCHEDULE_SEED = 26_202_608_05
TIMEOUT_SECONDS = 120
PRIMARY_COMPARISONS = (
    {
        "comparison": "sendmmsg_over_scalar",
        "baseline_label": "scalar",
        "baseline_mode": "scalar",
        "candidate_label": "sendmmsg",
        "candidate_mode": "sendmmsg",
    },
    {
        "comparison": "udp_segment_over_scalar",
        "baseline_label": "scalar",
        "baseline_mode": "scalar",
        "candidate_label": "udp_segment",
        "candidate_mode": "udp_segment",
    },
)
MEASUREMENT_KEYS = {
    "schema",
    "kind",
    "status",
    "mode",
    "gro_enabled",
    "transport",
    "segment_bytes",
    "segments_per_batch",
    "warmup_rounds",
    "measured_rounds",
    "logical_datagrams",
    "logical_bytes",
    "verified_datagrams",
    "setup_ns",
    "elapsed_ns",
    "ns_per_datagram",
    "user_cpu_ns",
    "system_cpu_ns",
    "data_send_syscalls",
    "data_receive_syscalls",
    "gro_control_messages",
    "max_gro_segments_per_receive",
    "sender_cpu",
    "receiver_cpu",
    "sender_observed_cpu",
    "receiver_observed_cpu",
    "sender_affinity_count",
    "receiver_affinity_count",
    "actual_receive_buffer",
    "actual_send_buffer",
    "payload_checksum",
    "expected_payload_checksum",
    "payload_verified",
}


class ValidationError(Exception):
    """A retained process result did not meet the declared schema."""


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def exact_json_line(stdout: str) -> dict[str, Any]:
    if not stdout.endswith("\n") or stdout.count("\n") != 1:
        raise ValidationError(
            "probe stdout must be exactly one newline-terminated JSON line"
        )
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ValidationError(f"probe emitted invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError("probe JSON must be an object")
    return value


def require_exact_int(value: Any, name: str, *, positive: bool = False) -> int:
    if type(value) is not int:
        raise ValidationError(f"{name} must be an integer")
    if positive and value <= 0:
        raise ValidationError(f"{name} must be positive")
    return value


def expected_payload_checksum(total_rounds: int) -> int:
    checksum = 0
    for round_index in range(total_rounds):
        for slot in range(SEGMENTS_PER_BATCH):
            receipt = (
                (round_index << 32) ^ (slot << 16) ^ SEGMENT_BYTES
            )
            checksum = (checksum + receipt) & ((1 << 64) - 1)
    return checksum


def validate_measurement(
    value: dict[str, Any],
    *,
    mode: str,
    gro_enabled: bool,
    measured_rounds: int,
    warmup_rounds: int,
) -> None:
    if set(value) != MEASUREMENT_KEYS:
        difference = sorted(set(value) ^ MEASUREMENT_KEYS)
        raise ValidationError(f"measurement fields differ: {difference}")
    fixed = {
        "schema": 1,
        "kind": "measurement",
        "status": "pass",
        "mode": mode,
        "gro_enabled": gro_enabled,
        "transport": "udp_ipv4_loopback",
        "segment_bytes": SEGMENT_BYTES,
        "segments_per_batch": SEGMENTS_PER_BATCH,
        "warmup_rounds": warmup_rounds,
        "measured_rounds": measured_rounds,
    }
    for field, expected in fixed.items():
        if value[field] != expected or type(value[field]) is not type(expected):
            raise ValidationError(
                f"measurement {field} differs: {value[field]!r} != {expected!r}"
            )

    logical_datagrams = measured_rounds * SEGMENTS_PER_BATCH
    verified_datagrams = (measured_rounds + warmup_rounds) * SEGMENTS_PER_BATCH
    checksum = expected_payload_checksum(measured_rounds + warmup_rounds)
    derived = {
        "logical_datagrams": logical_datagrams,
        "logical_bytes": logical_datagrams * SEGMENT_BYTES,
        "verified_datagrams": verified_datagrams,
        "payload_checksum": checksum,
        "expected_payload_checksum": checksum,
        "payload_verified": True,
    }
    for field, expected in derived.items():
        if value[field] != expected or type(value[field]) is not type(expected):
            raise ValidationError(
                f"measurement {field} differs: {value[field]!r} != {expected!r}"
            )

    for field in (
        "setup_ns",
        "elapsed_ns",
        "data_send_syscalls",
        "data_receive_syscalls",
        "actual_receive_buffer",
        "actual_send_buffer",
    ):
        require_exact_int(value[field], field, positive=True)
    for field in (
        "user_cpu_ns",
        "system_cpu_ns",
        "gro_control_messages",
        "max_gro_segments_per_receive",
    ):
        if require_exact_int(value[field], field) < 0:
            raise ValidationError(f"{field} must be nonnegative")
    for field in (
        "sender_cpu",
        "receiver_cpu",
        "sender_observed_cpu",
        "receiver_observed_cpu",
        "sender_affinity_count",
        "receiver_affinity_count",
    ):
        require_exact_int(value[field], field)

    if value["sender_cpu"] == value["receiver_cpu"]:
        raise ValidationError("sender and receiver must use different CPUs")
    if (
        value["sender_observed_cpu"] != value["sender_cpu"]
        or value["receiver_observed_cpu"] != value["receiver_cpu"]
        or value["sender_affinity_count"] != 1
        or value["receiver_affinity_count"] != 1
    ):
        raise ValidationError("thread CPU-affinity receipt differs")
    if value["data_receive_syscalls"] < measured_rounds or (
        value["data_receive_syscalls"] > logical_datagrams
    ):
        raise ValidationError("data receive syscall count is outside possible bounds")
    minimum_send_calls = (
        logical_datagrams if mode == "scalar" else measured_rounds
    )
    if value["data_send_syscalls"] < minimum_send_calls:
        raise ValidationError("data send syscall count is below the mode minimum")

    if gro_enabled:
        if mode != "udp_segment":
            raise ValidationError("UDP_GRO is legal only with UDP_SEGMENT here")
        if value["gro_control_messages"] < measured_rounds or (
            value["max_gro_segments_per_receive"] <= 1
        ):
            raise ValidationError("UDP_GRO control did not observe coalesced delivery")
    elif (
        value["gro_control_messages"] != 0
        or value["max_gro_segments_per_receive"] != 0
    ):
        raise ValidationError("no-GRO path reported a UDP_GRO receipt")

    observed_ns = value["ns_per_datagram"]
    if not isinstance(observed_ns, (int, float)) or isinstance(observed_ns, bool):
        raise ValidationError("ns_per_datagram must be numeric")
    expected_ns = value["elapsed_ns"] / logical_datagrams
    if not math.isclose(
        float(observed_ns), expected_ns, rel_tol=1e-9, abs_tol=1e-6
    ):
        raise ValidationError("ns_per_datagram differs from elapsed/datagrams")


def make_schedule(
    comparison: dict[str, str], blocks: int, rng: random.Random
) -> list[dict[str, Any]]:
    if blocks <= 0 or blocks % 2:
        fail("schedule blocks must be a positive even number")
    templates = ["ABBA"] * (blocks // 2) + ["BAAB"] * (blocks // 2)
    rng.shuffle(templates)
    return [
        {
            **comparison,
            "block": block,
            "template": template,
        }
        for block, template in enumerate(templates, start=1)
    ]


def invoke(
    binary: Path,
    *,
    mode: str,
    gro_enabled: bool,
    measured_rounds: int,
    warmup_rounds: int,
    identity: dict[str, Any],
    attempts,
) -> dict[str, Any] | None:
    command = [
        str(binary),
        mode,
        str(measured_rounds),
        str(warmup_rounds),
    ]
    if gro_enabled:
        command.append("--gro")

    started = time.monotonic_ns()
    timed_out = False
    spawn_error = ""
    try:
        completed = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
        returncode: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = None
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
    except OSError as error:
        returncode = None
        stdout = ""
        stderr = ""
        spawn_error = f"{type(error).__name__}: {error}"
    process_ns = time.monotonic_ns() - started

    parse_status = "ok"
    parse_error = ""
    parsed: dict[str, Any] | None = None
    try:
        if spawn_error:
            raise ValidationError(f"probe could not start: {spawn_error}")
        if timed_out:
            raise ValidationError("probe timed out")
        if returncode != 0:
            raise ValidationError(f"probe exited {returncode}")
        if stderr:
            raise ValidationError("probe wrote to stderr")
        parsed = exact_json_line(stdout)
        validate_measurement(
            parsed,
            mode=mode,
            gro_enabled=gro_enabled,
            measured_rounds=measured_rounds,
            warmup_rounds=warmup_rounds,
        )
    except ValidationError as error:
        parse_status = "error"
        parse_error = str(error)

    attempt = {
        **identity,
        "mode": mode,
        "gro_enabled": gro_enabled,
        "command": command,
        "timeout_seconds": TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "spawn_error": spawn_error,
        "returncode": returncode,
        "process_ns": process_ns,
        "stdout": stdout,
        "stderr": stderr,
        "parse_status": parse_status,
        "parse_error": parse_error,
    }
    attempts.write(json.dumps(attempt, sort_keys=True) + "\n")
    attempts.flush()
    if parsed is None or parse_status != "ok":
        return None
    return {**identity, "process_ns": process_ns, **parsed}


def log_contrast(
    rows: list[dict[str, Any]], numerator: str, denominator: str
) -> float:
    numerator_logs = [
        math.log(row["elapsed_ns"]) for row in rows if row["label"] == numerator
    ]
    denominator_logs = [
        math.log(row["elapsed_ns"])
        for row in rows
        if row["label"] == denominator
    ]
    if len(numerator_logs) != 2 or len(denominator_logs) != 2:
        fail("complete four-period block is missing")
    return statistics.fmean(numerator_logs) - statistics.fmean(denominator_logs)


def interval(contrasts: list[float]) -> dict[str, Any]:
    critical = {
        4: 3.182446305,
        8: 2.364624251,
    }.get(len(contrasts))
    if critical is None:
        fail("no predeclared Student-t critical value for contrast count")
    mean = statistics.fmean(contrasts)
    deviation = statistics.stdev(contrasts)
    half = critical * deviation / math.sqrt(len(contrasts))
    return {
        "n_complete_blocks": len(contrasts),
        "geometric_mean_ratio": math.exp(mean),
        "log_t_95_low": math.exp(mean - half),
        "log_t_95_high": math.exp(mean + half),
        "mean_log_contrast": mean,
        "log_sd": deviation,
    }


def mode_diagnostics(
    observations: list[dict[str, Any]], mode: str
) -> dict[str, Any]:
    rows = [
        row
        for row in observations
        if row["family"] in {"primary", "aa"} and row["mode"] == mode
    ]
    return {
        "processes": len(rows),
        "median_ns_per_datagram": statistics.median(
            row["ns_per_datagram"] for row in rows
        ),
        "median_data_send_syscalls": statistics.median(
            row["data_send_syscalls"] for row in rows
        ),
        "median_data_receive_syscalls": statistics.median(
            row["data_receive_syscalls"] for row in rows
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    output_dir = args.output_dir.resolve()
    if not binary.is_file():
        fail(f"binary is unavailable: {binary}")
    if output_dir.exists() and any(output_dir.iterdir()):
        fail("output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SCHEDULE_SEED)
    primary_schedule = [
        block
        for comparison in PRIMARY_COMPARISONS
        for block in make_schedule(comparison, AB_BLOCKS_PER_COMPARISON, rng)
    ]
    aa_spec = {
        "comparison": "aa_right_over_aa_left",
        "baseline_label": "aa_left",
        "baseline_mode": "sendmmsg",
        "candidate_label": "aa_right",
        "candidate_mode": "sendmmsg",
    }
    aa_schedule = make_schedule(aa_spec, AA_BLOCKS, rng)
    fixed_attempts = (
        len(primary_schedule) * 4 + len(aa_schedule) * 4 + 2
    )
    binary_digest = sha256(binary)
    design = {
        "schema": 1,
        "binary_sha256": binary_digest,
        "transport": "UDP/IPv4 loopback",
        "segment_bytes": SEGMENT_BYTES,
        "segments_per_batch": SEGMENTS_PER_BATCH,
        "measured_rounds_per_primary_process": MEASURED_ROUNDS,
        "warmup_rounds_per_primary_process": WARMUP_ROUNDS,
        "gro_control_rounds": GRO_CONTROL_ROUNDS,
        "schedule_seed": SCHEDULE_SEED,
        "primary_schedule": primary_schedule,
        "aa_schedule": aa_schedule,
        "gro_control_schedule": [
            {"label": "gro_disabled", "mode": "udp_segment", "gro_enabled": False},
            {"label": "gro_enabled", "mode": "udp_segment", "gro_enabled": True},
        ],
        "fixed_attempt_count": fixed_attempts,
        "treatment_application_unit": "one fresh process invocation",
        "randomization_unit": "one block receives an ABBA or BAAB template",
        "analysis_unit": "one complete four-process ABBA or BAAB block",
        "subsamples": (
            "rounds inside a process are workload repetition, not independent samples"
        ),
        "assignment": (
            "seed-shuffled restricted randomization with equal ABBA and BAAB "
            "counts inside each comparison"
        ),
        "stopping": (
            "fixed 8 blocks per primary comparison, 4 A/A blocks, and two "
            "semantic controls; no peeking, retry, or replacement"
        ),
        "invalid_attempt_policy": (
            "retain every attempt; any invalid attempt or incomplete block fails the run"
        ),
        "primary_receive_semantics": "UDP_GRO disabled for every timed comparison",
        "estimands": [
            "geometric-mean sendmmsg/scalar elapsed ratio",
            "geometric-mean UDP_SEGMENT/scalar elapsed ratio",
        ],
        "interval": (
            "two-sided 95% Student-t interval over complete-block log contrasts; "
            "a descriptive run-window interval whose repeated-block independence "
            "and normality are assumptions, not established by fresh processes; "
            "variation covers process blocks on this host and run window"
        ),
        "aa_scope": (
            "same binary and sendmmsg command through both labels; mechanical "
            "path-asymmetry diagnostic, not long-run null calibration"
        ),
        "gro_control_scope": (
            "payload and coalesced-delivery semantics only; elapsed values do "
            "not enter a performance estimate"
        ),
        "timing_boundary": (
            "payloads are prebuilt during setup; CLOCK_MONOTONIC_RAW covers "
            "one contiguous sequence of measured sender/receiver/ack rounds "
            "after warmup; process setup and payload construction are excluded"
        ),
    }
    write_json(output_dir / "design.json", design)

    observations: list[dict[str, Any]] = []
    failures = 0
    sequence = 0
    with (output_dir / "attempts.jsonl").open("x", encoding="utf-8") as attempts:
        for block in primary_schedule:
            for position, letter in enumerate(block["template"], start=1):
                candidate = letter == "B"
                mode = (
                    block["candidate_mode"] if candidate else block["baseline_mode"]
                )
                label = (
                    block["candidate_label"]
                    if candidate
                    else block["baseline_label"]
                )
                identity = {
                    "sequence": sequence,
                    "family": "primary",
                    "comparison": block["comparison"],
                    "block": block["block"],
                    "template": block["template"],
                    "position": position,
                    "label": label,
                }
                result = invoke(
                    binary,
                    mode=mode,
                    gro_enabled=False,
                    measured_rounds=MEASURED_ROUNDS,
                    warmup_rounds=WARMUP_ROUNDS,
                    identity=identity,
                    attempts=attempts,
                )
                failures += result is None
                if result is not None:
                    observations.append(result)
                sequence += 1

        for block in aa_schedule:
            for position, letter in enumerate(block["template"], start=1):
                label = (
                    block["candidate_label"]
                    if letter == "B"
                    else block["baseline_label"]
                )
                identity = {
                    "sequence": sequence,
                    "family": "aa",
                    "comparison": block["comparison"],
                    "block": block["block"],
                    "template": block["template"],
                    "position": position,
                    "label": label,
                }
                result = invoke(
                    binary,
                    mode="sendmmsg",
                    gro_enabled=False,
                    measured_rounds=MEASURED_ROUNDS,
                    warmup_rounds=WARMUP_ROUNDS,
                    identity=identity,
                    attempts=attempts,
                )
                failures += result is None
                if result is not None:
                    observations.append(result)
                sequence += 1

        for position, gro_enabled in enumerate((False, True), start=1):
            label = "gro_enabled" if gro_enabled else "gro_disabled"
            identity = {
                "sequence": sequence,
                "family": "gro_control",
                "comparison": "gro_semantics",
                "block": 1,
                "template": "CG",
                "position": position,
                "label": label,
            }
            result = invoke(
                binary,
                mode="udp_segment",
                gro_enabled=gro_enabled,
                measured_rounds=GRO_CONTROL_ROUNDS,
                warmup_rounds=0,
                identity=identity,
                attempts=attempts,
            )
            failures += result is None
            if result is not None:
                observations.append(result)
            sequence += 1

    with (output_dir / "observations.jsonl").open(
        "x", encoding="utf-8"
    ) as stream:
        for row in observations:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    complete = failures == 0 and len(observations) == fixed_attempts
    status = {
        "schema": 1,
        "complete": complete,
        "attempts": sequence,
        "valid_observations": len(observations),
        "invalid_attempts": failures,
        "fixed_attempt_count": fixed_attempts,
    }
    write_json(output_dir / "run-status.json", status)
    if not complete:
        fail("one or more attempts failed; retained fixed run is incomplete")

    contrast_rows: list[dict[str, Any]] = []
    for family, schedule in (
        ("primary", primary_schedule),
        ("aa", aa_schedule),
    ):
        for block in schedule:
            rows = [
                row
                for row in observations
                if row["family"] == family
                and row["comparison"] == block["comparison"]
                and row["block"] == block["block"]
            ]
            contrast = log_contrast(
                rows, block["candidate_label"], block["baseline_label"]
            )
            contrast_rows.append(
                {
                    "family": family,
                    "comparison": block["comparison"],
                    "block": block["block"],
                    "template": block["template"],
                    "log_contrast": contrast,
                    "ratio": math.exp(contrast),
                }
            )
    with (output_dir / "block-contrasts.csv").open(
        "x", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(contrast_rows[0]))
        writer.writeheader()
        writer.writerows(contrast_rows)

    summaries = {}
    for comparison in (
        "sendmmsg_over_scalar",
        "udp_segment_over_scalar",
        "aa_right_over_aa_left",
    ):
        summaries[comparison] = interval(
            [
                row["log_contrast"]
                for row in contrast_rows
                if row["comparison"] == comparison
            ]
        )
    summaries["aa_right_over_aa_left"]["scope"] = design["aa_scope"]

    gro_rows = [
        row for row in observations if row["family"] == "gro_control"
    ]
    by_label = {row["label"]: row for row in gro_rows}
    gro_control = {
        "schema": 1,
        "scope": design["gro_control_scope"],
        "gro_disabled": by_label["gro_disabled"],
        "gro_enabled": by_label["gro_enabled"],
        "same_logical_payload": (
            by_label["gro_disabled"]["logical_datagrams"]
            == by_label["gro_enabled"]["logical_datagrams"]
            and by_label["gro_disabled"]["payload_checksum"]
            == by_label["gro_enabled"]["payload_checksum"]
        ),
        "coalesced_delivery_observed": (
            by_label["gro_enabled"]["gro_control_messages"] > 0
            and by_label["gro_enabled"]["max_gro_segments_per_receive"] > 1
        ),
        "timing_claim": None,
    }
    if (
        gro_control["same_logical_payload"] is not True
        or gro_control["coalesced_delivery_observed"] is not True
    ):
        fail("GRO semantic control differs after validated observations")
    write_json(output_dir / "gro-control.json", gro_control)

    summary = {
        "schema": 1,
        "binary_sha256": binary_digest,
        "attempt_count": sequence,
        "valid_observation_count": len(observations),
        "primary_gro_enabled": False,
        "summaries": summaries,
        "mode_diagnostics": {
            mode: mode_diagnostics(observations, mode)
            for mode in ("scalar", "sendmmsg", "udp_segment")
        },
        "gro_control": {
            "same_logical_payload": gro_control["same_logical_payload"],
            "coalesced_delivery_observed": gro_control[
                "coalesced_delivery_observed"
            ],
            "timing_claim": None,
        },
    }
    write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SystemExit as error:
        if str(error):
            print(str(error), file=sys.stderr)
        raise
