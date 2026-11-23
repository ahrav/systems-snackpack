"""Collect fresh processes in alternating order. Emit one CSV row per sample."""
import csv
import subprocess
import sys

writer = csv.writer(sys.stdout, lineterminator="\n")
writer.writerow(["target", "pair", "position", "code", "helpers", "read_bytes", "repeats", "total_ns"])
for pair in range(20):
    for target in ((0, 8) if pair % 4 < 2 else (8, 0)):
        order = ("rs", "lrc") if (pair + (target == 8)) % 2 == 0 else ("lrc", "rs")
        for position, code in enumerate(order):
            values = list(map(int, subprocess.check_output(
                [sys.argv[1], "bench", code, str(target)], text=True).split()))
            expected = 3 if code == "lrc" and target == 0 else 6
            assert values[:3] == [expected, expected << 20, 8]
            writer.writerow([target, pair, position, code, *values])
            sys.stdout.flush()
