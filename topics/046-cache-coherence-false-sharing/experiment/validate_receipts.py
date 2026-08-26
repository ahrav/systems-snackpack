#!/usr/bin/env python3
"""Validate source-bound Topic 46 Linux host receipts."""

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path


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


def require(condition, message):
    if not condition:
        raise SystemExit(message)


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
        and result["elapsed_ns"] > 0
        and result.get("start_cpu0") == cpu0
        and result.get("start_cpu1") == cpu1
        and result.get("end_cpu0") == cpu0
        and result.get("end_cpu1") == cpu1
    )


def recomputed_validity(record, iterations, cpu0, cpu1):
    result = record.get("result")
    return (
        record.get("returncode") == 0
        and record.get("timed_out") is False
        and "parse_error" not in record
        and isinstance(result, dict)
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
    require("/coherency_line_size:64" in host.get("coherence_line_sizes", ""), "missing 64-byte line evidence")
    require(sha256(root / "source-archive.tar.gz") == args.expected_archive_sha256, "archive digest mismatch")
    require((root / "source-manifest-before.sha256").read_bytes() == (root / "source-manifest-after.sha256").read_bytes(), "source changed during run")
    require((root / "source-manifest.diff").read_bytes() == b"", "source manifest diff is not empty")
    require("CORRECTNESS_STATUS=pass" in (root / "correctness.txt").read_text(), "correctness gate failed")
    require("BUILD_STATUS=pass" in (root / "build.txt").read_text(), "build gate failed")
    require("status=PASS" in (root / "codegen-check.txt").read_text(), "codegen check failed")

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
    require(metadata.get("blocks") == args.expected_blocks and metadata.get("aa_blocks") == args.expected_aa_blocks, "metadata block count mismatch")

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
    for record in attempts:
        record["valid"] = recomputed_validity(record, iterations, cpu0, cpu1)
    require(all(record["valid"] for record in attempts), "recomputed attempt validity failed")

    by_block = {}
    for record in attempts:
        by_block.setdefault(record.get("block"), []).append(record)
    # Contrast order must mirror run_processes.py (schedule order, not sorted
    # names): the bootstrap consumes one shared RNG stream over this sequence.
    contrasts = {pair: [] for pair in ("packed_over_padded", "padded_A_over_padded_B")}
    for entry in metadata.get("schedule", []):
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
            isinstance(bootstrap_draws, int) and bootstrap_draws > 0,
            f"missing bootstrap draws for {pair_name}",
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
