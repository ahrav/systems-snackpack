#!/usr/bin/env python3
"""Run paired fresh-process comparisons for the Topic 36 container kernels."""

import argparse
import hashlib
import os
import statistics
import subprocess
import sys
import time


CONTRASTS = (
    ("tiny16", "array", "bitmap"),
    ("sparse256", "array", "bitmap"),
    ("threshold4096", "array", "bitmap"),
    ("dense32768", "array", "bitmap"),
    ("runs64", "run", "bitmap"),
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run order-balanced process-level bitmap kernel comparisons."
    )
    parser.add_argument("--binary", required=True, help="Path to bitmap-probe")
    parser.add_argument("--blocks", type=int, default=12)
    parser.add_argument("--aa-blocks", type=int, default=4)
    parser.add_argument("--target-ms", type=int, default=200)
    return parser.parse_args()


def require_linux_affinity():
    if not hasattr(os, "sched_getaffinity") or not hasattr(os, "sched_setaffinity"):
        raise RuntimeError(
            "this harness requires Linux os.sched_getaffinity and os.sched_setaffinity"
        )
    available = sorted(os.sched_getaffinity(0))
    if not available:
        raise RuntimeError("the process has an empty CPU affinity set")
    cpu = available[0]
    os.sched_setaffinity(0, {cpu})
    return cpu


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_probe_row(line, expected_case, expected_method):
    fields = {}
    for part in line.split():
        if "=" not in part:
            raise RuntimeError(f"unparseable probe field {part!r} in {line!r}")
        key, value = part.split("=", 1)
        if key in fields:
            raise RuntimeError(f"duplicate probe field {key!r} in {line!r}")
        fields[key] = value
    if fields.get("CHECK") != "PASS":
        raise RuntimeError(f"probe did not report CHECK=PASS: {line!r}")
    if fields.get("CASE") != expected_case or fields.get("METHOD") != expected_method:
        raise RuntimeError(
            f"probe identity mismatch for {expected_case}/{expected_method}: {line!r}"
        )
    required = {"ITERS", "ELAPSED_NS", "NS_PER_OP", "COUNT", "CHECKSUM"}
    missing = required.difference(fields)
    if missing:
        raise RuntimeError(f"probe row omitted {sorted(missing)}: {line!r}")
    return fields


def invoke(binary, case, method, target_ms):
    command = [binary, "bench", case, method, str(target_ms)]
    wall_start = time.monotonic_ns()
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    external_wall_ns = time.monotonic_ns() - wall_start
    if completed.returncode != 0:
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise RuntimeError(
            f"probe exited {completed.returncode}: {' '.join(command)}"
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(
            f"probe emitted {len(lines)} non-empty stdout rows for {case}/{method}: "
            f"{completed.stdout!r}"
        )
    return parse_probe_row(lines[0], case, method), external_wall_ns


def quartiles(values):
    lower, _, upper = statistics.quantiles(sorted(values), n=4, method="inclusive")
    return lower, upper


def validate_arguments(args):
    args.binary = os.path.abspath(args.binary)
    if args.blocks < 2 or args.blocks % 2 != 0:
        raise ValueError(
            "--blocks must be an even count of at least 2 so the alternating AB "
            "schedule places each method first in exactly half the blocks"
        )
    if args.aa_blocks < 2:
        raise ValueError("--aa-blocks must be at least 2")
    if args.target_ms <= 0:
        raise ValueError("--target-ms must be greater than zero")
    if not os.path.isfile(args.binary):
        raise ValueError(f"--binary is not a regular file: {args.binary}")
    if not os.access(args.binary, os.X_OK):
        raise ValueError(f"--binary is not executable: {args.binary}")


def emit_raw(family, case, block, position, method, row, external_wall_ns):
    print(
        f"RAW FAMILY={family} CASE={case} BLOCK={block} POSITION={position} "
        f"METHOD={method} ITERS={row['ITERS']} ELAPSED_NS={row['ELAPSED_NS']} "
        f"NS_PER_OP={row['NS_PER_OP']} COUNT={row['COUNT']} "
        f"CHECKSUM={row['CHECKSUM']} EXTERNAL_WALL_NS={external_wall_ns} CHECK=PASS"
    )


def main():
    args = parse_arguments()
    validate_arguments(args)
    cpu = require_linux_affinity()
    binary_digest = sha256(args.binary)
    print(
        f"META CPU={cpu} BLOCKS={args.blocks} AA_BLOCKS={args.aa_blocks} "
        f"TARGET_MS={args.target_ms} BINARY_SHA256={binary_digest}"
    )

    ratios = {case: [] for case, _, _ in CONTRASTS}
    process_count = 0
    for case, candidate, baseline in CONTRASTS:
        for block in range(args.blocks):
            order = (candidate, baseline) if block % 2 == 0 else (baseline, candidate)
            rows = {}
            for position, method in enumerate(order):
                row, external_wall_ns = invoke(
                    args.binary, case, method, args.target_ms
                )
                process_count += 1
                rows[method] = row
                emit_raw(
                    "AB", case, block, position, method, row, external_wall_ns
                )
            ratios[case].append(
                float(rows[candidate]["NS_PER_OP"])
                / float(rows[baseline]["NS_PER_OP"])
            )

    aa_ratios = []
    for block in range(args.aa_blocks):
        pair = []
        for position in range(2):
            row, external_wall_ns = invoke(
                args.binary, "threshold4096", "bitmap", args.target_ms
            )
            process_count += 1
            pair.append(row)
            emit_raw(
                "AA",
                "threshold4096",
                block,
                position,
                "bitmap",
                row,
                external_wall_ns,
            )
        aa_ratios.append(
            float(pair[0]["NS_PER_OP"]) / float(pair[1]["NS_PER_OP"])
        )

    for case, candidate, baseline in CONTRASTS:
        values = ratios[case]
        lower, upper = quartiles(values)
        print(
            f"SUMMARY CASE={case} RATIO={candidate}/{baseline} "
            f"MEDIAN={statistics.median(values):.9f} Q1={lower:.9f} "
            f"Q3={upper:.9f} N={len(values)}"
        )
    lower, upper = quartiles(aa_ratios)
    print(
        "SUMMARY CASE=aa_bitmap RATIO=first/second "
        f"MEDIAN={statistics.median(aa_ratios):.9f} Q1={lower:.9f} "
        f"Q3={upper:.9f} N={len(aa_ratios)}"
    )
    print(
        f"CHECK=PASS BLOCKS={args.blocks} AA_BLOCKS={args.aa_blocks} "
        f"PROCESSES={process_count}"
    )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"run_processes.py: {error}", file=sys.stderr)
        raise SystemExit(2) from None
