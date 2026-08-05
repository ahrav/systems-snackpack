#!/usr/bin/env python3
"""Independently validate a retained Topic 25 evidence directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, NoReturn

MAPPING_BYTES = 512 * 1024 * 1024
PASSES = 4
AB_BLOCKS_PER_DIRECTION = 8
AA_BLOCKS_PER_DIRECTION = 4
T_CRITICAL = {4: 3.182446305, 8: 2.364624251, 16: 2.131449546}


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        values = [json.loads(line) for line in lines]
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not values or not all(isinstance(value, dict) for value in values):
        fail(f"{path} must contain JSON objects")
    return values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(observed: float, expected: float, name: str) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12):
        fail(f"{name} differs: {observed!r} != {expected!r}")


def parse_one_json_line(text: str, name: str) -> dict[str, Any]:
    if not text.endswith("\n") or text.count("\n") != 1:
        fail(f"{name} is not exactly one newline-terminated JSON line")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        fail(f"{name} contains invalid JSON: {error}")
    if not isinstance(value, dict):
        fail(f"{name} JSON must be an object")
    return value


def expected_pair(topology: dict[str, Any], control: bool) -> tuple[list[int], list[int], list[int]]:
    if control:
        return (
            [topology["control_node"], topology["control_node"]],
            [topology["control_cpu"], topology["control_cpu"]],
            [topology["control_distance"], topology["control_distance"]],
        )
    return topology["pair_nodes"], topology["pair_cpus"], topology["pair_distances"]


def validate_affinity(value: Any, cpu: int, name: str) -> None:
    fields = {"requested_cpu", "effective_cpu", "current_cpu", "effective_count"}
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{name} affinity schema differs")
    if value["effective_count"] != 1 or any(
        value[field] != cpu for field in ("requested_cpu", "effective_cpu", "current_cpu")
    ):
        fail(f"{name} affinity is not the requested singleton CPU")


def validate_measurement(
    value: dict[str, Any], topology: dict[str, Any], *, passes: int = PASSES
) -> None:
    if value.get("schema") != 1 or value.get("kind") != "measurement":
        fail("measurement schema differs")
    treatment = value.get("treatment")
    direction = value.get("direction")
    if treatment not in {"local", "remote", "control"} or direction not in {0, 1}:
        fail("measurement treatment or direction is invalid")
    control = treatment == "control"
    if control and direction != 0:
        fail("one-node control must use direction zero")
    nodes, cpus, distances = expected_pair(topology, control)
    fixed = {
        "mapping_bytes": MAPPING_BYTES,
        "passes": passes,
        "pair_nodes": nodes,
        "pair_cpus": cpus,
        "pair_distances": distances,
    }
    for field, expected in fixed.items():
        if value.get(field) != expected:
            fail(f"measurement {field} differs")
    page_size = value.get("page_size")
    pages = value.get("page_count")
    if not isinstance(page_size, int) or not isinstance(pages, int):
        fail("page size or count is not an integer")
    if page_size * pages != MAPPING_BYTES or value.get("loads") != pages * passes:
        fail("mapping or dependent-load count differs")
    step = value.get("permutation_step")
    if not isinstance(step, int) or math.gcd(step, pages) != 1:
        fail("pointer-chase permutation is not a single cycle")

    worker_node = nodes[direction]
    worker_cpu = cpus[direction]
    peer_node = nodes[1 - direction]
    peer_cpu = cpus[1 - direction]
    touch_node, touch_cpu = (
        (worker_node, worker_cpu)
        if treatment in {"local", "control"}
        else (peer_node, peer_cpu)
    )
    identity = (
        value.get("worker_node"), value.get("worker_cpu"),
        value.get("peer_node"), value.get("peer_cpu"),
        value.get("touch_node"), value.get("touch_cpu"),
    )
    if identity != (worker_node, worker_cpu, peer_node, peer_cpu, touch_node, touch_cpu):
        fail("measurement CPU/node identities differ from the declared treatment")
    if treatment == "remote" and value.get("access_distance") != distances[direction]:
        fail("remote access distance differs from topology")
    if control and value.get("access_distance") != topology["control_distance"]:
        fail("control access distance differs from topology")
    validate_affinity(value.get("touch_affinity"), touch_cpu, "touch")
    validate_affinity(value.get("worker_affinity"), worker_cpu, "worker")

    smaps = value.get("smaps")
    if not isinstance(smaps, dict) or not (
        smaps.get("exact_vma") is True
        and smaps.get("vmflag_nh") is True
        and smaps.get("anon_huge_kib") == 0
        and smaps.get("thp_eligible") == 0
    ):
        fail("smaps does not establish the exact base-page VMA")
    if value.get("madv_nohugepage") is not True:
        fail("MADV_NOHUGEPAGE receipt is absent")
    for phase in ("placement_before", "placement_after"):
        placement = value.get(phase)
        if not isinstance(placement, dict) or (
            placement.get("syscall_result") != 0
            or placement.get("expected_pages") != pages
            or placement.get("other_pages") != 0
            or placement.get("error_pages") != 0
        ):
            fail(f"{phase} does not keep every page on the intended node")
    if value.get("checksum_ok") is not True or value.get("checksum") != value.get(
        "expected_checksum"
    ):
        fail("pointer-chase checksum differs")
    if value.get("read_faults_zero") is not True or value.get("read_minor_faults") != 0 or (
        value.get("read_major_faults") != 0
    ):
        fail("timed dependent chase incurred a page fault")
    if not isinstance(value.get("read_ns"), int) or value["read_ns"] <= 0:
        fail("read timing is invalid")
    close(value.get("ns_per_load"), value["read_ns"] / value["loads"], "ns_per_load")


def interval(contrasts: list[float]) -> dict[str, float | int]:
    if len(contrasts) not in T_CRITICAL:
        fail(f"no declared critical value for {len(contrasts)} blocks")
    mean = statistics.fmean(contrasts)
    deviation = statistics.stdev(contrasts)
    half = T_CRITICAL[len(contrasts)] * deviation / math.sqrt(len(contrasts))
    return {
        "n_complete_blocks": len(contrasts),
        "geometric_mean_ratio": math.exp(mean),
        "log_t_95_low": math.exp(mean - half),
        "log_t_95_high": math.exp(mean + half),
        "mean_log_contrast": mean,
        "log_sd": deviation,
    }


def compare_interval(observed: dict[str, Any], expected: dict[str, float | int], name: str) -> None:
    if set(observed) != set(expected):
        fail(f"{name} interval fields differ")
    for field, value in expected.items():
        if field == "n_complete_blocks":
            if observed[field] != value:
                fail(f"{name}.{field} differs")
        else:
            close(observed[field], value, f"{name}.{field}")


def verify_source_identity(evidence: Path, source_root: Path, binary_digest: str) -> None:
    binary_line = (evidence / "binary.sha256").read_text(encoding="utf-8").split()
    if not binary_line or binary_line[0] != binary_digest:
        fail("binary SHA-256 differs from experiment design")
    identity_lines = (evidence / "source-identity.txt").read_text(encoding="utf-8").splitlines()
    recorded = None
    for line in identity_lines:
        if line.startswith("source_commit="):
            recorded = line.split("=", 1)[1].strip()
    if recorded is None or len(recorded) != 40:
        fail("source identity lacks a recorded source commit")
    # Retained receipts are validated from later commits, after review may
    # have changed the experiment sources. Bind the receipts to the recorded
    # source commit's blobs, and require that commit to be reachable from the
    # checkout, instead of assuming HEAD is the source commit.
    reachable = subprocess.run(
        ["git", "-C", str(source_root), "merge-base", "--is-ancestor", recorded, "HEAD"],
        capture_output=True, check=False,
    )
    if reachable.returncode != 0:
        fail("recorded source commit is not reachable from the checkout HEAD")
    expected_files = {
        "numa_first_touch_probe.c", "run_processes.py", "validate_receipts.py", "run_host.sh"
    }
    found: set[str] = set()
    for line in identity_lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            continue
        name = Path(parts[1].strip()).name
        if name in expected_files:
            blob = subprocess.run(
                [
                    "git", "-C", str(source_root), "show",
                    f"{recorded}:topics/025-numa-first-touch-migration/experiment/{name}",
                ],
                capture_output=True, check=False,
            )
            if blob.returncode != 0:
                fail(f"recorded source commit lacks experiment file {name}")
            if hashlib.sha256(blob.stdout).hexdigest() != parts[0]:
                fail(f"source identity differs for {name}")
            found.add(name)
    if found != expected_files:
        fail("source identity does not cover every experiment file")


def verify_evidence_manifest(evidence: Path) -> None:
    """Verify the retained seal: every bundle file hashed, every hash correct."""
    manifest_path = evidence / "evidence.sha256"
    listed: set[str] = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            fail("malformed evidence manifest line")
        name = parts[1].strip()
        target = (evidence / name).resolve()
        if evidence.resolve() not in target.parents:
            fail(f"evidence manifest names a path outside the bundle: {name}")
        if sha256(target) != parts[0]:
            fail(f"evidence hash differs for {name}")
        listed.add(str(target))
    for path in evidence.rglob("*"):
        if (
            path.is_file()
            # Manifests seal other files; they are not themselves sealed.
            and path.name not in ("evidence.sha256", "supplement.sha256")
            and str(path.resolve()) not in listed
        ):
            # Post-run supplements are sealed by the bundle set's sibling
            # manifest rather than the run's own evidence manifest.
            if supplement_digest(evidence, path) == sha256(path):
                continue
            fail(f"retained file is not sealed by the evidence manifest: {path.name}")


def supplement_digest(evidence: Path, path: Path) -> str | None:
    """Return the recorded digest for a supplement file, if sealed."""
    manifest = evidence.parent / "supplements.sha256"
    if not manifest.is_file():
        return None
    relative = f"{evidence.name}/{path.relative_to(evidence)}"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip() == relative:
            return parts[0]
    return None


def validate_schedule(design: dict[str, Any], observations: list[dict[str, Any]]) -> None:
    ab_schedule = design.get("ab_schedule")
    aa_schedule = design.get("aa_schedule")
    if not isinstance(ab_schedule, list) or not isinstance(aa_schedule, list):
        fail("two-node design schedules are absent")
    for name, schedule, per_direction in (
        ("ab", ab_schedule, AB_BLOCKS_PER_DIRECTION),
        ("aa", aa_schedule, AA_BLOCKS_PER_DIRECTION),
    ):
        if len(schedule) != 2 * per_direction:
            fail(f"{name} schedule has the wrong block count")
        if len({row["block"] for row in schedule}) != len(schedule):
            fail(f"{name} schedule repeats a block identifier")
        for direction in (0, 1):
            templates = [row["template"] for row in schedule if row["direction"] == direction]
            if Counter(templates) != Counter({"ABBA": per_direction // 2, "BAAB": per_direction // 2}):
                fail(f"{name} direction {direction} is not position-balanced")

    expected: list[tuple[Any, ...]] = []
    sequence = 0
    for family, schedule in (("ab", ab_schedule), ("aa", aa_schedule)):
        for block in schedule:
            for position, letter in enumerate(block["template"], start=1):
                if family == "ab":
                    label = letter
                    treatment = "local" if letter == "A" else "remote"
                else:
                    label = "A0" if letter == "A" else "A1"
                    treatment = "local"
                expected.append((sequence, family, block["block"], block["template"],
                                 block["direction"], position, label, treatment))
                sequence += 1
    observed = [
        (row["sequence"], row["family"], row["block"], row["template"], row["direction"],
         row["position"], row["label"], row["treatment"])
        for row in observations
    ]
    if observed != expected:
        fail("observations differ from the fixed schedule or include replacements")


def validate_two_node(
    experiment: Path, design: dict[str, Any], observations: list[dict[str, Any]],
    summary: dict[str, Any], attempts: list[dict[str, Any]],
) -> None:
    expected_count = 2 * (AB_BLOCKS_PER_DIRECTION + AA_BLOCKS_PER_DIRECTION) * 4
    if len(attempts) != expected_count or len(observations) != expected_count:
        fail("two-node attempt count differs from the fixed design")
    validate_schedule(design, observations)
    by_block: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        by_block[(row["family"], row["block"])].append(row)
    contrasts: list[dict[str, Any]] = []
    for (family, block), rows in by_block.items():
        numerator, denominator = (("B", "A") if family == "ab" else ("A1", "A0"))
        numerator_logs = [math.log(row["read_ns"]) for row in rows if row["label"] == numerator]
        denominator_logs = [math.log(row["read_ns"]) for row in rows if row["label"] == denominator]
        if len(numerator_logs) != 2 or len(denominator_logs) != 2:
            fail("a complete block does not contain two observations per label")
        contrasts.append({
            "family": family, "block": block, "direction": rows[0]["direction"],
            "log_contrast": statistics.fmean(numerator_logs) - statistics.fmean(denominator_logs),
        })
    groups = {
        "ab": [row["log_contrast"] for row in contrasts if row["family"] == "ab"],
        "direction_0": [row["log_contrast"] for row in contrasts if row["family"] == "ab" and row["direction"] == 0],
        "direction_1": [row["log_contrast"] for row in contrasts if row["family"] == "ab" and row["direction"] == 1],
        "aa": [row["log_contrast"] for row in contrasts if row["family"] == "aa"],
        "aa_direction_0": [row["log_contrast"] for row in contrasts if row["family"] == "aa" and row["direction"] == 0],
        "aa_direction_1": [row["log_contrast"] for row in contrasts if row["family"] == "aa" and row["direction"] == 1],
    }
    for name, values in groups.items():
        compare_interval(summary[name], interval(values), name)
    if summary.get("attempt_count") != expected_count or summary.get(
        "valid_observation_count"
    ) != expected_count:
        fail("two-node summary process counts differ")
    if summary.get("placement_after_changed_pages") != 0:
        fail("summary reports post-read page movement")
    if not (experiment / "block-contrasts.csv").is_file():
        fail("block contrast ledger is absent")


def validate_control(
    design: dict[str, Any], observations: list[dict[str, Any]], summary: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> None:
    if design.get("mode") != "one-node-correctness-control" or len(attempts) != 4 or (
        len(observations) != 4
    ):
        fail("one-node control design or process count differs")
    for sequence, row in enumerate(observations):
        identity = (row.get("sequence"), row.get("family"), row.get("block"),
                    row.get("template"), row.get("position"), row.get("label"),
                    row.get("treatment"), row.get("direction"))
        if identity != (sequence, "control", sequence + 1, "C", 1, "C", "control", 0):
            fail("one-node control schedule differs or includes a replacement")
    if set(summary) & {"ab", "direction_0", "direction_1", "geometric_mean_ratio"}:
        fail("one-node summary contains a remote/local performance estimate")
    if summary.get("remote_local_estimate", "missing") is not None:
        fail("one-node summary must explicitly report no remote/local estimate")
    if summary.get("attempt_count") != 4 or summary.get("valid_observation_count") != 4 or (
        summary.get("all_pages_stayed_on_control_node") is not True
    ):
        fail("one-node summary correctness fields differ")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    source_root = args.source_root.resolve()
    experiment = evidence / "experiment"
    topology = load_json(experiment / "topology.json")
    design = load_json(experiment / "design.json")
    summary = load_json(experiment / "summary.json")
    status = load_json(experiment / "run-status.json")
    attempts = load_jsonl(experiment / "attempts.jsonl")
    observations = load_jsonl(experiment / "observations.jsonl")
    if status.get("complete") is not True or status.get("invalid_attempts") != 0:
        fail("run status is incomplete")
    if design.get("binary_sha256") != summary.get("binary_sha256"):
        fail("design and summary binary identities differ")
    verify_source_identity(evidence, source_root, design["binary_sha256"])
    verify_evidence_manifest(evidence)

    if len(attempts) != len(observations):
        fail("attempt and observation ledgers differ in length")
    # pi-lens-ignore: B905
    for attempt, observation in zip(attempts, observations):
        if attempt.get("returncode") != 0 or attempt.get("timed_out") is not False or (
            attempt.get("stderr") != "" or attempt.get("parse_status") != "ok"
        ):
            fail("an attempted process did not pass")
        measurement = parse_one_json_line(attempt.get("stdout", ""), "attempt stdout")
        validate_measurement(measurement, topology)
        for field, value in measurement.items():
            if observation.get(field) != value:
                fail(f"observation differs from attempt stdout for {field}")
        for field in ("sequence", "family", "block", "template", "direction", "position", "label"):
            if observation.get(field) != attempt.get(field):
                fail(f"observation identity differs from attempt for {field}")

    smoke = parse_one_json_line(
        (evidence / "control-smoke.jsonl").read_text(encoding="utf-8"), "control smoke"
    )
    validate_measurement(smoke, topology, passes=1)
    if smoke.get("treatment") != "control" or (evidence / "control-smoke.stderr").stat().st_size:
        fail("control smoke did not complete cleanly")
    if topology.get("supported") is True:
        validate_two_node(experiment, design, observations, summary, attempts)
    else:
        validate_control(design, observations, summary, attempts)

    required_gates = {
        "git-diff-check.log", "cargo-fmt.log", "cargo-test-lib-examples.log",
        "cargo-test-doc.log", "cargo-clippy.log", "cargo-bench-no-run.log", "cargo-doc.log",
        "script-syntax.log",
    }
    if {path.name for path in (evidence / "gates").iterdir()} != required_gates:
        fail("workspace gate receipt set differs")
    for path in ("codegen-first-touch.txt", "codegen-dependent-read.txt"):
        if (evidence / path).stat().st_size == 0:
            fail(f"{path} is empty")
    print(
        json.dumps(
            {
                "status": "pass",
                "mode": "two-node-performance" if topology.get("supported") else "one-node-control",
                "attempts": len(attempts),
                "source_identity": "match",
                "placement": "all-pages-fixed",
                "codegen": "linked-symbols-present",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
