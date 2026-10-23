#!/usr/bin/env python3
"""Apply predeclared 5% paired descriptive rule; emit all ratios and ranges."""
import csv
import itertools
import json
import statistics
import sys

rows = list(csv.DictReader(open(sys.argv[1])))
measured = [r for r in rows if r['kind'] == 'measure']
assert len(measured) == 162
report = []
for n in [4096, 262144, 4194304]:
    for workers in [1, 4, 8]:
        cells = {v: sorted([r for r in measured if int(r['n']) == n and int(r['workers']) == workers and r['variant'] == v], key=lambda r: int(r['block'])) for v in ['serial', 'local', 'rescan']}
        assert all([int(r['block']) for r in a] == list(range(6)) for a in cells.values())
        values = {v: [float(r['ns_call']) / n for r in a] for v, a in cells.items()}
        summary = {v: {'median_ns_item': statistics.median(a), 'min': min(a), 'max': max(a)} for v, a in values.items()}
        pairs = []
        for a, b in itertools.combinations(values, 2):
            ratios = [x/y for x,y in zip(values[a], values[b])]
            decision = a if max(ratios) < 1/1.05 else b if min(ratios) > 1.05 else 'tie' if min(ratios) >= 1/1.05 and max(ratios) <= 1.05 else 'unresolved'
            pairs.append({'a': a, 'b': b, 'ratios_a_over_b': ratios, 'decision': decision})
        report.append({'n': n, 'workers': workers, 'variants': summary, 'pairs': pairs})
aa = [float(r['ns_call']) for r in rows if r['kind'] == 'aa']
assert len(aa) == 2
print(json.dumps({'cells': report, 'aa_ratio': aa[0]/aa[1], 'rule': 'Every paired ratio must clear 5 percent; descriptive only.'}, indent=2))
