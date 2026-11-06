"""Compare both Rust methods to materialized SQLite bags after each batch."""
import json
import random
import sqlite3
import subprocess
import sys

rng = random.Random(100)
n = 12
con = sqlite3.connect(":memory:")
con.executescript("create table a(k integer); create table b(k integer);")
a, b = [0] * n, [0] * n
batches, expected = [], []
for step in range(3000):
    changes = [(rng.randrange(n), rng.randrange(-3, 4), rng.randrange(-3, 4))
               for _ in range(rng.randrange(8))]
    if step % 20 == 0:
        changes = [(0, -9, 2), (0, 9, -2)]
    if step % 31 == 0:
        changes += [(n, 1, 1)]
    aa, bb = a[:], b[:]
    valid = True
    for k, da, db in changes:
        if k >= n:
            valid = False
        else:
            aa[k] += da
            bb[k] += db
    valid &= all(0 <= x <= 1_000_000_000 for x in aa + bb)
    if valid:
        a, b = aa, bb
    con.executescript("delete from a; delete from b;")
    con.executemany("insert into a values (?)", [(k,) for k, v in enumerate(a) for _ in range(v)])
    con.executemany("insert into b values (?)", [(k,) for k, v in enumerate(b) for _ in range(v)])
    count = con.execute("select count(*) from a join b using(k)").fetchone()[0]
    expected.append(f"{'ok' if valid else 'err'} {count}")
    batches.append(" ".join(str(v) for change in changes for v in change))
result = subprocess.run([sys.argv[1], "check", str(n)], input="\n".join(batches) + "\n",
                        text=True, capture_output=True, check=True)
assert result.stdout.splitlines() == expected
print(json.dumps({"snapshots": len(expected), "method_comparisons": 2 * len(expected),
                  "accepted": sum(x.startswith("ok") for x in expected), "sqlite": sqlite3.sqlite_version}))
