#!/usr/bin/env python3
"""Validate source-bound Topic 46 Linux host receipts."""

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import tarfile
from pathlib import Path

# run_processes.py's fixed publication default; the publication runner never
# overrides it, so a receipt claiming any other draw count is not publishable.
PUBLICATION_BOOTSTRAP_DRAWS = 20_000
PUBLICATION_RUNNER_PATH = "topics/046-cache-coherence-false-sharing/experiment/run_processes.py"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt_dir")
    parser.add_argument("--expected-label", required=True)
    parser.add_argument("--expected-resolved-host", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-blocks", required=True, type=int)
    parser.add_argument("--expected-aa-blocks", required=True, type=int)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def key_values(path):
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values.setdefault(key, value)
    return values


def archive_file_digests(archive_path):
    digests = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit(f"unreadable archive member: {member.name}")
            reader = source
            digest = hashlib.sha256()
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                digest.update(chunk)
            # Manifest paths are relative to the repository root; strip the
            # single top-level archive directory prefix.
            digests["/".join(parts[1:])] = digest.hexdigest()
    return digests


def parse_cpu_list(value):
    cpus = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-", 1)
            cpus.update(range(int(first), int(last) + 1))
        else:
            cpus.add(int(part))
    return cpus


def recorded_manifest(path):
    values = {}
    for line in path.read_text().splitlines():
        if line.startswith("\\"):
            raise SystemExit(f"manifest uses escaped names: {path}")
        digest, separator, name = line.partition("  ")
        if not separator or name.endswith("/") or len(digest) != 64:
            raise SystemExit(f"malformed manifest line: {line}")
        values[name] = digest
    return values


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def templates(count, rng):
    result = ["ABBA"] * (count // 2) + ["BAAB"] * (count // 2)
    rng.shuffle(result)
    return result


def make_schedule(blocks, aa_blocks, seed):
    rng = random.Random(seed)
    schedule = []
    for index, template in enumerate(templates(blocks, rng), 1):
        schedule.append(
            {
                "pair": "packed_over_padded",
                "block": f"primary-{index:02d}",
                "template": template,
                "A": "packed",
                "B": "padded",
                "aa": False,
            }
        )
    for index, template in enumerate(templates(aa_blocks, rng), 1):
        schedule.append(
            {
                "pair": "padded_A_over_padded_B",
                "block": f"aa-{index:02d}",
                "template": template,
                "A": "padded",
                "B": "padded",
                "aa": True,
            }
        )
    rng.shuffle(schedule)
    return schedule


def expected_attempt_fields(schedule):
    fields = []
    for entry in schedule:
        for position, label in enumerate(entry["template"], 1):
            fields.append(
                {
                    "block": entry["block"],
                    "pair": entry["pair"],
                    "template": entry["template"],
                    "position": position,
                    "label": label,
                    "mode": entry[label],
                }
            )
    return fields


def strict_result(result, mode, iterations, cpu0, cpu1):
    expected = {
        "mode": mode,
        "iterations_per_thread": iterations,
        "cpu0": cpu0,
        "cpu1": cpu1,
        "first": iterations,
        "second": iterations,
        "address0_mod_128": 0,
        "slot_bytes": 128,
        "layout_ok": True,
        "affinity_ok": True,
        "correct": True,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        return False
    expected_delta = 8 if mode == "packed" else 128
    return (
        result.get("address_delta") == expected_delta
        and result.get("packed_size") == 128
        and result.get("padded_size") == 256
        and isinstance(result.get("elapsed_ns"), int)
        and not isinstance(result.get("elapsed_ns"), bool)
        and result["elapsed_ns"] > 0
        and result.get("start_cpu0") == cpu0
        and result.get("start_cpu1") == cpu1
        and result.get("end_cpu0") == cpu0
        and result.get("end_cpu1") == cpu1
    )


def reparsed_stdout_result(record):
    stdout = record.get("stdout")
    if not isinstance(stdout, str):
        return None
    lines = stdout.splitlines()
    if len(lines) != 1:
        return None
    try:
        value = json.loads(lines[0])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def recomputed_validity(record, iterations, cpu0, cpu1):
    result = record.get("result")
    return (
        record.get("returncode") == 0
        and record.get("timed_out") is False
        and "parse_error" not in record
        and isinstance(result, dict)
        and reparsed_stdout_result(record) == result
        and strict_result(result, record.get("mode"), iterations, cpu0, cpu1)
    )


def percentile(values, probability):
    ordered = sorted(values)
    location = probability * (len(ordered) - 1)
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return ordered[lower]
    weight = location - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(contrasts, seed, draws):
    if len(contrasts) < 2:
        return {"complete_blocks": len(contrasts), "estimable": False}
    mean_log = statistics.fmean(contrasts)
    rng = random.Random(seed)
    bootstrap = [
        math.exp(statistics.fmean(rng.choice(contrasts) for _ in contrasts))
        for _ in range(draws)
    ]
    return {
        "complete_blocks": len(contrasts),
        "estimable": True,
        "geometric_mean_ratio": math.exp(mean_log),
        "median_block_ratio": math.exp(statistics.median(contrasts)),
        "log_contrast_sd": statistics.stdev(contrasts),
        "min_block_ratio": math.exp(min(contrasts)),
        "max_block_ratio": math.exp(max(contrasts)),
        "bootstrap_95pct_ratio": [
            percentile(bootstrap, 0.025),
            percentile(bootstrap, 0.975),
        ],
        "bootstrap_draws": draws,
    }


def close_enough(recomputed, published):
    if set(recomputed) != set(published):
        return False
    for key, value in recomputed.items():
        other = published[key]
        if isinstance(value, float):
            if not (
                isinstance(other, (int, float))
                and math.isclose(value, other, rel_tol=1e-9, abs_tol=1e-12)
            ):
                return False
        elif isinstance(value, list):
            if not (
                isinstance(other, list)
                and len(value) == len(other)
                and all(
                    math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
                    for a, b in zip(value, other)
                )
            ):
                return False
        elif value != other:
            return False
    return True


def main():
    args = parse_args()
    root = Path(args.receipt_dir).resolve()
    output = Path(args.output).resolve()
    required = [
        "source-archive.tar.gz",
        "source-manifest-before.sha256",
        "source-manifest-after.sha256",
        "source-manifest.diff",
        "host.txt",
        "correctness.txt",
        "build.txt",
        "binary.sha256",
        "binary/cache_coherence_probe",
        "codegen-increment.txt",
        "codegen-check.txt",
        "smoke-packed.json",
        "smoke-padded.json",
        "experiment/metadata.json",
        "experiment/attempts.jsonl",
        "experiment/summary.json",
    ]
    for relative in required:
        require((root / relative).is_file(), f"missing receipt: {relative}")

    host = key_values(root / "host.txt")
    expected_host = {
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_archive_sha256,
        "ssh_target_label": args.expected_label,
        "ssh_resolved_hostname": args.expected_resolved_host,
        "runtime_hostname": args.expected_resolved_host,
        "architecture": args.expected_architecture,
        "blocks": str(args.expected_blocks),
        "aa_blocks": str(args.expected_aa_blocks),
    }
    require(all(host.get(key) == value for key, value in expected_host.items()), "host identity mismatch")
    line_entries = (host.get("coherence_line_sizes") or "").split()
    observed_sizes = set()
    for entry in line_entries:
        path, separator, value = entry.rpartition(":")
        if not separator or not path.endswith("coherency_line_size"):
            raise SystemExit(f"malformed coherence line entry: {entry}")
        observed_sizes.add(int(value))
    require(observed_sizes == {64}, f"coherence lines are not exactly 64 bytes: {sorted(observed_sizes)}")
    require(sha256(root / "source-archive.tar.gz") == args.expected_archive_sha256, "archive digest mismatch")
    require((root / "source-manifest-before.sha256").read_bytes() == (root / "source-manifest-after.sha256").read_bytes(), "source changed during run")
    require((root / "source-manifest.diff").read_bytes() == b"", "source manifest diff is not empty")
    require(
        recorded_manifest(root / "source-manifest-before.sha256") == archive_file_digests(root / "source-archive.tar.gz"),
        "source manifest does not describe the authenticated archive",
    )
    require("CORRECTNESS_STATUS=pass" in (root / "correctness.txt").read_text(), "correctness gate failed")
    require("BUILD_STATUS=pass" in (root / "build.txt").read_text(), "build gate failed")
    require("status=PASS" in (root / "codegen-check.txt").read_text(), "codegen check failed")
    increment_text = (root / "codegen-increment.txt").read_text()
    require("<topic46_increment>" in (root / "codegen.txt").read_text(), "missing increment symbol in retained disassembly")
    require("<topic46_increment>" in increment_text, "increment extract lacks the increment symbol")
    if args.expected_architecture == "x86_64":
        locked_rmw = re.search(r"\block\b.*\b(inc|add|xadd)", increment_text)
    elif args.expected_architecture in ("aarch64", "arm64"):
        locked_rmw = re.search(r"\b(ldadd|ldxr|ldaxr|stxr|stlxr|__aarch64_ldadd)", increment_text)
    else:
        raise SystemExit(f"unsupported architecture: {args.expected_architecture}")
    require(locked_rmw is not None, "retained disassembly lacks the architecture-specific atomic increment")

    smoke_packed = json.loads((root / "smoke-packed.json").read_text())
    smoke_padded = json.loads((root / "smoke-padded.json").read_text())
    require(smoke_packed.get("mode") == "packed" and smoke_packed.get("correct") is True, "packed smoke failed")
    require(smoke_padded.get("mode") == "padded" and smoke_padded.get("correct") is True, "padded smoke failed")

    metadata = json.loads((root / "experiment/metadata.json").read_text())
    attempts = [json.loads(line) for line in (root / "experiment/attempts.jsonl").read_text().splitlines()]
    summary = json.loads((root / "experiment/summary.json").read_text())
    expected_attempts = 4 * (args.expected_blocks + args.expected_aa_blocks)
    require(len(attempts) == expected_attempts, "wrong attempt count")
    require(all(record.get("valid") is True for record in attempts), "invalid attempt retained")
    require([record.get("attempt") for record in attempts] == list(range(1, expected_attempts + 1)), "attempt sequence mismatch")
    require(summary.get("attempts") == expected_attempts, "summary attempt count mismatch")
    require(summary.get("all_attempts_valid") is True and summary.get("invalid_blocks") == [], "summary reports invalid blocks")
    require(summary.get("identity_unchanged") is True, "runner or binary changed")
    require(
        summary.get("runner_sha256_before") == summary.get("runner_sha256_after"),
        "recorded runner digest changed during the run",
    )
    require(
        metadata.get("runner_sha256") == summary.get("runner_sha256_before"),
        "metadata and summary runner digests disagree",
    )
    require(
        archive_file_digests(root / "source-archive.tar.gz").get(PUBLICATION_RUNNER_PATH)
        == metadata.get("runner_sha256"),
        "archived runner does not match the recorded runner digest",
    )
    require(metadata.get("blocks") == args.expected_blocks and metadata.get("aa_blocks") == args.expected_aa_blocks, "metadata block count mismatch")

    core_values = (
        host.get("cpu0_core_id"),
        host.get("cpu1_core_id"),
        host.get("cpu0_package_id"),
        host.get("cpu1_package_id"),
    )
    require(all(value is not None and value.isdigit() for value in core_values), "missing or malformed recorded CPU topology")
    require(core_values[0] != core_values[1], "recorded CPUs share a physical core")
    require(core_values[2] == core_values[3], "recorded CPUs are in different packages")
    siblings0 = parse_cpu_list(host.get("cpu0_thread_siblings", ""))
    siblings1 = parse_cpu_list(host.get("cpu1_thread_siblings", ""))
    require(
        int(metadata.get("cpu1")) not in siblings0
        and int(metadata.get("cpu0")) not in siblings1,
        "recorded CPUs are simultaneous threads",
    )

    require(
        host.get("cpu0") == str(metadata.get("cpu0"))
        and host.get("cpu1") == str(metadata.get("cpu1")),
        "host and metadata CPU placement disagree",
    )

    primary = summary.get("pairs", {}).get("packed_over_padded", {})
    aa = summary.get("pairs", {}).get("padded_A_over_padded_B", {})
    require(primary.get("complete_blocks") == args.expected_blocks and primary.get("estimable") is True, "primary estimate incomplete")
    require(aa.get("complete_blocks") == args.expected_aa_blocks and aa.get("estimable") is True, "A/A estimate incomplete")

    iterations = metadata.get("iterations_per_thread")
    cpu0 = metadata.get("cpu0")
    cpu1 = metadata.get("cpu1")
    schedule = make_schedule(
        metadata.get("blocks"), metadata.get("aa_blocks"), metadata.get("seed")
    )
    require(
        metadata.get("schedule") == schedule,
        "metadata schedule does not match the regenerated fixed schedule",
    )
    expected_fields = expected_attempt_fields(schedule)
    require(len(attempts) == len(expected_fields), "attempt count differs from regenerated schedule")
    for record, expected in zip(attempts, expected_fields):
        require(
            all(record.get(key) == value for key, value in expected.items()),
            f"attempt {record.get('attempt')} deviates from the regenerated fixed schedule",
        )
    for record in attempts:
        record["valid"] = recomputed_validity(record, iterations, cpu0, cpu1)
    require(all(record["valid"] for record in attempts), "recomputed attempt validity failed")

    by_block = {}
    for record in attempts:
        by_block.setdefault(record.get("block"), []).append(record)
    # Contrast order must mirror run_processes.py (regenerated schedule order,
    # not sorted names): the bootstrap consumes one shared RNG stream over this
    # sequence. The regenerated schedule is used, never the serialized copy.
    contrasts = {pair: [] for pair in ("packed_over_padded", "padded_A_over_padded_B")}
    for entry in schedule:
        records = by_block.get(entry.get("block"), [])
        pair_name = entry.get("pair")
        if pair_name not in contrasts:
            continue
        if len(records) != 4 or not all(record["valid"] for record in records):
            continue
        if any(record.get("pair") != pair_name for record in records):
            continue
        by_label = {"A": [], "B": []}
        for record in records:
            by_label[record["label"]].append(math.log(record["result"]["elapsed_ns"]))
        if len(by_label["A"]) != 2 or len(by_label["B"]) != 2:
            continue
        contrasts[pair_name].append(
            statistics.fmean(by_label["A"]) - statistics.fmean(by_label["B"])
        )

    published_pairs = summary.get("pairs", {})
    require(set(published_pairs) == set(contrasts), "published pairs do not match the attempt stream")
    ordered_pairs = sorted(published_pairs)
    for index, pair_name in enumerate(ordered_pairs):
        values = contrasts[pair_name]
        bootstrap_draws = published_pairs[pair_name].get("bootstrap_draws")
        require(
            bootstrap_draws == PUBLICATION_BOOTSTRAP_DRAWS,
            f"{pair_name} does not use the fixed publication draw count",
        )
        metadata_seed = metadata.get("seed")
        require(isinstance(metadata_seed, int), "metadata seed missing")
        recomputed = summarize(values, metadata_seed + index + 1, bootstrap_draws)
        recomputed["interval_scope"] = (
            "descriptive percentile bootstrap over complete four-process blocks "
            "from this host, binary, CPU placement, and run window"
        )
        require(
            close_enough(recomputed, published_pairs[pair_name]),
            f"published {pair_name} statistics are not supported by attempts.jsonl",
        )

    binary_digest = (root / "binary.sha256").read_text().split()[0]
    require(binary_digest == metadata.get("binary_sha256"), "binary digest mismatch")
    require(
        sha256(root / "binary/cache_coherence_probe") == binary_digest,
        "retained binary does not match its recorded digest",
    )
    result = {
        "status": "PASS",
        "source_commit": args.expected_source_commit,
        "source_archive_sha256": args.expected_archive_sha256,
        "binary_sha256": binary_digest,
        "attempts": expected_attempts,
        "primary_blocks": args.expected_blocks,
        "aa_blocks": args.expected_aa_blocks,
    }
    output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
