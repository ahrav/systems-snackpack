#!/usr/bin/env python3
"""Build separate exact-source treatments and retain all oracle/timing evidence."""
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MASK = (1 << 64) - 1
LENGTHS = [0, 1, 2, 7, 8, 9, 15, 16, 17, 255, 256, 257, 4096]
RUSTC = ["rustc", "+1.93.1"]
FLAGS = ["--edition=2024", "-Copt-level=3", "-Ccodegen-units=1", "-Clto=off",
         "-Cdebuginfo=0", "-Cpanic=abort", "-Csymbol-mangling-version=v0"]


def run(args):
    return subprocess.check_output([str(x) for x in args], text=True, stderr=subprocess.STDOUT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def oracle(length, seed):
    state = seed
    for index in range(length):
        byte = (17 * index + 3) % 256
        product = ((state ^ byte) * 1099511628211) % (1 << 64)
        state = ((product * 128) % (1 << 64)) + (product // (1 << 57))
    return state


def measure(binary, length, calls, count):
    fields = [int(x) for x in run([binary, length, calls]).strip().split(",")]
    assert fields[:3] == [length, calls, count], fields
    values = [oracle(length, seed) for seed in range(1, count + 1)]
    expected = (sum(values) * (calls // count) + sum(values[:calls % count])) & MASK
    assert fields[4] == expected, (fields, expected)
    return {"length": length, "calls": calls, "policies": count,
            "ns": fields[3], "checksum": fields[4], "ns_per_call": fields[3] / calls}


def main():
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    affinity = None
    if hasattr(os, "sched_getaffinity"):
        affinity = min(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {affinity})
    metadata = {"platform": platform.platform(), "machine": platform.machine(),
                "hostname": platform.node(), "cpu": affinity, "rustc": run(RUSTC + ["-Vv"]),
                "flags": FLAGS, "source_sha256": {}, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for path in [ROOT / "src/lib.rs", ROOT / "examples/probe.rs", Path(__file__).resolve()]:
        metadata["source_sha256"][str(path.relative_to(ROOT))] = sha(path)
    if platform.system() == "Linux":
        metadata["lscpu"] = run(["lscpu"])
        metadata["loadavg_start"] = Path("/proc/loadavg").read_text()
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    test_binary = out / "unit-tests"
    run(RUSTC + ["--edition=2024", "--test", ROOT / "src/lib.rs", "-o", test_binary])
    (out / "tests.txt").write_text(run([test_binary]))
    builds = []
    binaries = {}
    # One warm build, then six balanced fresh rustc invocations per treatment.
    for count in [1, 16]:
        for block in range(-1, 6):
            order = ["generic", "outlined"] if block % 2 == 0 else ["outlined", "generic"]
            for mode in order:
                binary = out / (mode + "-" + str(count))
                cmd = RUSTC + FLAGS + ["--crate-name", "probe", ROOT / "examples/probe.rs", "-o", binary]
                if count == 16:
                    cmd += ["--cfg", "many"]
                if mode == "outlined":
                    cmd += ["--cfg", "outlined"]
                start = time.perf_counter_ns()
                log = run(cmd)
                builds.append({"policies": count, "mode": mode, "block": block,
                               "seconds": (time.perf_counter_ns() - start) / 1e9,
                               "sha256": sha(binary), "file_bytes": binary.stat().st_size})
                (out / (binary.name + "-build.txt")).write_text(log)
                binaries[(count, mode)] = binary
    (out / "builds.json").write_text(json.dumps(builds, indent=2) + "\n")
    checked = 0
    for (count, mode), binary in binaries.items():
        for length in LENGTHS:
            actual = [tuple(map(int, line.split())) for line in run([binary, length, 0]).splitlines()]
            expected = [(seed, oracle(length, seed)) for seed in range(1, count + 1)]
            assert actual == expected, (mode, count, length, actual, expected)
            checked += len(expected)
        if platform.system() == "Linux":
            for tool, args in [("size", ["-A"]), ("nm", ["-S", "--size-sort", "-C"]), ("objdump", ["-d", "-C"])]:
                (out / (binary.name + "-" + tool + ".txt")).write_text(run([tool] + args + [binary]))
    (out / "oracle.json").write_text(json.dumps({"checked_values": checked, "lengths": LENGTHS, "result": "pass"}, indent=2) + "\n")
    rows = []
    for count in [1, 16]:
        for length in [8, 4096]:
            calibration = []
            for mode in ["generic", "outlined"]:
                row = measure(binaries[(count, mode)], length, 10000, count)
                row.update(mode=mode, block=-1, kind="calibration")
                rows.append(row)
                calibration.append(row["ns_per_call"])
            # Equal work in both arms; target at least 0.2 s in the faster pilot.
            calls = max(count, int(200_000_000 / min(calibration)))
            calls = ((calls + count - 1) // count) * count
            for block in range(6):
                order = ["generic", "outlined"] if block % 2 == 0 else ["outlined", "generic"]
                for mode in order:
                    row = measure(binaries[(count, mode)], length, calls, count)
                    row.update(mode=mode, block=block, kind="measured")
                    rows.append(row)
    with (out / "runtime.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"result": "pass", "oracle_values": checked, "runtime_processes": len(rows), "fresh_builds": len(builds), "output": str(out)}))


if __name__ == "__main__":
    main()
