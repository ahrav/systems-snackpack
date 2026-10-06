#!/usr/bin/env python3
"""8 balanced process blocks per cell. No concurrent benchmark processes."""
import json, os, pathlib, subprocess, sys

binary, output = sys.argv[1:]
cpus = sorted(os.sched_getaffinity(0))
assert len(cpus) >= 4
policies = ["spin", "one", "all", "hybrid"]
cells = [
    ("uncontended", 1, 100000, 1, 0, 4),
    ("short", 4, 10000, 1, 0, 4),
    ("long", 4, 2000, 256, 0, 4),
    ("oversubscribed", 8, 2000, 1, 0, 1),
    ("sleeping_owner", 4, 50, 1, 50, 4),
    ("burst", 4, 1, 1, 0, 4),
]
out = pathlib.Path(output)
out.mkdir(parents=True, exist_ok=True)
(out / "plan.json").write_text(json.dumps({"blocks":8,"cells":cells,"cpus":cpus,
    "flags":"rustc -C opt-level=3 -C target-cpu=native; unwind; default LTO",
    "warmup":"20 operations per worker, separate locks/workers before each measurement",
    "boundary":"ready-worker release through join; includes lock stats and checks in critical section; excludes thread creation, post-run serial oracle and output",
    "criterion":"lowest median wall ns/op, resolved only if >=2% better and paired 95% bootstrap median-ratio upper bound <1 against every other candidate",
    "limitations":"instrumented lock; not fairness bound; burst is warm-process start/join, not cold-cache; selected CPUs not guaranteed physical cores"}, indent=2))
with (out / "runs.jsonl").open("w") as f:
    for name, threads, n, work, sleep, budget in cells:
        affinity = ",".join(map(str, cpus[:budget]))
        for block in range(8):
            order = policies[block % 4:] + policies[:block % 4]
            if (block // 4) % 2: order = order[::-1]
            for position, policy in enumerate(order):
                cmd = ["taskset", "-c", affinity, binary, policy, str(threads), str(n), str(work), str(sleep)]
                run = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
                if run.returncode: raise RuntimeError((cmd, run.stdout, run.stderr))
                r = json.loads(run.stdout)
                r.update(cell=name, block=block, position=position, affinity=affinity)
                f.write(json.dumps(r)+"\n"); f.flush()
        print(name, "complete", flush=True)
