#!/usr/bin/env python3
"""Validate Topic 16 process pairs and bootstrap paired log-ratio estimates."""

from __future__ import annotations

import csv
import hashlib
import math
import os
import random
import statistics
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

PAIRS = 12
BOOTSTRAP_RESAMPLES = 20_000
EXPECTED_FIELDS = [
    "comparison",
    "pair",
    "order",
    "position",
    "mode",
    "steady_ns",
    "process_ns",
    "elements",
    "rounds",
    "checksum",
]
COMPARISONS = [
    ("imported/local", "imported", "local"),
    ("opaque/local", "opaque", "local"),
]


@dataclass(frozen=True)
class Observation:
    """One fresh process result with its timed and whole-process boundaries."""

    steady_ns: int
    process_ns: int
    elements: int
    rounds: int
    checksum: int

    @property
    def outside_ns(self) -> int:
        """Return whole-process time minus the steady timed region."""

        return self.process_ns - self.steady_ns


def fail(message: str) -> NoReturn:
    """Exit without a traceback for invalid retained evidence."""

    raise SystemExit(message)


def integer(row: dict[str, str], field: str) -> int:
    """Parse one integer field or reject its row."""

    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError):
        fail(f"{row.get('comparison', '<unknown>')}: {field} is not an integer")


def quantile(values: list[float], probability: float) -> float:
    """Return a type-7 quantile."""

    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def schedule() -> list[tuple[str, int, str, int, str]]:
    """Return the fixed row order for both twelve-pair comparisons."""

    rows: list[tuple[str, int, str, int, str]] = []
    for comparison, mode_a, mode_b in COMPARISONS:
        for pair in range(1, PAIRS + 1):
            order = "AB" if pair % 2 == 1 else "BA"
            modes = (mode_a, mode_b) if order == "AB" else (mode_b, mode_a)
            rows.extend(
                (comparison, pair, order, position, mode)
                for position, mode in enumerate(modes, start=1)
            )
    return rows


def parse(path: Path) -> dict[str, dict[int, dict[str, Observation]]]:
    """Parse raw rows and enforce schedule, fixture, and timing invariants."""

    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != EXPECTED_FIELDS:
            fail(f"unexpected raw header: {reader.fieldnames}")
        rows = list(reader)

    expected = schedule()
    if len(rows) != len(expected):
        fail(f"expected {len(expected)} process rows, observed {len(rows)}")
    if any(None in row for row in rows):
        fail("one or more rows contain fields beyond the declared schema")
    if any(value is None for row in rows for value in row.values()):
        fail("one or more rows omit a field from the declared schema")

    observations: dict[str, dict[int, dict[str, Observation]]] = {
        comparison: {pair: {} for pair in range(1, PAIRS + 1)}
        for comparison, _, _ in COMPARISONS
    }
    fixture: tuple[int, int, int] | None = None

    for row, expected_identity in zip(rows, expected):
        identity = (
            row["comparison"],
            integer(row, "pair"),
            row["order"],
            integer(row, "position"),
            row["mode"],
        )
        if identity != expected_identity:
            fail(f"row identity {identity!r} differs from schedule {expected_identity!r}")

        observation = Observation(
            steady_ns=integer(row, "steady_ns"),
            process_ns=integer(row, "process_ns"),
            elements=integer(row, "elements"),
            rounds=integer(row, "rounds"),
            checksum=integer(row, "checksum"),
        )
        if observation.steady_ns <= 0 or observation.process_ns <= 0:
            fail(f"{identity!r}: timing fields must be positive")
        if observation.outside_ns <= 0:
            fail(f"{identity!r}: process_ns must exceed steady_ns")
        if observation.elements <= 0 or observation.rounds <= 0:
            fail(f"{identity!r}: elements and rounds must be positive")

        current_fixture = (
            observation.elements,
            observation.rounds,
            observation.checksum,
        )
        if fixture is None:
            fixture = current_fixture
        elif current_fixture != fixture:
            fail(f"{identity!r}: workload or correctness checksum changed")

        comparison, pair, _, _, mode = identity
        if mode in observations[comparison][pair]:
            fail(f"{comparison} pair {pair}: duplicate mode {mode}")
        observations[comparison][pair][mode] = observation

    return observations


def bootstrap_seed(comparison: str, metric: str) -> int:
    """Derive a stable seed from the comparison and metric names."""

    digest = hashlib.sha256(f"topic16:{comparison}:{metric}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def ratio_summary(
    comparison: str,
    metric: str,
    ratios: list[float],
) -> list[str]:
    """Summarize paired ratios with a percentile bootstrap in log space."""

    if len(ratios) != PAIRS or any(value <= 0 or not math.isfinite(value) for value in ratios):
        fail(f"{comparison} {metric}: ratios must contain {PAIRS} positive values")
    logs = [math.log(value) for value in ratios]
    point = math.exp(statistics.fmean(logs))
    seed = bootstrap_seed(comparison, metric)
    rng = random.Random(seed)
    boot = [
        math.exp(statistics.fmean(rng.choice(logs) for _ in logs))
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    return [
        comparison,
        metric,
        str(PAIRS),
        f"{point:.9f}",
        f"{quantile(boot, 0.025):.9f}",
        f"{quantile(boot, 0.975):.9f}",
        f"{quantile(ratios, 0.5):.9f}",
        f"{quantile(ratios, 0.25):.9f}",
        f"{quantile(ratios, 0.75):.9f}",
        f"{statistics.stdev(logs):.9f}",
        str(BOOTSTRAP_RESAMPLES),
        str(seed),
    ]


def write_summary(
    path: Path,
    observations: dict[str, dict[int, dict[str, Observation]]],
) -> None:
    """Atomically write steady, whole-process, and outside-region ratios."""

    rows: list[list[str]] = []
    for comparison, mode_a, mode_b in COMPARISONS:
        paired = observations[comparison]
        for metric, accessor in (
            ("steady_a_over_b", lambda item: item.steady_ns),
            ("process_a_over_b", lambda item: item.process_ns),
            ("outside_a_over_b", lambda item: item.outside_ns),
        ):
            ratios = [
                accessor(paired[pair][mode_a]) / accessor(paired[pair][mode_b])
                for pair in range(1, PAIRS + 1)
            ]
            rows.append(ratio_summary(comparison, metric, ratios))

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=".topic16-summary.",
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as destination:
            writer = csv.writer(destination, lineterminator="\n")
            writer.writerow(
                [
                    "comparison",
                    "metric",
                    "n_pairs",
                    "geometric_mean",
                    "bootstrap_low_95",
                    "bootstrap_high_95",
                    "median",
                    "q1",
                    "q3",
                    "log_sample_sd",
                    "bootstrap_resamples",
                    "bootstrap_seed",
                ]
            )
            writer.writerows(rows)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    """Validate arguments, parse raw evidence, and emit the summary."""

    if len(sys.argv) != 3:
        fail(f"usage: {Path(sys.argv[0]).name} RAW.csv SUMMARY.csv")
    raw_path = Path(sys.argv[1])
    summary_path = Path(sys.argv[2])
    if not raw_path.is_file():
        fail(f"raw CSV does not exist: {raw_path}")
    if raw_path.resolve() == summary_path.resolve() or (
        summary_path.exists() and raw_path.samefile(summary_path)
    ):
        fail("RAW.csv and SUMMARY.csv must name different files")
    write_summary(summary_path, parse(raw_path))


if __name__ == "__main__":
    main()
