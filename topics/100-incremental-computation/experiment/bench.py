"""Eight alternating pairs per workload; each sample uses a fresh process."""
import json
import os
import platform
import statistics
import subprocess
import sys

binary = os.path.abspath(sys.argv[1])
if hasattr(os, "sched_getaffinity"):
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
else:
    cpu = None
cells = []
for n, k, rounds in [(65536, 1, 200), (65536, 256, 100), (65536, 65536, 8), (8, 8, 2000)]:
    def run(method):
        return json.loads(subprocess.check_output([binary, method, str(n), str(k), str(rounds)], text=True))
    for method in ["delta", "recompute"]:
        run(method)
    samples = []
    for trial in range(8):
        pair = {m: run(m) for m in (["delta", "recompute"] if trial % 2 == 0 else ["recompute", "delta"])}
        assert pair["delta"]["checksum"] == pair["recompute"]["checksum"]
        samples.append(pair)
    stats = {m: {"median_ns": statistics.median(p[m]["ns_per_batch"] for p in samples),
                 "min_ns": min(p[m]["ns_per_batch"] for p in samples),
                 "max_ns": max(p[m]["ns_per_batch"] for p in samples)} for m in ["delta", "recompute"]}
    ratios = [p["recompute"]["ns_per_batch"] / p["delta"]["ns_per_batch"] for p in samples]
    winner = "delta" if min(ratios) > 1.05 else "recompute" if max(ratios) < 1 / 1.05 else "unresolved"
    cells.append({"n": n, "k": k, "rounds": rounds, "samples": samples, "stats": stats, "winner": winner})
print(json.dumps({"platform": platform.platform(), "machine": platform.machine(), "cpu": cpu,
                  "criterion": "winner must exceed 5 percent in every pair; otherwise unresolved", "cells": cells}, indent=2))
