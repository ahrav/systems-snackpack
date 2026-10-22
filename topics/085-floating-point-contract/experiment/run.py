"""Fixed twelve-block experiment; elapsed kernel time excludes setup and checking."""
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

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
RUSTC = [str(Path.home()/".cargo/bin/rustup"), "run", "1.93.1", "rustc"]
FLAGS = ["--edition", "2024", "-C", "opt-level=3", "-C", "target-cpu=native",
         "-C", "codegen-units=1", "-C", "lto=off", "-C", "panic=unwind"]


def command(name, argv, timeout=180):
    start = time.time()
    try:
        p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
        rec = dict(argv=list(map(str, argv)), start=start, seconds=time.time()-start,
                   returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except subprocess.TimeoutExpired as e:
        # TimeoutExpired carries raw bytes even in text mode.
        stdout, stderr = (None if s is None else s.decode(errors="replace") for s in (e.stdout, e.stderr))
        rec = dict(argv=list(map(str, argv)), start=start, seconds=time.time()-start,
                   returncode=None, timeout=timeout, stdout=stdout, stderr=stderr)
        (OUT / f"{name}.json").write_text(json.dumps(rec, indent=2)+"\n")
        raise
    (OUT / f"{name}.json").write_text(json.dumps(rec, indent=2)+"\n")
    if p.returncode:
        raise RuntimeError(f"{name} failed: {p.stderr}")
    return p.stdout


source = ROOT / "src/main.rs"
meta = {"platform": platform.platform(), "machine": platform.machine(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "input_hashes": {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                         for f in [source, *sorted((ROOT/"experiment").glob("*.py"))]},
        "flags": FLAGS, "toolchain": command("rustc", RUSTC+["-vV"]),
        "hostname": platform.node(), "thread_count": 1, "scope": "warm repeated kernel passes; allocation and checks excluded"}
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
    cache = Path(f"/sys/devices/system/cpu/cpu{cpus[0]}/cache")
    meta["cpu_cache"] = {p.name: {k: (p / k).read_text().strip() for k in ("level", "type", "size")}
                         for p in sorted(cache.glob("index*"))}
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
orders = list(itertools.permutations(("ordered", "lanes4", "compensated"))) * 2
# Balanced order and equal work: 2**24 items per measured process.
for n in (256, 65536, 1048576):
    for workload in ("positive", "signed"):
        for rep, order in enumerate(orders):
            for position, mode in enumerate(order):
                result = command(f"{workload}-n{n}-r{rep}-{position}-{mode}",
                                 [str(binary), "bench", mode, workload, str(n), str((1 << 24)//n)])
                row = next(csv.DictReader(io.StringIO(result)))
                row.update(rep=rep, position=position)
                rows.append(row)
        print(f"completed {workload} n={n}", flush=True)
with (OUT/"samples.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"complete: {len(rows)} measured processes", flush=True)
