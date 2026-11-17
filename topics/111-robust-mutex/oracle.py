"""Compare native outcomes with atomic serial transfers, independent of undo code."""
import csv
import sys
from collections import Counter

if sys.flags.optimize:
    raise SystemExit("validation uses assert: run without python -O or PYTHONOPTIMIZE")

expected = Counter()
for a in (10, 40, 60, 100):
    for amount in (1, a // 2, a):
        expected.update((a, amount, point, cut, "repair") for point in range(6) for cut in range(-1, 4))
        expected.update((a, amount, 3, -1, mode) for mode in ("poison", "premature"))

counts = Counter()
seen = Counter()
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
for row in rows:
    a, amount, point, cut, left, right = (int(row[k]) for k in
        ("initial", "amount", "point", "repair_cut", "a", "b"))
    mode = row["mode"]
    if mode == "repair":
        delta = amount if point == 5 else 0
        assert (left, right) == (a - delta, 100 - a + delta), row
    elif mode == "premature":
        assert point == 3 and cut == -1
        assert (left, right) == (a - amount, 100 - a) and left + right != 100, row
    else:
        assert mode == "poison" and point == 3 and cut == -1, row
    counts[mode] += 1
    seen[a, amount, point, cut, mode] += 1
assert seen == expected, ("native.c matrix: missing", expected - seen, "unexpected", seen - expected)
print("PASS:", dict(counts), "total=384")
