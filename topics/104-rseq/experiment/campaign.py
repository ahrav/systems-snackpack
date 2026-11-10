"""Check exact totals independently and retain balanced fresh-process samples."""
import itertools
import json
import os
import platform
import subprocess
import sys

binary = os.path.abspath(sys.argv[1])
env = dict(os.environ, GLIBC_TUNABLES="glibc.pthread.rseq=0")
records = []

def run(method, threads, iterations, cpus, stress, phase, block):
    result = subprocess.run([binary, method, str(threads), str(iterations), str(cpus), str(stress)],
                            env=env, check=True, capture_output=True, text=True, timeout=120)
    row = json.loads(result.stdout)
    assert row["total"] == threads * iterations, row
    row.update(phase=phase, block=block)
    records.append(row)

for threads, cpus in [(1, 1), (8, 8), (8, 2)]:
    for method in ["rseq", "tls", "atomic"]:
        for n in [0, 1, 17]:
            run(method, threads, n, cpus, 0, "correctness", 0)
        run(method, threads, 100000, cpus, 0, "warmup", 0)
    for block, order in enumerate(itertools.permutations(["rseq", "tls", "atomic"])):
        for method in order:
            run(method, threads, 3000000, cpus, 0, "measurement", block)
for block in range(3):
    run("rseq", 8, 100000, 2, 1, "stress", block)
assert sum(r["retries"] for r in records if r["phase"] == "stress") > 0
print(json.dumps({"machine": platform.machine(), "platform": platform.platform(), "records": records}, indent=2))
