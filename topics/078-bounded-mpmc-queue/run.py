"""Run paired independent processes; exclude one warmup pair per workload."""
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path

binary, destination = sys.argv[1:]
partial = Path(destination + ".partial")
rows = []
for producers, capacity in [(1, 4), (1, 1024), (4, 4), (4, 1024)]:
    for block in range(-1, 6):
        order = ["array", "mutex"] if block % 2 == 0 else ["mutex", "array"]
        for mode in order:
            command = [binary, mode, str(capacity), str(producers), str(producers), "100000"]
            row = json.loads(subprocess.check_output(command, text=True, timeout=120))
            expected = {"mode": mode, "capacity": capacity, "producers": producers, "consumers": producers, "per_producer": 100000, "jobs": producers * 100000, "verified": True}
            if {key: row.get(key) for key in expected} != expected or type(row.get("elapsed_ns")) is not int or row["elapsed_ns"] <= 0:
                raise SystemExit(f"row does not match its command: {command} -> {row}")
            row.update(block=block, warmup=block == -1)
            rows.append(row)
            partial.write_text(json.dumps({"platform": platform.platform(), "rows": rows}, indent=2) + "\n")
summary = []
for producers, capacity in [(1, 4), (1, 1024), (4, 4), (4, 1024)]:
    cell = [r for r in rows if not r["warmup"] and r["producers"] == producers and r["capacity"] == capacity]
    series = {m: [next(r["elapsed_ns"] / r["jobs"] for r in cell if r["mode"] == m and r["block"] == b) for b in range(6)] for m in ["array", "mutex"]}
    ratios = [m / a for m, a in zip(series["mutex"], series["array"])]
    winner = "array" if min(ratios) > 1.05 else "mutex" if max(ratios) < 1 / 1.05 else "unresolved"
    summary.append({"producers": producers, "consumers": producers, "capacity": capacity, "ns_per_job": {m: {"median": statistics.median(v), "min": min(v), "max": max(v)} for m, v in series.items()}, "mutex_over_array_pairs": ratios, "winner": winner})
partial.write_text(json.dumps({"platform": platform.platform(), "rows": rows, "summary": summary}, indent=2) + "\n")
partial.replace(destination)
print(json.dumps(summary, indent=2))
