"""Six order-balanced fresh-process blocks, with separate trace executions."""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import statistics
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
parser.add_argument("--node", default="node")
a = parser.parse_args()
out = pathlib.Path(a.out)
# A fresh directory keeps every result file in it from the campaign that wrote it.
out.mkdir(parents=True, exist_ok=False)
script = pathlib.Path(__file__).with_name("bench.js")
# Node reads NODE_OPTIONS from the environment; removing it isolates both modes from inherited flags.
env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
affinity = None
if hasattr(os, "sched_getaffinity"):
    affinity = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {affinity})
cpu = platform.processor()
if pathlib.Path("/proc/cpuinfo").exists():
    cpu = pathlib.Path("/proc/cpuinfo").read_text()
flags = {"default": [], "jitless": ["--jitless"]}
metadata = dict(platform=platform.platform(), machine=platform.machine(), cpu=cpu,
    affinity=affinity, script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
    flags=flags)
(out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
records = []
for workload in ["stable", "shift", "mixed"]:
    for block in range(6):
        for mode in (["default", "jitless"] if block % 2 == 0 else ["jitless", "default"]):
            cmd = [a.node, *flags[mode], str(script), workload]
            start = time.perf_counter_ns()
            r = subprocess.run(cmd, text=True, capture_output=True, env=env)
            wall = time.perf_counter_ns() - start
            (out / f"{workload}-{block}-{mode}.stderr").write_text(r.stderr)
            r.check_returncode()
            row = json.loads(r.stdout)
            # The check raises so it holds under python -O.
            if row["checksum"] != 267386880:
                raise SystemExit(f"{workload} {block} {mode}: checksum={row['checksum']}")
            row.update(block=block, mode=mode, wallNs=wall)
            records.append(row)
            (out / "samples.json").write_text(json.dumps(records, indent=2) + "\n")
summary = {}
for workload in ["stable", "shift", "mixed"]:
    summary[workload] = {}
    for metric in ["coldNs", "transitionNs", "steadyNs", "wallNs"]:
        values = {mode: [r[metric] for r in records if r["workload"] == workload and r["mode"] == mode]
                  for mode in ["default", "jitless"]}
        d, j = values["default"], values["jitless"]
        verdict = ("default" if all(x < .95*y for x,y in zip(d,j)) else
                   "jitless" if all(y < .95*x for x,y in zip(d,j)) else
                   "tie" if all(abs(x-y) <= .05*max(x,y) for x,y in zip(d,j)) else "unresolved")
        summary[workload][metric] = dict(verdict=verdict, **{m: dict(median=statistics.median(v),
            minimum=min(v), maximum=max(v)) for m,v in values.items()})
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
for workload in ["stable", "shift", "mixed"]:
    r = subprocess.run([a.node, "--trace-opt", "--trace-deopt", str(script), workload],
                       text=True, capture_output=True, env=env)
    (out / f"trace-{workload}.log").write_text(r.stdout + r.stderr)
    r.check_returncode()
print(json.dumps(summary, indent=2))
