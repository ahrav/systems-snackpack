#!/usr/bin/env python3
"""Fixed environment for every timed or correctness probe process."""

from __future__ import annotations

import os

# An allowlist excludes loader interposition, profilers, and inherited runtime
# tuning while retaining only deterministic process basics.
PROBE_ENVIRONMENT = {
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": os.defpath,
    "TZ": "UTC",
}

REFERENCE_ITERATIONS = 20_000_000
REFERENCE_TIMEOUT_SECONDS = 120


def probe_timeout_seconds(iterations: int) -> int:
    """Scale the process deadline linearly above the fixed default workload."""

    return max(
        REFERENCE_TIMEOUT_SECONDS,
        (iterations * REFERENCE_TIMEOUT_SECONDS + REFERENCE_ITERATIONS - 1)
        // REFERENCE_ITERATIONS,
    )
