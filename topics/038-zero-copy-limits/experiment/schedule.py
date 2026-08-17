#!/usr/bin/env python3
"""Create the fixed-seed order-balanced fresh-process schedule."""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduledRun:
    """One fresh treatment process in the declared schedule."""

    pair: str
    block: int
    position: int
    template: str
    label: str
    method: str


PAIRS = (
    ("buffered-sendfile", "buffered", "sendfile"),
    ("buffered-splice", "buffered", "splice"),
    ("aa-buffered", "buffered", "buffered"),
)


def make_schedule(seed: int, blocks: int) -> list[ScheduledRun]:
    """Return equal counts of `ABBA` and `BAAB` blocks for every pair."""

    if blocks < 2 or blocks % 2 != 0:
        raise ValueError("blocks must be an even integer of at least two")
    rng = random.Random(seed)
    rows: list[ScheduledRun] = []
    for pair, method_a, method_b in PAIRS:
        templates = ["ABBA"] * (blocks // 2) + ["BAAB"] * (blocks // 2)
        rng.shuffle(templates)
        for block, template in enumerate(templates, 1):
            for position, label in enumerate(template, 1):
                rows.append(
                    ScheduledRun(
                        pair=pair,
                        block=block,
                        position=position,
                        template=template,
                        label=label,
                        method=method_a if label == "A" else method_b,
                    )
                )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=38_017)
    parser.add_argument("--blocks", type=int, default=8)
    arguments = parser.parse_args()
    try:
        rows = make_schedule(arguments.seed, arguments.blocks)
    except ValueError as error:
        parser.error(str(error))
    writer = csv.DictWriter(sys.stdout, delimiter="\t", fieldnames=list(ScheduledRun.__annotations__))
    writer.writeheader()
    for row in rows:
        writer.writerow(row.__dict__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
