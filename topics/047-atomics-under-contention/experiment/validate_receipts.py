#!/usr/bin/env python3
"""Validate and independently recompute source-bound Topic 47 receipts."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import random
import re
import statistics
import subprocess
import tarfile
from pathlib import Path, PurePosixPath


THREADS = 8
ITERATIONS = 2_000_000
WARMUP_ITERATIONS = 100_000
BATCH_SIZE = 256
COORDINATOR_CPU = 8
WORKER_CPUS = list(range(8))
BLOCKS = 12
AA_BLOCKS = 4
SEED = 20260826
TIMEOUT_SECONDS = 120.0
BOOTSTRAP_DRAWS = 20_000
MODES = ("shared", "cas", "striped", "batched")
MODE_BY_LABEL = dict(zip("ABCD", MODES))
WILLIAMS_TEMPLATES = ("ABDC", "BCAD", "CDBA", "DACB")
PRIMARY_PAIRS = (("cas", "shared"), ("striped", "shared"), ("batched", "shared"))
RECORDED_BINARY = "binary/atomic_contention"
RUNNER_PATH = "topics/047-atomics-under-contention/experiment/run_processes.py"
RESULT_KEYS = {
    "schema", "label", "mode", "threads", "iterations_per_thread",
    "warmup_iterations_per_thread", "batch_size", "logical_ops",
    "rmw_attempts", "cas_retries", "final_count", "correct", "affinity_ok",
    "startup_ns", "warmup_ns", "steady_ns", "teardown_ns", "total_ns",
    "coordinator_cpu", "worker_cpus", "worker_start_cpus", "worker_end_cpus",
    "stripe_alignment",
}
PROBE_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PATH": os.defpath, "TZ": "UTC"}
SYMBOLS = (
    "topic47_shared_fetch_add",
    "topic47_cas_increment",
    "topic47_striped_fetch_add",
    "topic47_batched_fetch_add",
)
REQUIRED = (
    "source-archive.tar.gz",
    "source-manifest-before.sha256",
    "source-manifest-after.sha256",
    "source-manifest.diff",
    "host.txt",
    "correctness.txt",
    "build.txt",
    "binary.sha256",
    "binary/atomic_contention",
    *(f"smoke/{mode}.{suffix}" for mode in MODES for suffix in ("json", "stderr", "status")),
    "codegen/all.asm",
    "codegen/symbols.txt",
    "codegen/symbol-addresses.json",
    "codegen/topic47_shared_fetch_add.asm",
    "codegen/topic47_cas_increment.asm",
    "codegen/topic47_striped_fetch_add.asm",
    "codegen/topic47_batched_fetch_add.asm",
    "codegen/codegen-check.json",
    "codegen/sha256sums.txt",
    "run-processes.txt",
    "experiment/metadata.json",
    "experiment/attempts.jsonl",
    "experiment/summary.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt_dir", type=Path)
    parser.add_argument("--expected-label", required=True)
    parser.add_argument("--expected-resolved-host", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def key_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("["):
            break
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not key.replace("_", "").isalnum():
            continue
        require(key not in values, f"duplicate host field: {key}")
        values[key] = value
    return values


def recorded_manifest(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        require(not line.startswith("\\"), f"manifest uses escaped names: {path}")
        digest, separator, name = line.partition("  ")
        require(bool(separator) and len(digest) == 64 and name not in values, f"malformed manifest line: {line}")
        values[name] = digest
    return values


def archive_file_digests(path: Path, expected_commit: str) -> dict[str, str]:
    digests = {}
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        declared = archive.pax_headers.get("comment")
        if declared is None:
            declared = next(
                (member.pax_headers.get("comment") for member in members if member.pax_headers.get("comment")),
                None,
            )
        require(declared == expected_commit, "archive embedded commit mismatch")
        names = set()
        normalized_names = set()
        roots = set()
        for member in members:
            member_path = PurePosixPath(member.name)
            normalized = str(member_path)
            require(
                member.name not in names
                and normalized not in normalized_names
                and not member_path.is_absolute()
                and ".." not in member_path.parts
                and (member.isdir() or member.isfile()),
                f"unsafe or duplicate archive member: {member.name}",
            )
            names.add(member.name)
            normalized_names.add(normalized)
            if member_path.parts:
                roots.add(member_path.parts[0])
        require(len(roots) == 1, "archive must contain one top-level root")
        for member in members:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            require(len(parts) >= 2, f"file outside archive root: {member.name}")
            source = archive.extractfile(member)
            require(source is not None, f"unreadable archive member: {member.name}")
            digest = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
            relative = "/".join(parts[1:])
            require(relative not in digests, f"duplicate relative archive path: {relative}")
            digests[relative] = digest.hexdigest()
    return digests


def parse_cpu_list(value: str) -> set[int]:
    value = value.rsplit(":", 1)[-1].strip()
    cpus = set()
    for part in value.split(","):
        if not part:
            continue
        if "-" in part:
            first, last = map(int, part.split("-", 1))
            cpus.update(range(first, last + 1))
        else:
            cpus.add(int(part))
    return cpus


def make_schedule() -> list[dict]:
    rng = random.Random(SEED)
    primary = []
    for cycle in range(1, BLOCKS // 4 + 1):
        for template in WILLIAMS_TEMPLATES:
            primary.append({
                "kind": "primary",
                "block": f"primary-{cycle:02d}-{template}",
                "cycle": cycle,
                "template": template,
                "order": [MODE_BY_LABEL[label] for label in template],
            })
    rng.shuffle(primary)
    aa_templates = ["ABBA"] * (AA_BLOCKS // 2) + ["BAAB"] * (AA_BLOCKS // 2)
    rng.shuffle(aa_templates)
    aa = [
        {
            "kind": "aa",
            "block": f"aa-{index:02d}",
            "template": template,
            "order": ["shared"] * 4,
        }
        for index, template in enumerate(aa_templates, 1)
    ]
    schedule = primary + aa
    rng.shuffle(schedule)
    return schedule


def integer(value: object) -> bool:
    return type(value) is int


def exact_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            exact_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exact_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(text: str) -> object:
    return json.loads(text, object_pairs_hook=reject_duplicate_keys)


def strict_result(
    result: object,
    mode: str,
    label: str,
    iterations: int,
    warmup_iterations: int,
) -> bool:
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        return False
    logical_ops = THREADS * iterations
    expected = {
        "schema": "atomics-contention.v1",
        "label": label,
        "mode": mode,
        "threads": THREADS,
        "iterations_per_thread": iterations,
        "warmup_iterations_per_thread": warmup_iterations,
        "batch_size": BATCH_SIZE,
        "logical_ops": logical_ops,
        "final_count": logical_ops,
        "correct": True,
        "affinity_ok": True,
        "coordinator_cpu": COORDINATOR_CPU,
        "worker_cpus": WORKER_CPUS,
        "worker_start_cpus": WORKER_CPUS,
        "worker_end_cpus": WORKER_CPUS,
        "stripe_alignment": 128,
    }
    if not exact_equal({key: result.get(key) for key in expected}, expected):
        return False
    counts = ("logical_ops", "rmw_attempts", "cas_retries", "final_count")
    phases = ("startup_ns", "warmup_ns", "steady_ns", "teardown_ns", "total_ns")
    if any(not integer(result.get(key)) or result[key] < 0 for key in counts + phases):
        return False
    if result["total_ns"] != sum(result[key] for key in phases[:-1]):
        return False
    if mode == "cas":
        return result["rmw_attempts"] == logical_ops + result["cas_retries"]
    if result["cas_retries"] != 0:
        return False
    if mode in ("shared", "striped"):
        return result["rmw_attempts"] == logical_ops
    if mode == "batched":
        return result["rmw_attempts"] == THREADS * math.ceil(iterations / BATCH_SIZE)
    return False


def parse_stdout(stdout: object) -> object:
    if not isinstance(stdout, str):
        return None
    lines = stdout.splitlines()
    if len(lines) != 1:
        return None
    try:
        return strict_json(lines[0])
    except (json.JSONDecodeError, ValueError):
        return None


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    location = probability * (len(ordered) - 1)
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return ordered[lower]
    weight = location - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_contrasts(values: list[float], seed: int) -> dict:
    require(len(values) >= 2, "too few complete block contrasts")
    mean_log = statistics.fmean(values)
    standard_deviation = statistics.stdev(values)
    rng = random.Random(seed)
    bootstrap = [
        math.exp(statistics.fmean(rng.choice(values) for _ in values))
        for _ in range(BOOTSTRAP_DRAWS)
    ]
    return {
        "complete_blocks": len(values),
        "estimable": True,
        "geometric_mean_ratio": math.exp(mean_log),
        "log_contrast_mean": mean_log,
        "log_contrast_sd": standard_deviation,
        "multiplicative_sd": math.exp(standard_deviation),
        "min_block_ratio": math.exp(min(values)),
        "max_block_ratio": math.exp(max(values)),
        "bootstrap_95pct_ratio": [percentile(bootstrap, 0.025), percentile(bootstrap, 0.975)],
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "interval_scope": (
            "descriptive percentile bootstrap over complete process-level blocks "
            "from this host, binary, placement, and run window"
        ),
    }


def mode_summary(records: list[dict], mode: str) -> dict:
    selected = [record for record in records if record["kind"] == "primary" and record["mode"] == mode]
    output = {"process_runs": len(selected)}
    for field in ("startup_ns", "warmup_ns", "steady_ns", "teardown_ns", "total_ns"):
        values = [record["result"][field] for record in selected]
        output[f"{field}_median"] = statistics.median(values)
        output[f"{field}_min"] = min(values)
        output[f"{field}_max"] = max(values)
    output["steady_ns_per_logical_op_median"] = statistics.median(
        record["result"]["steady_ns"] / record["result"]["logical_ops"] for record in selected
    )
    output["rmw_attempts_per_logical_op_median"] = statistics.median(
        record["result"]["rmw_attempts"] / record["result"]["logical_ops"] for record in selected
    )
    if mode == "cas":
        retry_rates = [record["result"]["cas_retries"] / record["result"]["logical_ops"] for record in selected]
        output.update({
            "cas_retry_rate_median": statistics.median(retry_rates),
            "cas_retry_rate_min": min(retry_rates),
            "cas_retry_rate_max": max(retry_rates),
            "cas_retries_total": sum(record["result"]["cas_retries"] for record in selected),
        })
    return output


def close_tree(actual: object, expected: object, path: str = "summary") -> None:
    if isinstance(expected, float):
        require(
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12),
            f"{path} differs from raw recomputation",
        )
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"{path} keys differ")
        for key, value in expected.items():
            close_tree(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"{path} length differs")
        for index, value in enumerate(expected):
            close_tree(actual[index], value, f"{path}[{index}]")
    else:
        require(
            type(actual) is type(expected) and actual == expected,
            f"{path} differs from raw recomputation",
        )


def linked_symbol_addresses(symbol_table: str) -> dict[str, int]:
    addresses = {}
    for line in symbol_table.splitlines():
        match = re.match(r"^([0-9a-f]+)\s+\S\s+(.+)$", line.strip())
        if match and match.group(2) in SYMBOLS:
            addresses[match.group(2)] = int(match.group(1), 16)
    return addresses


def function_body_at_address(disassembly: str, address: int) -> tuple[str, str] | None:
    lines = disassembly.splitlines()
    headers = []
    for index, line in enumerate(lines):
        match = re.match(r"^([0-9a-f]+) <(.+)>:$", line.strip())
        if match:
            headers.append((index, int(match.group(1), 16), match.group(2)))
    header_index = next(
        (position for position, (_, candidate, _) in enumerate(headers) if candidate == address),
        None,
    )
    if header_index is None:
        return None
    start, _, label = headers[header_index]
    end = headers[header_index + 1][0] if header_index + 1 < len(headers) else len(lines)
    return "\n".join(lines[start:end]) + "\n", label


def normalized_disassembly(text: str) -> str:
    """Replace the input path in objdump's file-format header with a fixed name.

    objdump prints the path it was invoked with on the first header line, so a
    receipt archive extracted at a different root would fail an exact
    comparison against a fresh disassembly of an unchanged binary. Normalizing
    the header on both sides keeps every instruction byte in the comparison
    while letting a relocated archive revalidate.
    """
    return re.sub(
        r"^.+:(\s+file format\s+\S+)$",
        r"atomic_contention:\1",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def validate_codegen(root: Path, architecture: str) -> None:
    binary = root / "binary/atomic_contention"
    try:
        disassembly = subprocess.run(
            ["objdump", "-d", "-C", "--no-show-raw-insn", str(binary)],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        ).stdout
        symbols = subprocess.run(
            ["nm", "-n", "-C", "--defined-only", str(binary)],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f"cannot inspect retained linked binary: {error!r}") from error
    require(
        normalized_disassembly((root / "codegen/all.asm").read_text())
        == normalized_disassembly(disassembly),
        "retained full disassembly differs from binary",
    )
    require((root / "codegen/symbols.txt").read_text() == symbols, "retained symbol table differs from binary")
    addresses = linked_symbol_addresses(symbols)
    require(set(addresses) == set(SYMBOLS), "linked image lacks a stable kernel symbol")
    bodies = {}
    expected_mapping = {}
    for symbol in SYMBOLS:
        body_and_label = function_body_at_address(disassembly, addresses[symbol])
        require(body_and_label is not None, f"linked image lacks a body for {symbol}")
        body, label = body_and_label
        require((root / f"codegen/{symbol}.asm").read_text() == body, f"retained {symbol} body differs")
        bodies[symbol] = body
        expected_mapping[symbol] = {
            "address": f"0x{addresses[symbol]:x}",
            "disassembly_label": label,
        }
    require(
        exact_equal(
            strict_json((root / "codegen/symbol-addresses.json").read_text()),
            expected_mapping,
        ),
        "stable symbol-address mapping differs from linked image",
    )
    if architecture == "x86_64":
        add_pattern = r"\block\b.*\b(inc|add|xadd)"
        cas_pattern = r"\block\b.*\bcmpxchg"
    elif architecture in ("aarch64", "arm64"):
        add_direct = r"\b(?:(?:ldadd|stadd)[a-z]*\b|__aarch64_ldadd)"
        cas_direct = r"\b(?:cas(?:a|l|al)?\b|__aarch64_cas)"
        exclusive_load = r"\b(ldxr|ldaxr)\b"
        exclusive_store = r"\b(stxr|stlxr)\b"
    else:
        raise SystemExit(f"unsupported architecture: {architecture}")
    if architecture == "x86_64":
        for symbol in (SYMBOLS[0], SYMBOLS[2], SYMBOLS[3]):
            require(re.search(add_pattern, bodies[symbol]) is not None, f"{symbol} lacks atomic add lowering")
        require(re.search(cas_pattern, bodies[SYMBOLS[1]]) is not None, "CAS kernel lacks CAS lowering")
    else:
        for symbol in (SYMBOLS[0], SYMBOLS[2], SYMBOLS[3]):
            body = bodies[symbol]
            direct = re.search(add_direct, body) is not None
            exclusive_pair = (
                re.search(exclusive_load, body) is not None
                and re.search(exclusive_store, body) is not None
            )
            require(direct or exclusive_pair, f"{symbol} lacks a complete atomic-add lowering")
        cas_body = bodies[SYMBOLS[1]]
        direct_cas = re.search(cas_direct, cas_body) is not None
        cas_exclusive_pair = (
            re.search(exclusive_load, cas_body) is not None
            and re.search(exclusive_store, cas_body) is not None
        )
        require(direct_cas or cas_exclusive_pair, "CAS kernel lacks a complete CAS lowering")
    expected_codegen = {"status": "PASS", "architecture": architecture, "symbols_checked": 4}
    require(
        exact_equal(strict_json((root / "codegen/codegen-check.json").read_text()), expected_codegen),
        "codegen check receipt mismatch",
    )
    manifest = recorded_manifest(root / "codegen/sha256sums.txt")
    expected_paths = {
        "codegen/all.asm",
        "codegen/symbols.txt",
        "codegen/symbol-addresses.json",
        *(f"codegen/{symbol}.asm" for symbol in SYMBOLS),
    }
    require(set(manifest) == expected_paths, "codegen digest manifest has the wrong paths")
    for relative, digest in manifest.items():
        require(sha256(root / relative) == digest, f"codegen digest mismatch: {relative}")


def main() -> None:
    args = parse_args()
    root = args.receipt_dir.resolve()
    output = args.output.resolve()
    require(root.is_dir(), "receipt directory does not exist")
    require(not output.exists(), "validation output already exists")
    for relative in REQUIRED:
        require((root / relative).is_file(), f"missing receipt: {relative}")

    host_text = (root / "host.txt").read_text(errors="replace")
    for marker in ("[uname]", "[lscpu]", "[lscpu-topology]", "[rustc]", "[cargo]", "[gcc]", "[python]", "[objdump]", "[nm]", "[timeout]", "[rustc-native-cfg]", "[rustc-target-features]", "[end-host]"):
        require(marker in host_text, f"host receipt lacks section {marker}")
    host = key_values(root / "host.txt")
    expected_host = {
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_archive_sha256,
        "ssh_target_label": args.expected_label,
        "ssh_resolved_hostname": args.expected_resolved_host,
        "runtime_hostname": args.expected_resolved_host,
        "architecture": args.expected_architecture,
        "threads": str(THREADS),
        "coordinator_cpu": str(COORDINATOR_CPU),
        "worker_cpus": ",".join(map(str, WORKER_CPUS)),
        "iterations_per_thread": str(ITERATIONS),
        "warmup_iterations_per_thread": str(WARMUP_ITERATIONS),
        "batch_size": str(BATCH_SIZE),
        "blocks": str(BLOCKS),
        "aa_blocks": str(AA_BLOCKS),
        "seed": str(SEED),
        "process_timeout_seconds": "120",
    }
    require(all(host.get(key) == value for key, value in expected_host.items()), "host identity or protocol mismatch")
    require(host.get("kernel_release"), "kernel release missing")
    require(int(host.get("available_cpu_count", "0")) >= 9, "too few available CPUs")
    require(set(WORKER_CPUS + [COORDINATOR_CPU]) <= parse_cpu_list(host.get("allowed_affinity", "")), "recorded affinity excludes a publication CPU")
    locations = set()
    packages = set()
    nodes = set()
    for cpu in WORKER_CPUS + [COORDINATOR_CPU]:
        core = host.get(f"cpu_{cpu}_core_id")
        package = host.get(f"cpu_{cpu}_package_id")
        node = host.get(f"cpu_{cpu}_node")
        require(all(value is not None and value.isdigit() for value in (core, package, node)), f"cpu{cpu} topology missing")
        locations.add((package, core))
        packages.add(package)
        nodes.add(node)
        sizes = {int(value) for value in host.get(f"cpu_{cpu}_coherence_line_sizes", "").split(",") if value}
        require(bool(sizes) and all(size > 0 and 128 % size == 0 for size in sizes), f"cpu{cpu} line size is incompatible with 128-byte stripes")
        siblings = parse_cpu_list(host.get(f"cpu_{cpu}_thread_siblings", ""))
        require(not (siblings - {cpu}) & set(WORKER_CPUS + [COORDINATOR_CPU]), f"cpu{cpu} shares a physical core")
    require(len(locations) == 9 and len(packages) == 1 and len(nodes) == 1, "publication placement is not nine distinct cores in one socket and NUMA node")
    if args.expected_label == "xxl":
        require(args.expected_architecture == "x86_64", "xxl receipt is not x86-64")
    else:
        require(
            args.expected_label == "dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com"
            and args.expected_resolved_host == args.expected_label
            and args.expected_architecture in ("aarch64", "arm64"),
            "receipt is not from an authorized Topic 47 target",
        )

    archive = root / "source-archive.tar.gz"
    require(sha256(archive) == args.expected_archive_sha256, "archive digest mismatch")
    archived = archive_file_digests(archive, args.expected_source_commit)
    before = recorded_manifest(root / "source-manifest-before.sha256")
    after = recorded_manifest(root / "source-manifest-after.sha256")
    require(before == after == archived, "source manifest does not match unchanged authenticated archive")
    require((root / "source-manifest.diff").read_bytes() == b"", "source manifest diff is not empty")
    require("CORRECTNESS_STATUS=pass" in (root / "correctness.txt").read_text(), "correctness gate failed")
    require("BUILD_STATUS=pass" in (root / "build.txt").read_text(), "release build gate failed")

    binary = root / "binary/atomic_contention"
    binary_digest = (root / "binary.sha256").read_text().split()[0]
    require(len(binary_digest) == 64 and sha256(binary) == binary_digest, "retained binary digest mismatch")
    validate_codegen(root, args.expected_architecture)
    for mode in MODES:
        smoke = strict_json((root / f"smoke/{mode}.json").read_text())
        require(strict_result(smoke, mode, f"smoke:{mode}", 10_000, 1_000), f"{mode} smoke result failed")
        smoke_status = key_values(root / f"smoke/{mode}.status")
        require(
            smoke_status == {"returncode": "0", "timed_out": "false", "timeout_seconds": "30"},
            f"{mode} smoke status failed",
        )
        require((root / f"smoke/{mode}.stderr").read_bytes() == b"", f"{mode} smoke wrote stderr")

    metadata = strict_json((root / "experiment/metadata.json").read_text())
    attempts = [strict_json(line) for line in (root / "experiment/attempts.jsonl").read_text().splitlines()]
    summary = strict_json((root / "experiment/summary.json").read_text())
    schedule = make_schedule()
    expected_metadata = {
        "threads": THREADS,
        "iterations_per_thread": ITERATIONS,
        "warmup_iterations_per_thread": WARMUP_ITERATIONS,
        "batch_size": BATCH_SIZE,
        "coordinator_cpu": COORDINATOR_CPU,
        "worker_cpus": WORKER_CPUS,
        "blocks": BLOCKS,
        "aa_blocks": AA_BLOCKS,
        "seed": SEED,
        "timeout_seconds": TIMEOUT_SECONDS,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "schedule": schedule,
        "analysis_unit": "one complete four-process Williams or A/A block",
        "subsamples": "workers and loop iterations inside one fresh process",
        "primary_estimands": [f"{a}_over_{b}" for a, b in PRIMARY_PAIRS],
        "timing_boundary": "steady_ns per logical operation; startup, warmup, and teardown excluded",
        "stopping_rule": "fixed schedule; no retries, replacement, peeking, or early stopping",
        "aa_scope": "mechanical label, parser, and position check; not a noise floor",
        "working_directory": "receipt-root",
    }
    require(
        exact_equal({key: metadata.get(key) for key in expected_metadata}, expected_metadata),
        "experiment metadata drifted",
    )
    recorded_output_dir = host.get("receipt_output_dir", "")
    require(
        recorded_output_dir.startswith("/")
        and os.path.normpath(recorded_output_dir) == recorded_output_dir,
        "recorded receipt output directory is not an absolute normalized path",
    )
    require(metadata.get("binary") == RECORDED_BINARY, "metadata binary is not receipt-root-relative")
    require(
        (root / metadata["binary"]).resolve(strict=True) == binary.resolve(strict=True),
        "metadata binary does not resolve to the retained binary",
    )
    require(metadata.get("binary_sha256") == binary_digest, "metadata binary digest mismatch")
    require(metadata.get("runner_sha256") == archived.get(RUNNER_PATH), "runner is not bound to archive")
    expected_attempts = 4 * (BLOCKS + AA_BLOCKS)
    require(len(attempts) == expected_attempts, "wrong retained attempt count")
    require(
        exact_equal(
            [record.get("attempt") for record in attempts],
            list(range(1, expected_attempts + 1)),
        ),
        "attempt sequence mismatch",
    )

    expected_rows = []
    for block in schedule:
        for position, (label, mode) in enumerate(zip(block["template"], block["order"]), 1):
            expected_rows.append((block, position, label, mode))
    primary_templates = collections.Counter(block["template"] for block in schedule if block["kind"] == "primary")
    require(primary_templates == collections.Counter({template: 3 for template in WILLIAMS_TEMPLATES}), "Williams templates are not balanced")
    position_counts = collections.Counter()
    transitions = collections.Counter()
    for block in schedule:
        if block["kind"] != "primary":
            continue
        for position, mode in enumerate(block["order"], 1):
            position_counts[(position, mode)] += 1
        transitions.update(zip(block["order"], block["order"][1:]))
    require(set(position_counts.values()) == {3} and len(position_counts) == 16, "treatment positions are not balanced")
    require(set(transitions.values()) == {3} and len(transitions) == 12, "directed first-order transitions are not balanced")

    for record, (block, position, label, mode) in zip(attempts, expected_rows):
        bench_label = f"{block['kind']}:{block['block']}:{label}"
        expected_command = [
            f"./{metadata['binary']}", mode, str(THREADS), str(ITERATIONS),
            str(WARMUP_ITERATIONS), str(BATCH_SIZE), str(COORDINATOR_CPU),
            ",".join(map(str, WORKER_CPUS)),
        ]
        environment = dict(PROBE_ENVIRONMENT)
        environment["BENCH_LABEL"] = bench_label
        expected_fields = {
            "kind": block["kind"], "block": block["block"],
            "cycle": block.get("cycle"), "template": block["template"],
            "position": position, "label": label, "bench_label": bench_label,
            "mode": mode, "command": expected_command,
            "environment": environment, "timeout_seconds": TIMEOUT_SECONDS,
        }
        require(
            exact_equal({key: record.get(key) for key in expected_fields}, expected_fields),
            f"attempt {record.get('attempt')} violates schedule",
        )
        result = record.get("result")
        protocol_valid = (
            type(record.get("returncode")) is int
            and record.get("returncode") == 0
            and record.get("timed_out") is False
            and "parse_error" not in record
            and parse_stdout(record.get("stdout")) == result
            and record.get("binary_sha256_before") == binary_digest
            and record.get("binary_sha256_after") == binary_digest
            and strict_result(result, mode, bench_label, ITERATIONS, WARMUP_ITERATIONS)
        )
        analysis_valid = protocol_valid and result["steady_ns"] > 0
        require(record.get("protocol_valid") == protocol_valid, f"attempt {record.get('attempt')} protocol flag mismatch")
        require(record.get("steady_analysis_valid") == analysis_valid, f"attempt {record.get('attempt')} analysis flag mismatch")
        require(record.get("valid") == analysis_valid and analysis_valid, f"attempt {record.get('attempt')} failed")
        require(type(record.get("protocol_valid")) is bool, "protocol flag is not Boolean")
        require(type(record.get("steady_analysis_valid")) is bool, "analysis flag is not Boolean")
        require(type(record.get("valid")) is bool, "valid flag is not Boolean")
        require(isinstance(record.get("stdout"), str) and isinstance(record.get("stderr"), str), "attempt output fields are not strings")
        require(record["stderr"] == "", f"attempt {record.get('attempt')} wrote stderr")
        require(
            integer(record.get("process_wall_ns"))
            and record["process_wall_ns"] >= result["total_ns"]
            and record["process_wall_ns"] > 0,
            "invalid parent wall-time envelope",
        )

    by_block = collections.defaultdict(list)
    for record in attempts:
        by_block[record["block"]].append(record)
    contrasts = {f"{a}_over_{b}": [] for a, b in PRIMARY_PAIRS}
    aa_values = []
    for block in schedule:
        records = by_block[block["block"]]
        require(len(records) == 4, f"incomplete block {block['block']}")
        if block["kind"] == "primary":
            by_mode = {record["mode"]: record for record in records}
            require(set(by_mode) == set(MODES), "primary block lacks a mode")
            for numerator, denominator in PRIMARY_PAIRS:
                numerator_value = by_mode[numerator]["result"]["steady_ns"] / by_mode[numerator]["result"]["logical_ops"]
                denominator_value = by_mode[denominator]["result"]["steady_ns"] / by_mode[denominator]["result"]["logical_ops"]
                contrasts[f"{numerator}_over_{denominator}"].append(math.log(numerator_value) - math.log(denominator_value))
        else:
            labels = {"A": [], "B": []}
            for record in records:
                labels[record["label"]].append(math.log(record["result"]["steady_ns"] / record["result"]["logical_ops"]))
            require(len(labels["A"]) == len(labels["B"]) == 2, "A/A label count mismatch")
            aa_values.append(statistics.fmean(labels["A"]) - statistics.fmean(labels["B"]))

    expected_pairs = {}
    for index, name in enumerate(sorted(contrasts)):
        expected_pairs[name] = summarize_contrasts(contrasts[name], SEED + index + 1)
        expected_pairs[name]["ratio_definition"] = (
            "numerator steady_ns per logical operation divided by shared steady_ns "
            "per logical operation within each complete Williams block"
        )
    expected_aa = summarize_contrasts(aa_values, SEED + 100)
    expected_aa["ratio_definition"] = (
        "shared label A steady_ns per logical operation divided by byte-identical "
        "shared label B within each complete ABBA or BAAB block"
    )
    expected_summary = {
        "attempts": expected_attempts,
        "protocol_invalid_attempts": [],
        "analysis_ineligible_attempts": [],
        "all_attempts_valid": True,
        "binary_sha256_before": binary_digest,
        "binary_sha256_after": binary_digest,
        "runner_sha256_before": metadata["runner_sha256"],
        "runner_sha256_after": metadata["runner_sha256"],
        "identity_unchanged": True,
        "invalid_blocks": [],
        "pairs": expected_pairs,
        "aa_shared_A_over_shared_B": expected_aa,
        "modes": {mode: mode_summary(attempts, mode) for mode in MODES},
    }
    close_tree(summary, expected_summary)
    require(
        (root / "run-processes.txt").read_text() == json.dumps(summary, indent=2) + "\n",
        "runner standard output differs from retained summary",
    )

    result = {
        "status": "PASS",
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_archive_sha256,
        "binary_sha256": binary_digest,
        "attempts": expected_attempts,
        "primary_blocks": BLOCKS,
        "aa_blocks": AA_BLOCKS,
        "primary_estimands": list(expected_pairs),
    }
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
