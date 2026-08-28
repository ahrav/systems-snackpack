#!/usr/bin/env python3
"""Validate and independently recompute one Topic 48 host receipt."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import shlex
import statistics
import subprocess
import tarfile
from collections import defaultdict
from pathlib import Path


T95 = {1: 12.706, 3: 3.182}
HINT_INSTRUCTION = re.compile(r"\b(?:prefetch(?:nta|t[012]|w|wt1)|prfm)\b")
# The frozen round-01 toolchain: rounds/01.md declares GCC 11.5 with exactly
# these flags, so a receipt built any other way measures different kernels.
FROZEN_GCC_VERSION = "11.5"
FROZEN_BUILD_FLAGS = (
    "-O3 -g -std=c11 -Wall -Wextra -Werror -march=native "
    "-fno-tree-vectorize -fno-tree-slp-vectorize"
)
GCC_VERSION_LINE = re.compile(r"^gcc \([^)]*\) (\d+\.\d+)", re.MULTILINE)
LINE_BYTES = 64
REQUIRED = (
    "source-archive.tar.gz",
    "source-commit.txt",
    "source-archive.sha256",
    "host.txt",
    "build.txt",
    "prefetch_bench",
    "binary.sha256",
    "experiment-sources.sha256",
    "smoke/demand.json",
    "smoke/demand.stderr",
    "smoke/prefetch.json",
    "smoke/prefetch.stderr",
    "codegen/symbols.txt",
    "codegen/kernel_demand.asm",
    "codegen/kernel_prefetch.asm",
    "random.tsv",
    "random-run.log",
    "random-analysis.json",
    "sequential.tsv",
    "sequential-run.log",
    "sequential-analysis.json",
    "SHA256SUMS",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recorded_hashes(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        digest, separator, name = line.partition("  ")
        require(separator == "  " and len(digest) == 64, f"malformed hash line: {line}")
        require(name not in values and not name.startswith("/"), f"unsafe hash path: {name}")
        require(".." not in Path(name).parts, f"unsafe hash path: {name}")
        values[name] = digest
    return values


def executed_source_hashes(path: Path) -> dict[str, str]:
    """Parse a sha256sum record whose names are the absolute paths that ran
    remotely; the basename identifies each source file."""
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        digest, separator, name = line.partition("  ")
        require(separator == "  " and len(digest) == 64, f"malformed hash line: {line}")
        base = Path(name).name
        require(base != "" and base not in values, f"duplicate executed source: {name}")
        values[base] = digest
    return values


def host_field_present(host_text: str, key: str, expected: str) -> bool:
    """host.txt lines are either bare values or key=value pairs."""
    lines = {line.strip() for line in host_text.splitlines()}
    return expected in lines or f"{key}={expected}" in lines


def require_recomputed_timing(result: dict) -> None:
    """Bind the derived per-access figure to the retained raw evidence instead
    of trusting the recorded field."""
    require(result["lines"] == result["mib"] * 1024 * 1024 // LINE_BYTES, "line count mismatch")
    require(result["accesses"] == result["lines"] * result["passes"], "access count mismatch")
    recomputed = result["elapsed_seconds"] * 1.0e9 / result["accesses"]
    require(
        math.isclose(result["ns_per_access"], recomputed, rel_tol=1e-4, abs_tol=1e-9),
        "ns_per_access differs from elapsed-time recomputation",
    )


def validate_smoke(path: Path, expected_mode: str) -> None:
    result = json.loads(path.read_text())
    require(result["schema"] == 1 and result["mode"] == expected_mode, "smoke mode mismatch")
    require(result["correct"] and result["checksum"] == result["expected"], "smoke checksum failed")
    require(result["cpu_start"] == 0 and result["cpu_end"] == 0, "smoke placement failed")
    require_recomputed_timing(result)


def summarize(values: list[float]) -> dict[str, float | int]:
    count = len(values)
    mean_log = statistics.fmean(values)
    standard_deviation = statistics.stdev(values)
    half = T95[count - 1] * standard_deviation / math.sqrt(count)
    return {
        "blocks": count,
        "prefetch_over_demand_geomean": math.exp(mean_log),
        "effect_percent": (math.exp(mean_log) - 1.0) * 100.0,
        "log_ratio_sample_sd": standard_deviation,
        "t95_ratio_low": math.exp(mean_log - half),
        "t95_ratio_high": math.exp(mean_log + half),
        "block_ratio_min": math.exp(min(values)),
        "block_ratio_max": math.exp(max(values)),
    }


def close(actual: object, expected: object, path: str = "analysis") -> None:
    if isinstance(expected, float):
        require(
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
            f"{path} differs",
        )
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"{path} keys differ")
        for key, value in expected.items():
            close(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{path} length differs")
        for index, value in enumerate(expected):
            close(actual[index], value, f"{path}[{index}]")
    else:
        require(type(actual) is type(expected) and actual == expected, f"{path} differs")


def validate_campaign(
    path: Path,
    analysis_path: Path,
    *,
    pattern: str,
    primary_distances: set[int],
    primary_blocks: int,
    aa_blocks: int,
    campaign_seed: int,
) -> dict[str, object]:
    grouped: dict[tuple[str, int, int], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    binary_hashes = set()
    pids = set()
    phases: dict[str, list[float]] = defaultdict(list)
    schedules: dict[tuple[str, int, int], dict[str, set[object]]] = defaultdict(
        lambda: {"templates": set(), "positions": set()}
    )
    distance_order: list[int] = []
    completed_distances: set[int] = set()
    current_distance: int | None = None
    saw_aa = False
    previous_started = -1
    actual_schedule: list[tuple[str, int, int, str, int, str]] = []
    rows = 0

    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        require(reader.fieldnames is not None, "missing TSV header")
        for row in reader:
            rows += 1
            require(int(row["returncode"]) == 0, "nonzero process retained")
            result = json.loads(row["result_json"])
            case = row["case"]
            distance = int(row["distance"])
            block = int(row["block"])
            template = row["template"]
            position = int(row["position"])
            label = row["label"]
            require(case in {"primary", "aa"} and label in {"A", "B"}, "invalid label")
            require(template in {"ABBA", "BAAB"}, "invalid template")
            require(1 <= position <= 4 and template[position - 1] == label, "template mismatch")
            require(int(row["campaign_seed"]) == campaign_seed, "campaign seed mismatch")
            started = int(row["started_unix_ns"])
            require(started > previous_started, "process start order is not strictly increasing")
            previous_started = started
            require(result["schema"] == 1 and result["pattern"] == pattern, "input echo mismatch")
            require(result["mib"] == 256 and result["passes"] == 2, "workload mismatch")
            require(result["warmup_passes"] == 1, "warmup mismatch")
            require(result["seed"] == "0x0000000002dc6c30", "workload seed mismatch")
            require(result["correct"] and result["checksum"] == result["expected"], "checksum failed")
            require(str(result["pid"]) == row["pid"], "TSV PID differs from process result")
            require(result["cpu_start"] == 0 and result["cpu_end"] == 0, "CPU placement failed")
            require(result["timed_minor_faults"] == 0, "timed minor fault retained")
            require(result["timed_major_faults"] == 0, "timed major fault retained")
            require(result["madv_nohuge_data_rc"] == 0, "data page advice failed")
            require(result["madv_nohuge_order_rc"] == 0, "order page advice failed")
            require_recomputed_timing(result)
            if case == "primary":
                require(not saw_aa, "primary row appears after A/A controls")
                require(distance in primary_distances, "unexpected distance")
                if distance != current_distance:
                    if current_distance is not None:
                        completed_distances.add(current_distance)
                    require(distance not in completed_distances, "distance rows are not contiguous")
                    distance_order.append(distance)
                    current_distance = distance
                expected_mode = "demand" if label == "A" else "prefetch"
                expected_distance = 0 if label == "A" else distance
                require(1 <= block <= primary_blocks, "primary block out of range")
            else:
                saw_aa = True
                require(distance == 0 and 1 <= block <= aa_blocks, "A/A block mismatch")
                expected_mode = "demand"
                expected_distance = 0
            require(result["mode"] == expected_mode, "mode assignment mismatch")
            require(row["mode"] == expected_mode, "TSV mode assignment mismatch")
            require(result["distance"] == expected_distance, "distance echo mismatch")
            binary_hashes.add(row["binary_sha256"])
            pids.add(result["pid"])
            phases["init_seconds"].append(result["init_seconds"])
            phases["warmup_seconds"].append(result["warmup_seconds"])
            phases["timed_seconds"].append(result["elapsed_seconds"])
            grouped[(case, distance, block)][label].append(result["ns_per_access"])
            schedules[(case, distance, block)]["templates"].add(template)
            schedules[(case, distance, block)]["positions"].add(position)
            actual_schedule.append((case, distance, block, template, position, label))

    expected_rows = len(primary_distances) * primary_blocks * 4 + aa_blocks * 4
    # PID uniqueness is not required: the kernel may legally reuse a PID after
    # an earlier fresh process exits, and each row's TSV PID is already bound
    # to its process result above. The analysis comparison still reports the
    # recomputed unique-PID count.
    require(rows == expected_rows, "process count mismatch")
    require(len(binary_hashes) == 1, "campaign used multiple binary hashes")
    expected_rng = random.Random(campaign_seed)
    expected_distance_order = sorted(primary_distances)
    expected_rng.shuffle(expected_distance_order)
    require(distance_order == expected_distance_order, "distance order differs from seed")

    expected_schedule: list[tuple[str, int, int, str, int, str]] = []
    for distance in expected_distance_order:
        templates = ["ABBA"] * (primary_blocks // 2) + ["BAAB"] * (
            primary_blocks // 2
        )
        expected_rng.shuffle(templates)
        for block, template in enumerate(templates, 1):
            for position, label in enumerate(template, 1):
                expected_schedule.append(
                    ("primary", distance, block, template, position, label)
                )
    aa_templates = ["ABBA"] * (aa_blocks // 2) + ["BAAB"] * (aa_blocks // 2)
    expected_rng.shuffle(aa_templates)
    for block, template in enumerate(aa_templates, 1):
        for position, label in enumerate(template, 1):
            expected_schedule.append(("aa", 0, block, template, position, label))
    require(actual_schedule == expected_schedule, "campaign row schedule differs from seed")

    template_counts: dict[tuple[str, int], dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for (case, distance, _block), schedule in schedules.items():
        require(len(schedule["templates"]) == 1, "block used multiple templates")
        require(schedule["positions"] == {1, 2, 3, 4}, "block positions differ")
        template = next(iter(schedule["templates"]))
        require(isinstance(template, str), "template type differs")
        template_counts[(case, distance)][template] += 1
    for (case, distance), counts in template_counts.items():
        expected_blocks = primary_blocks if case == "primary" else aa_blocks
        require(
            counts == {"ABBA": expected_blocks // 2, "BAAB": expected_blocks // 2},
            f"template balance differs: {case} distance {distance}",
        )

    summaries = []
    block_details = []
    for (case, distance, block), labels in sorted(grouped.items()):
        require(len(labels["A"]) == 2 and len(labels["B"]) == 2, "incomplete block")
        mean_a = statistics.fmean(math.log(value) for value in labels["A"])
        mean_b = statistics.fmean(math.log(value) for value in labels["B"])
        contrast = mean_b - mean_a
        block_details.append(
            {
                "case": case,
                "distance": distance,
                "block": block,
                "a_ns_per_access_geomean": math.exp(mean_a),
                "b_ns_per_access_geomean": math.exp(mean_b),
                "b_over_a": math.exp(contrast),
            }
        )

    by_case: dict[tuple[str, int], list[float]] = defaultdict(list)
    for detail in block_details:
        by_case[(str(detail["case"]), int(detail["distance"]))].append(
            math.log(float(detail["b_over_a"]))
        )
    for (case, distance), values in sorted(by_case.items()):
        value = {"case": case, "distance": distance}
        value.update(summarize(values))
        summaries.append(value)

    phase_summary = {
        phase: {"min": min(values), "median": statistics.median(values), "max": max(values)}
        for phase, values in sorted(phases.items())
    }
    expected_analysis = {
        "schema": 1,
        "input": path.name,
        "rows": rows,
        "unique_pids": len(pids),
        "binary_sha256": next(iter(binary_hashes)),
        "timed_fault_totals": {"minor": 0, "major": 0},
        "cpu_migrations": 0,
        "madv_nohuge_failures": 0,
        "phase_summary": phase_summary,
        "summary": summaries,
        "blocks": block_details,
        "interval_note": (
            "Two-sided 95% Student-t interval over complete-block log ratios; "
            "descriptive for this host, binary, workload, and run window only."
        ),
    }
    close(json.loads(analysis_path.read_text()), expected_analysis)
    return {"rows": rows, "binary_sha256": next(iter(binary_hashes))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument(
        "--expected-source-archive-sha256",
        required=True,
        help=(
            "trusted digest of source-archive.tar.gz obtained out of band, "
            "for example from the published measurement page; archive PAX "
            "metadata alone does not authenticate the commit"
        ),
    )
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--expected-uname-machine", required=True)
    parser.add_argument(
        "--objdump",
        help=(
            "disassembler used to regenerate kernel disassembly from the "
            "retained binary; omit when no tool for the receipt's "
            "architecture is available, which limits the codegen check to "
            "the recorded text"
        ),
    )
    args = parser.parse_args()
    receipt = args.receipt.resolve()

    for name in REQUIRED:
        require((receipt / name).is_file(), f"missing receipt file: {name}")
    # The executed-source record stays outside the manifest: its integrity
    # comes from matching the sealed archive digests below, and the manifest
    # membership check must keep equating SHA256SUMS with REQUIRED.
    require(
        (receipt / "execution-sources.sha256").is_file(),
        "missing receipt file: execution-sources.sha256",
    )
    hashes = recorded_hashes(receipt / "SHA256SUMS")
    require(set(hashes) == set(REQUIRED) - {"SHA256SUMS"}, "manifest membership differs")
    for name, digest in hashes.items():
        require(sha256(receipt / name) == digest, f"digest mismatch: {name}")
    host_text = (receipt / "host.txt").read_text()
    require(
        host_field_present(host_text, "hostname", args.expected_hostname),
        "host identity differs: hostname",
    )
    require(
        host_field_present(host_text, "uname_machine", args.expected_uname_machine),
        "host identity differs: uname machine",
    )
    # Every distance-to-bytes translation in the experiment assumes 64-byte
    # records on 64-byte cache lines.
    require(
        host_field_present(host_text, "line_size", str(LINE_BYTES)),
        "host cache line size is not the frozen 64 bytes",
    )
    gcc_versions = GCC_VERSION_LINE.findall(host_text)
    require(
        bool(gcc_versions) and all(v == FROZEN_GCC_VERSION for v in gcc_versions),
        "compiler version differs from the frozen toolchain",
    )
    build_lines = (receipt / "build.txt").read_text().splitlines()
    require(bool(build_lines), "build record is empty")
    # Token-exact comparison: a substring test would accept extra
    # outcome-changing options appended to the frozen flags. The source
    # content itself is bound separately through the executed-source digests.
    # shlex handles the printf %q escaping run_host.sh applies to paths.
    try:
        build_tokens = shlex.split(build_lines[0])
    except ValueError:
        build_tokens = []
    frozen_flags = FROZEN_BUILD_FLAGS.split()
    require(
        len(build_tokens) == len(frozen_flags) + 4
        and build_tokens[0] == "gcc"
        and build_tokens[1 : 1 + len(frozen_flags)] == frozen_flags
        and Path(build_tokens[-3]).name == "prefetch_bench.c"
        and build_tokens[-2] == "-o"
        and Path(build_tokens[-1]).name == "prefetch_bench",
        "build command differs from the frozen flags",
    )
    require(
        (receipt / "source-commit.txt").read_text().strip() == args.expected_source_commit,
        "source commit differs",
    )
    source_hashes = recorded_hashes(receipt / "source-archive.sha256")
    require(
        source_hashes == {"source-archive.tar.gz": sha256(receipt / "source-archive.tar.gz")},
        "source archive digest record differs",
    )
    # The archive's PAX comment is writable by whoever packed the archive, so
    # commit authentication rests on this externally supplied trusted digest;
    # the PAX and prefix checks below remain as consistency checks only.
    require(
        source_hashes["source-archive.tar.gz"] == args.expected_source_archive_sha256,
        "source archive differs from the trusted digest",
    )
    binary_hashes = recorded_hashes(receipt / "binary.sha256")
    require(
        binary_hashes == {"prefetch_bench": sha256(receipt / "prefetch_bench")},
        "binary digest record differs",
    )
    expected_source_names = {
        "prefetch_bench.c",
        "run_campaign.py",
        "analyze.py",
        "validate_receipts.py",
    }
    source_hashes = recorded_hashes(receipt / "experiment-sources.sha256")
    require(set(source_hashes) == expected_source_names, "experiment source set differs")
    archive_prefix = f"systems-snackpack-{args.expected_source_commit}/"
    archive_path = receipt / "source-archive.tar.gz"
    with tarfile.open(archive_path, "r:gz") as archive:
        require(
            archive.pax_headers.get("comment") == args.expected_source_commit,
            "git archive commit header differs",
        )
        members = {member.name: member for member in archive.getmembers() if member.isfile()}
        require(
            bool(members) and all(name.startswith(archive_prefix) for name in members),
            "source archive prefix differs from commit",
        )
        archived_digests: dict[str, str] = {}
        for name in sorted(expected_source_names):
            member_name = (
                archive_prefix
                + "topics/048-hardware-software-prefetching/experiment/"
                + name
            )
            require(member_name in members, f"source archive missing {name}")
            stream = archive.extractfile(members[member_name])
            require(stream is not None, f"cannot read archived source: {name}")
            assert stream is not None
            archived_digests[name] = hashlib.sha256(stream.read()).hexdigest()
    for name, digest in source_hashes.items():
        require(archived_digests[name] == digest, f"source digest differs: {name}")
    executed_hashes = executed_source_hashes(receipt / "execution-sources.sha256")
    require(
        {"prefetch_bench.c", "run_campaign.py"} <= set(executed_hashes)
        and set(executed_hashes) <= expected_source_names,
        "executed source set differs",
    )
    for name, digest in executed_hashes.items():
        require(
            archived_digests[name] == digest,
            f"executed source differs from sealed archive: {name}",
        )
    validate_smoke(receipt / "smoke/demand.json", "demand")
    validate_smoke(receipt / "smoke/prefetch.json", "prefetch")
    symbols = (receipt / "codegen/symbols.txt").read_text()
    require("kernel_demand" in symbols and "kernel_prefetch" in symbols, "kernel symbols missing")
    demand_asm = (receipt / "codegen/kernel_demand.asm").read_text().lower()
    prefetch_asm = (receipt / "codegen/kernel_prefetch.asm").read_text().lower()
    require(HINT_INSTRUCTION.search(prefetch_asm) is not None, "linked prefetch hint missing")
    require(HINT_INSTRUCTION.search(demand_asm) is None, "demand kernel contains prefetch hint")
    # The recorded .asm text is only manifest-covered; regenerating from the
    # retained binary binds the hint evidence to the bytes that actually ran.
    codegen_binding = "recorded-text-only"
    if args.objdump:
        for kernel, expect_hint in (("kernel_demand", False), ("kernel_prefetch", True)):
            disassembly = subprocess.run(
                [
                    args.objdump,
                    "-drwC",
                    f"--disassemble={kernel}",
                    str(receipt / "prefetch_bench"),
                ],
                capture_output=True,
                text=True,
            )
            require(
                disassembly.returncode == 0,
                f"objdump failed for {kernel}: {disassembly.stderr.strip()}",
            )
            regenerated = disassembly.stdout.lower()
            require(f"<{kernel}>" in regenerated, f"regenerated disassembly missing {kernel}")
            require(
                (HINT_INSTRUCTION.search(regenerated) is not None) == expect_hint,
                f"binary hint evidence differs from recorded text: {kernel}",
            )
        codegen_binding = "regenerated-from-binary"

    random_result = validate_campaign(
        receipt / "random.tsv",
        receipt / "random-analysis.json",
        pattern="random",
        primary_distances={4, 8, 16, 32, 64},
        primary_blocks=4,
        aa_blocks=2,
        campaign_seed=480048,
    )
    sequential_result = validate_campaign(
        receipt / "sequential.tsv",
        receipt / "sequential-analysis.json",
        pattern="sequential",
        primary_distances={16},
        primary_blocks=2,
        aa_blocks=2,
        campaign_seed=480049,
    )
    require(
        random_result["binary_sha256"] == sequential_result["binary_sha256"],
        "campaign binary hashes differ",
    )
    require(
        random_result["binary_sha256"] == sha256(receipt / "prefetch_bench"),
        "recorded binary hash differs from file",
    )
    print(
        json.dumps(
            {
                "schema": 1,
                "valid": True,
                "source_commit": args.expected_source_commit,
                "hostname": args.expected_hostname,
                "uname_machine": args.expected_uname_machine,
                "codegen_binding": codegen_binding,
                "random_rows": random_result["rows"],
                "sequential_rows": sequential_result["rows"],
                "binary_sha256": random_result["binary_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
