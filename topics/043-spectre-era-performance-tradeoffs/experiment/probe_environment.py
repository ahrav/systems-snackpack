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
