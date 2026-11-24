"""Time one verification session per process. Both readers use the same immutable bytes."""
import csv
import json
import platform
import subprocess
import sys
from time import perf_counter_ns
from verity import BLOCK, Reader, build, digest, file_digest, index_bytes


def sample(method, workload):
    data = index_bytes()
    levels, root = build(data)
    flat_pin = digest(data)
    tree_pin = file_digest(len(data), root)
    indices = (129, 130, 384) if workload == "sparse" else range(len(data) // BLOCK)
    expected = sum(indices)
    start = perf_counter_ns()
    if method == "flat":
        if digest(data) != flat_pin:
            raise ValueError("flat digest mismatch")
        total = sum(int.from_bytes(data[i * BLOCK:i * BLOCK + 4], "little") for i in indices)
    else:
        reader = Reader(data, levels, root, tree_pin)
        total = sum(int.from_bytes(reader.read(i)[:4], "little") for i in indices)
    elapsed = perf_counter_ns() - start
    if total != expected:
        raise ValueError("consumer result mismatch")
    return elapsed


if __name__ == "__main__":
    if len(sys.argv) == 3:
        print(sample(*sys.argv[1:]))
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["system", "arch", "workload", "pair", "position", "method", "ns"])
        for pair in range(12):
            for workload in ("sparse", "scan"):
                order = ("flat", "tree") if pair % 2 == 0 else ("tree", "flat")
                for position, method in enumerate(order):
                    ns = json.loads(subprocess.check_output(
                        [sys.executable, __file__, method, workload], text=True))
                    writer.writerow([platform.system(), platform.machine(), workload,
                                     pair, position, method, ns])
                    sys.stdout.flush()
