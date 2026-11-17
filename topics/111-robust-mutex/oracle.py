"""Compare native outcomes with atomic serial transfers, independent of undo code."""
import csv
import sys
from collections import Counter

counts = Counter()
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
assert counts == {"repair": 360, "poison": 12, "premature": 12}, counts
assert len({tuple(row.values()) for row in rows}) == 384
print("PASS:", dict(counts), "total=384")
