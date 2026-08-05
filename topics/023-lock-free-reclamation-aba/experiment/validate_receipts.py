#!/usr/bin/env python3
"""Validate Topic 23 process counts, controls, and correctness receipts.

Every check is exact: correctness replicates must match the witness line
byte-for-byte, each timed row must match the predeclared schedule rebuilt
from the templates in ``run_processes``, final words must match the kernel
contract for the recorded iteration count, and both summary comparisons are
recomputed from ``raw.csv`` before ``PASS`` is reported.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_processes import AA_TEMPLATES, AB_TEMPLATES, summarize

EXPECTED_CHECK_LINE = (
    "check,raw_stale_cas=true,raw_reintroduced_b=true,"
    "tagged_stale_cas=false,tagged_generation=3,tagged_index=1"
)


def expected_design() -> list[dict[str, str]]:
    """Rebuild the predeclared 72-row schedule from the run templates."""
    rows: list[dict[str, str]] = []
    for phase, templates in (("ab", AB_TEMPLATES), ("aa", AA_TEMPLATES)):
        for block, template in enumerate(templates, start=1):
            for period, label in enumerate(template, start=1):
                mode = "tagged" if phase == "ab" and label == "B" else "raw"
                rows.append(
                    {
                        "phase": phase,
                        "block": str(block),
                        "period": str(period),
                        "template": template,
                        "label": label,
                        "mode": mode,
                    }
                )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()

    checks = (
        (args.evidence_directory / "correctness" / "replicates.txt")
        .read_text()
        .splitlines()
    )
    if len(checks) != 32:
        raise SystemExit(f"expected 32 correctness processes, found {len(checks)}")
    for number, line in enumerate(checks, start=1):
        if line != EXPECTED_CHECK_LINE:
            raise SystemExit(f"correctness replicate {number} deviates: {line!r}")

    with (args.evidence_directory / "processes" / "raw.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    design = expected_design()
    if len(rows) != len(design):
        raise SystemExit(
            f"expected {len(design)} timed processes, found {len(rows)}"
        )

    iteration_values = {row["iterations"] for row in rows}
    if len(iteration_values) != 1:
        raise SystemExit(
            f"iteration counts vary across rows: {sorted(iteration_values)}"
        )
    iterations = int(next(iter(iteration_values)))
    if iterations <= 0:
        raise SystemExit("iterations must be positive")

    # Both kernels restore index A (1). The tagged kernel advances the packed
    # 32-bit generation twice per iteration with wrapping arithmetic.
    expected_final = {
        "raw": 1,
        "tagged": ((2 * iterations) % 2**32) << 32 | 1,
    }
    # Lengths are checked above, so plain zip cannot truncate silently.
    # zip(strict=True) needs Python 3.10+, newer than the measurement hosts.
    # pi-lens-ignore: B905
    for number, (row, spec) in enumerate(zip(rows, design), start=1):
        for key, value in spec.items():
            if row[key] != value:
                raise SystemExit(
                    f"row {number}: {key}={row[key]!r} does not match "
                    f"the predeclared {value!r}"
                )
        if int(row["final_word"]) != expected_final[row["mode"]]:
            raise SystemExit(
                f"row {number}: final_word does not match the kernel contract"
            )
        if int(row["elapsed_ns"]) <= 0:
            raise SystemExit(f"row {number}: nonpositive elapsed_ns")

    summary = json.loads(
        (args.evidence_directory / "processes" / "summary.json").read_text()
    )
    recomputed = {
        entry["phase"]: entry
        for entry in (summarize(rows, "ab", "B", "A"), summarize(rows, "aa", "R", "L"))
    }
    reported = {entry["phase"]: entry for entry in summary["comparisons"]}
    for phase, expected in recomputed.items():
        actual = reported.get(phase)
        if actual is None:
            raise SystemExit(f"summary lacks the {phase} comparison")
        for key, value in expected.items():
            if isinstance(value, float):
                if not math.isclose(actual[key], value, rel_tol=1e-9, abs_tol=1e-12):
                    raise SystemExit(f"summary {phase}.{key} does not match raw.csv")
            elif actual[key] != value:
                raise SystemExit(f"summary {phase}.{key} does not match raw.csv")

    print("receipt validation: PASS")


if __name__ == "__main__":
    main()
