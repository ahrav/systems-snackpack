#!/usr/bin/env python3
"""Validate Topic 38 process, correctness, analysis, and completion receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedule import ScheduledRun, make_schedule  # noqa: E402


RESULT_PATTERN = re.compile(r"^result (?P<fields>.+)$")
COMPLETION_PATTERN = re.compile(
    r"^completion=\d+ first=(\d+) last=(\d+) ee_errno=(\d+) "
    r"ee_code=(\d+) copied=(yes|no)$"
)


def digest_path(path: Path) -> str:
    """Return a streaming SHA-256 digest."""

    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a nonempty tab-separated receipt."""

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError(f"empty table: {path}")
    return rows


def scheduled_dict(row: ScheduledRun) -> dict[str, str]:
    """Convert one expected schedule row to its serialized form."""

    return {name: str(value) for name, value in row.__dict__.items()}


def parse_probe_line(text: str) -> dict[str, str]:
    """Parse a retained probe result without positional assumptions."""

    lines = [line for line in text.splitlines() if line]
    if len(lines) != 1:
        raise ValueError("a probe stdout receipt does not contain exactly one line")
    matched = RESULT_PATTERN.fullmatch(lines[0])
    if matched is None:
        raise ValueError("a probe stdout receipt lacks the result marker")
    result: dict[str, str] = {}
    for token in matched.group("fields").split():
        key, separator, value = token.partition("=")
        if not separator or key in result:
            raise ValueError(f"invalid probe token: {token}")
        result[key] = value
    return result


def validate_schedule(root: Path, seed: int, blocks: int) -> list[dict[str, str]]:
    """Require the declared seeded schedule byte-for-byte by field."""

    observed = read_tsv(root / "schedule.tsv")
    expected = [scheduled_dict(row) for row in make_schedule(seed, blocks)]
    if observed != expected:
        raise ValueError("schedule.tsv differs from the declared generator")
    return expected


def validate_correctness(root: Path, config: dict[str, object]) -> None:
    """Require exact-byte verified runs for all three file paths."""

    rows = read_tsv(root / "correctness.tsv")
    if Counter(row["method"] for row in rows) != Counter(
        {"buffered": 1, "sendfile": 1, "splice": 1}
    ):
        raise ValueError("correctness.tsv does not contain exactly three methods")
    expected_bytes = str(config["correctness_bytes"])
    for row in rows:
        if (
            row["rc"] != "0"
            or row["ok"] != "1"
            or row["verify"] != "1"
            or row["bytes"] != expected_bytes
            or row["received_bytes"] != expected_bytes
            or row["transfer_errno"] != "0"
            or row["receiver_status"] != "0"
        ):
            raise ValueError(f"failed correctness receipt for {row['method']}")
        raw_stdout = root / "raw" / f"correctness-{row['method']}.stdout"
        raw_stderr = root / "raw" / f"correctness-{row['method']}.stderr"
        if digest_path(raw_stdout) != row["stdout_sha256"]:
            raise ValueError(f"correctness stdout digest mismatch for {row['method']}")
        if digest_path(raw_stderr) != row["stderr_sha256"]:
            raise ValueError(f"correctness stderr digest mismatch for {row['method']}")
        parsed = parse_probe_line(raw_stdout.read_text(encoding="utf-8"))
        for field, value in parsed.items():
            if row.get(field) != value:
                raise ValueError(f"correctness raw/result drift for {row['method']} field {field}")


def validate_runs(
    root: Path,
    expected_schedule: list[dict[str, str]],
    config: dict[str, object],
) -> None:
    """Require all 96 no-retry process receipts and their raw output hashes."""

    rows = read_tsv(root / "runs.tsv")
    if len(rows) != len(expected_schedule) or len(rows) != 96:
        raise ValueError(f"expected 96 timing rows, found {len(rows)}")
    if len({row["run_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate run_id")
    if [int(row["sequence"]) for row in rows] != list(range(1, 97)):
        raise ValueError("timing sequence is not exactly 1..96")

    per_pair = Counter(row["pair"] for row in rows)
    if per_pair != Counter(
        {"buffered-sendfile": 32, "buffered-splice": 32, "aa-buffered": 32}
    ):
        raise ValueError(f"unexpected pair counts: {per_pair}")

    blocks: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row, expected in zip(rows, expected_schedule, strict=True):
        for field, expected_value in expected.items():
            if row[field] != expected_value:
                raise ValueError(f"schedule drift in {row['run_id']} field {field}")
        if row["pair"] == "aa-buffered" and row["method"] != "buffered":
            raise ValueError("A/A pair used a non-buffered method")
        if (
            row["rc"] != "0"
            or row["ok"] != "1"
            or row["verify"] != "0"
            or row["bytes"] != str(config["bytes"])
            or row["received_bytes"] != str(config["bytes"])
            or row["transfer_errno"] != "0"
            or row["receiver_status"] != "0"
            or int(row["outer_ns"]) <= 0
        ):
            raise ValueError(f"failed timing receipt for {row['run_id']}")
        for field in (
            "transfer_sec",
            "setup_sec",
            "total_sec",
            "sender_cpu_sec",
            "receiver_cpu_sec",
        ):
            value = float(row[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid {field} in {row['run_id']}")
        raw_stdout = root / "raw" / f"{row['run_id']}.stdout"
        raw_stderr = root / "raw" / f"{row['run_id']}.stderr"
        if digest_path(raw_stdout) != row["stdout_sha256"]:
            raise ValueError(f"stdout digest mismatch for {row['run_id']}")
        if digest_path(raw_stderr) != row["stderr_sha256"]:
            raise ValueError(f"stderr digest mismatch for {row['run_id']}")
        parsed = parse_probe_line(raw_stdout.read_text(encoding="utf-8"))
        for field, value in parsed.items():
            if row.get(field) != value:
                raise ValueError(f"raw/result drift in {row['run_id']} field {field}")
        blocks[(row["pair"], row["block"])].append(row)

    if len(blocks) != 24:
        raise ValueError(f"expected 24 pair-blocks, found {len(blocks)}")
    for (pair, block), block_rows in blocks.items():
        if len(block_rows) != 4:
            raise ValueError(f"incomplete {pair} block {block}")
        ordered = sorted(block_rows, key=lambda row: int(row["position"]))
        labels = "".join(row["label"] for row in ordered)
        if labels != ordered[0]["template"] or labels not in {"ABBA", "BAAB"}:
            raise ValueError(f"invalid order for {pair} block {block}")


def validate_analysis(root: Path, blocks: int) -> None:
    """Require complete block contrasts and summaries, including outer time."""

    contrasts = read_tsv(root / "contrasts.tsv")
    summaries = read_tsv(root / "summary.tsv")
    if len(contrasts) != 3 * blocks * 2:
        raise ValueError("contrast table has the wrong row count")
    expected_metrics = {
        "transfer_sec",
        "setup_sec",
        "sender_cpu_sec",
        "receiver_cpu_sec",
        "total_sec",
        "outer_sec",
    }
    for pair in ("buffered-sendfile", "buffered-splice", "aa-buffered"):
        pair_rows = [row for row in summaries if row["pair"] == pair]
        if {row["metric"] for row in pair_rows} != expected_metrics:
            raise ValueError(f"summary metrics incomplete for {pair}")
        transfer = next(row for row in pair_rows if row["metric"] == "transfer_sec")
        if transfer["complete_blocks"] != str(blocks) or transfer["process_runs"] != str(4 * blocks):
            raise ValueError(f"summary replication changed for {pair}")
        for field in ("ratio_B_over_A", "ci95_low", "ci95_high"):
            value = float(transfer[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid transfer summary {field} for {pair}")
        deviation = float(transfer["sd_log_block_contrast"])
        if not math.isfinite(deviation) or deviation < 0:
            raise ValueError(f"invalid transfer dispersion for {pair}")


def validate_msgzc(path: Path) -> None:
    """Require exact receive bytes and complete error-queue coverage."""

    lines = path.read_text(encoding="utf-8").splitlines()
    required = {
        "measurement=correctness_only timing_reported=no",
        "receiver_bytes=524288/524288 receiver_content=verified",
        "completion_coverage=8/8",
        "contract_result=PASS buffer_lifetime=held_through_all_completions",
    }
    for marker in required:
        if not any(line.startswith(marker) for line in lines):
            raise ValueError(f"{path.name} lacks {marker}")
    fallback = [line for line in lines if line.startswith("copied_fallback_observed=")]
    if len(fallback) != 1 or fallback[0] not in {
        "copied_fallback_observed=yes",
        "copied_fallback_observed=no",
    }:
        raise ValueError(f"{path.name} lacks a fallback report")
    covered: set[int] = set()
    for line in lines:
        matched = COMPLETION_PATTERN.fullmatch(line)
        if matched is None:
            continue
        first, last, error_number, _code, _copied = matched.groups()
        first_id = int(first)
        last_id = int(last)
        if int(error_number) != 0 or first_id > last_id or last_id >= 8:
            raise ValueError(f"invalid completion range in {path.name}")
        covered.update(range(first_id, last_id + 1))
    if covered != set(range(8)):
        raise ValueError(f"{path.name} completion ranges cover {sorted(covered)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument("--binary", type=Path)
    arguments = parser.parse_args()
    root = arguments.result_dir.resolve()
    config = json.loads((root / "run-config.json").read_text(encoding="utf-8"))
    if config.get("blocks") != 8 or config.get("seed") != 38_017:
        raise ValueError("retained configuration is not the promoted design")
    if config.get("retry_policy") != "none":
        raise ValueError("retry policy changed")
    expected = validate_schedule(root, int(config["seed"]), int(config["blocks"]))
    validate_correctness(root, config)
    validate_runs(root, expected, config)
    validate_analysis(root, int(config["blocks"]))
    validate_msgzc(root / "msgzc-generic.stdout")
    validate_msgzc(root / "msgzc-native.stdout")
    if arguments.binary is not None and digest_path(arguments.binary) != config["binary_sha256"]:
        raise ValueError("supplied timing binary differs from run-config.json")
    print("VALIDATION=PASS timing_rows=96 blocks_per_pair=8 aa=yes msgzc_coverage=8/8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, ValueError) as error:
        print(f"VALIDATION=FAIL reason={error}", file=sys.stderr)
        raise SystemExit(1) from error
