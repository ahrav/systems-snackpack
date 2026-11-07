"""Six balanced permutations; fresh Python workers, Rust chunker child per file."""
import itertools
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from hashlib import sha256
from cas import Store, chunks

MODES = ["whole", "fixed", "cdc"]
WORKLOADS = ["identical", "insert", "overwrite", "unrelated"]


def data(seed):
    return b"".join(sha256(seed + i.to_bytes(4, "little")).digest() for i in range(32768))


def worker(binary, workload, mode):
    a = data(b"a")
    b = {"identical": lambda: a, "insert": lambda: a[:12345]+b"!"+a[12345:],
         "overwrite": lambda: a[:12288]+bytes(4096)+a[16384:],
         "unrelated": lambda: data(b"b")}[workload]()
    start = time.perf_counter_ns()
    store = Store()
    lengths = []
    for name, content in [("a", a), ("b", b)]:
        parts = chunks(binary, mode, content)
        lengths.extend(map(len, parts))
        store.publish(name, parts)
    elapsed = time.perf_counter_ns() - start
    assert store.restore(store.roots["a"]) == a
    assert store.restore(store.roots["b"]) == b
    payload = sum(len(v)-9 for v in store.objects.values() if v.startswith(b"chunk-v1\0"))
    return {"ns": elapsed, "logical": len(a)+len(b), "payload": payload,
            "encoded_bytes": sum(map(len, store.objects.values())), "objects": len(store.objects),
            "refs": len(lengths), "chunk_mean": statistics.mean(lengths),
            "chunk_stdev": statistics.pstdev(lengths), "chunk_min": min(lengths), "chunk_max": max(lengths)}


def run(binary):
    result = {"host": platform.platform(), "machine": platform.machine(), "python": sys.version,
              "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
              "cells": {}}
    def one(w, m):
        return json.loads(subprocess.check_output([sys.executable, __file__, binary, w, m]))
    for workload in WORKLOADS:
        for mode in MODES:
            one(workload, mode)
        samples = {m: [] for m in MODES}
        for order in itertools.permutations(MODES):
            for mode in order:
                samples[mode].append(one(workload, mode))
        result["cells"][workload] = samples
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    if len(sys.argv) == 4:
        print(json.dumps(worker(*sys.argv[1:])))
    else:
        run(sys.argv[1])
