#!/usr/bin/env python3
"""Validate Topic 23 process counts, controls, and correctness receipts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()

    checks = (args.evidence_directory / "correctness" / "replicates.txt").read_text().splitlines()
    if len(checks) != 32:
        raise SystemExit(f"expected 32 correctness processes, found {len(checks)}")
    expected = (
        "raw_stale_cas=true,raw_reintroduced_b=true,"
        "tagged_stale_cas=false,tagged_generation=3,tagged_index=1"
    )
    if any(expected not in line for line in checks):
        raise SystemExit("a correctness replicate did not preserve the ABA controls")

    with (args.evidence_directory / "processes" / "raw.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 72:
        raise SystemExit(f"expected 72 timed processes, found {len(rows)}")
    if sum(row["phase"] == "ab" for row in rows) != 48:
        raise SystemExit("A/B process count is not 48")
    if sum(row["phase"] == "aa" for row in rows) != 24:
        raise SystemExit("A/A process count is not 24")

    summary = json.loads(
        (args.evidence_directory / "processes" / "summary.json").read_text()
    )
    comparisons = {entry["phase"]: entry for entry in summary["comparisons"]}
    if comparisons["ab"]["blocks"] != 12 or comparisons["aa"]["blocks"] != 6:
        raise SystemExit("summary block counts do not match the predeclared design")
    for entry in comparisons.values():
        if not (0 < entry["ci95_low"] <= entry["geometric_mean_ratio"] <= entry["ci95_high"]):
            raise SystemExit("invalid ratio interval")

    print("receipt validation: PASS")


if __name__ == "__main__":
    main()
