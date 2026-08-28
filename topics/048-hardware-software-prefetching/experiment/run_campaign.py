#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path


FIELDNAMES = [
    "campaign_seed",
    "case",
    "distance",
    "block",
    "template",
    "position",
    "label",
    "mode",
    "pid",
    "started_unix_ns",
    "binary_sha256",
    "returncode",
    "result_json",
    "stderr",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_distances(text: str):
    values = [int(item) for item in text.split(",") if item]
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("distances must be positive comma-separated integers")
    if len(set(values)) != len(values):
        raise argparse.ArgumentTypeError("distances must be unique")
    return values


def balanced_templates(blocks: int, rng: random.Random):
    if blocks <= 0 or blocks % 2 != 0:
        raise ValueError("blocks must be a positive even number")
    templates = ["ABBA"] * (blocks // 2) + ["BAAB"] * (blocks // 2)
    rng.shuffle(templates)
    return templates


def run_one(args, *, case, distance, block, template, position, label, mode,
            binary_hash, writer):
    command = []
    if args.cpu is not None:
        command.extend(["taskset", "-c", str(args.cpu)])
    command.extend(
        [
            str(args.binary),
            "--mode",
            mode,
            "--pattern",
            args.pattern,
            "--distance",
            str(distance if mode == "prefetch" else 0),
            "--mib",
            str(args.mib),
            "--passes",
            str(args.passes),
            "--warmup-passes",
            str(args.warmup_passes),
            "--seed",
            str(args.workload_seed),
        ]
    )
    started = time.time_ns()
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=args.process_timeout
        )
        returncode = completed.returncode
        result_text = completed.stdout.strip()
        stderr_text = completed.stderr.strip()
    except subprocess.TimeoutExpired as timeout_error:
        # The acceptance contract retains every timeout, so the attempt is
        # written before the campaign terminates.
        def captured_text(data: object) -> str:
            if isinstance(data, bytes):
                return data.decode(errors="replace").strip()
            return str(data).strip() if data else ""

        returncode = 124
        result_text = captured_text(timeout_error.stdout)
        stderr_text = (
            captured_text(timeout_error.stderr)
            + f" process timed out after {args.process_timeout} seconds"
        ).strip()
    parsed = None
    if result_text:
        try:
            parsed = json.loads(result_text)
        except json.JSONDecodeError:
            parsed = None
    writer.writerow(
        {
            "campaign_seed": args.campaign_seed,
            "case": case,
            "distance": distance,
            "block": block,
            "template": template,
            "position": position,
            "label": label,
            "mode": mode,
            "pid": "" if parsed is None else parsed.get("pid", ""),
            "started_unix_ns": started,
            "binary_sha256": binary_hash,
            "returncode": returncode,
            "result_json": result_text,
            "stderr": stderr_text.replace("\n", "\\n"),
        }
    )
    sys.stdout.write(
        f"case={case} distance={distance} block={block} template={template} "
        f"position={position} label={label} mode={mode} rc={returncode} "
        f"result={result_text}\n"
    )
    sys.stdout.flush()
    if returncode != 0 or parsed is None or not parsed.get("correct", False):
        raise RuntimeError(f"invalid attempt retained in output; command={command!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Run fresh-process ABBA/BAAB blocks for demand vs software prefetch."
    )
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--distances", type=parse_distances, default=[4, 8, 16, 32, 64])
    parser.add_argument("--blocks", type=int, default=4)
    parser.add_argument("--aa-blocks", type=int, default=2)
    parser.add_argument("--pattern", choices=["random", "sequential"], default="random")
    parser.add_argument("--mib", type=int, default=512)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--warmup-passes", type=int, default=1)
    parser.add_argument("--cpu", type=int)
    parser.add_argument("--campaign-seed", type=int, default=480048)
    parser.add_argument("--workload-seed", type=int, default=48000048)
    parser.add_argument("--process-timeout", type=float, default=600.0)
    args = parser.parse_args()

    if not args.binary.is_file():
        parser.error("binary does not exist")
    args.binary = args.binary.resolve()
    if args.blocks <= 0 or args.blocks % 2 != 0:
        parser.error("--blocks must be a positive even number")
    if args.aa_blocks <= 0 or args.aa_blocks % 2 != 0:
        parser.error("--aa-blocks must be a positive even number")
    if args.process_timeout <= 0:
        parser.error("--process-timeout must be positive seconds")

    binary_hash = sha256(args.binary)
    rng = random.Random(args.campaign_seed)
    # Shuffle from sorted order so the schedule depends only on the distance
    # set and seed; validate_receipts.py recomputes it the same way.
    distance_order = sorted(args.distances)
    rng.shuffle(distance_order)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Exclusive create: overwriting an existing log would erase retained
        # failed attempts from an earlier run of the same command.
        output_stream = args.output.open("x", newline="")
    except FileExistsError:
        parser.error("output already exists; choose a new path to retain prior attempts")
    with output_stream as output:
        writer = csv.DictWriter(output, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()

        for distance in distance_order:
            for block, template in enumerate(balanced_templates(args.blocks, rng), 1):
                for position, label in enumerate(template, 1):
                    mode = "demand" if label == "A" else "prefetch"
                    run_one(
                        args,
                        case="primary",
                        distance=distance,
                        block=block,
                        template=template,
                        position=position,
                        label=label,
                        mode=mode,
                        binary_hash=binary_hash,
                        writer=writer,
                    )
                    output.flush()

        aa_distance = 0
        for block, template in enumerate(balanced_templates(args.aa_blocks, rng), 1):
            for position, label in enumerate(template, 1):
                run_one(
                    args,
                    case="aa",
                    distance=aa_distance,
                    block=block,
                    template=template,
                    position=position,
                    label=label,
                    mode="demand",
                    binary_hash=binary_hash,
                    writer=writer,
                )
                output.flush()

    print(
        json.dumps(
            {
                "schema": 1,
                "host": platform.node(),
                "output": str(args.output),
                "binary_sha256": binary_hash,
                "campaign_seed": args.campaign_seed,
                "workload_seed": args.workload_seed,
                "pattern": args.pattern,
                "declared_distances": args.distances,
                "distance_order": distance_order,
                "blocks": args.blocks,
                "aa_blocks": args.aa_blocks,
                "mib": args.mib,
                "passes": args.passes,
                "warmup_passes": args.warmup_passes,
                "cpu": args.cpu,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
