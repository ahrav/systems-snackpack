"""Fixed six-order experiment; elapsed kernel time excludes setup and checking."""
import csv
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from oracle import check

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
RUSTC = [str(Path.home() / ".cargo/bin/rustc"), "+1.93.1"]
FLAGS = ["--edition", "2024", "-C", "opt-level=3", "-C", "target-cpu=native",
         "-C", "codegen-units=1", "-C", "lto=off", "-C", "panic=unwind"]


def command(name, argv, timeout=180):
    start = time.time()
    try:
        p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
        rec = dict(argv=list(map(str, argv)), start=start, seconds=time.time()-start,
                   returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except subprocess.TimeoutExpired as e:
        rec = dict(argv=list(map(str, argv)), start=start, seconds=time.time()-start,
                   timeout=timeout, stdout=str(e.stdout), stderr=str(e.stderr))
        (OUT / f"{name}.json").write_text(json.dumps(rec, indent=2)+"\n")
        raise
    (OUT / f"{name}.json").write_text(json.dumps(rec, indent=2)+"\n")
    if p.returncode:
        raise RuntimeError(f"{name} failed: {p.stderr}")
    return p.stdout


source = ROOT / "src/main.rs"
meta = {"platform": platform.platform(), "machine": platform.machine(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "flags": FLAGS, "toolchain": command("rustc", RUSTC+["-vV"]),
        "thread_count": 1, "scope": "warm repeated kernel passes; allocation and checks excluded"}
if sys.platform == "linux":
    cpus = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpus[0]})
    if os.sched_getaffinity(0) != {cpus[0]}:
        raise RuntimeError("affinity verification failed")
    meta.update(allowed_cpus=cpus, pinned_cpu=cpus[0])
    command("lscpu", ["lscpu"])
    command("kernel", ["uname", "-a"])
    command("memory", ["cat", "/proc/meminfo"])
    command("load", ["cat", "/proc/loadavg"])
    meta["cpu_cache"] = {str(p): p.read_text().strip() for p in
                         Path(f"/sys/devices/system/cpu/cpu{cpus[0]}/cache").glob("index*/size")}
else:
    meta["placement"] = "uncontrolled"
(OUT / "metadata.json").write_text(json.dumps(meta, indent=2)+"\n")
binary = OUT / "demo"
command("compile", RUSTC+FLAGS+[str(source), "-o", str(binary)])
command("compile-tests", RUSTC+FLAGS+["--test", str(source), "-o", str(OUT/"tests")])
command("tests", [str(OUT/"tests")])
command("oracle", [sys.executable, str(ROOT/"experiment/oracle.py"), str(binary)])
command("assembly", RUSTC+FLAGS+["--emit=asm", str(source), "-o", str(OUT/"demo.s")])
if sys.platform == "linux":
    command("disassembly", ["objdump", "-d", "-C", str(binary)])
(OUT / "binary.sha256").write_text(hashlib.sha256(binary.read_bytes()).hexdigest()+"\n")
rows = []
orders = list(itertools.permutations(("split", "blocked", "fused")))
# Each cell processes 2**26 items per process. Every process warms three passes.
for n in (1024, 262144, 16777216):
    for rep, order in enumerate(orders):
        for position, mode in enumerate(order):
            result = command(f"n{n}-r{rep}-{position}-{mode}",
                             [str(binary), mode, str(n), str((1 << 26)//n)])
            row = next(csv.DictReader(io.StringIO(result)))
            row.update(rep=rep, position=position)
            rows.append(row)
    print(f"completed n={n}", flush=True)
with (OUT/"samples.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"complete: {len(rows)} measured processes", flush=True)
