#!/usr/bin/env python3
"""Apply predeclared 5% paired descriptive rule; emit all ratios and ranges."""
import csv
import itertools
import json
import statistics
import sys

MASK = (1 << 64) - 1
try:
    with open(sys.argv[1], newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
except OSError as error:
    raise SystemExit(f'cannot read raw CSV {sys.argv[1]}: {error}') from error
if len(rows) != 164:
    raise RuntimeError(f'expected 162 measured and 2 A/A rows, found {len(rows)}')
for r in rows:
    n = int(r['n'])
    if int(r['total']) != (n * (n + 1) // 2) & MASK:
        raise RuntimeError(f'row total disagrees with the triangular-number oracle: {r}')
    if not float(r['ns_call']) > 0:
        raise RuntimeError(f'non-positive timing: {r}')
measured = [r for r in rows if r['kind'] == 'measure']
if len(measured) != 162:
    raise RuntimeError(f'expected 162 measured rows, found {len(measured)}')
report = []
for n in [4096, 262144, 4194304]:
    for workers in [1, 4, 8]:
        cells = {v: sorted([r for r in measured if int(r['n']) == n and int(r['workers']) == workers and r['variant'] == v], key=lambda r: int(r['block'])) for v in ['serial', 'local', 'rescan']}
        if any([int(r['block']) for r in a] != list(range(6)) for a in cells.values()):
            raise RuntimeError(f'{n}/{workers}: each variant needs blocks 0..5 exactly once')
        values = {v: [float(r['ns_call']) / n for r in a] for v, a in cells.items()}
        summary = {v: {'median_ns_item': statistics.median(a), 'min': min(a), 'max': max(a)} for v, a in values.items()}
        pairs = []
        for a, b in itertools.combinations(values, 2):
            ratios = [x/y for x,y in zip(values[a], values[b])]
            decision = a if max(ratios) < 1/1.05 else b if min(ratios) > 1.05 else 'tie' if min(ratios) >= 1/1.05 and max(ratios) <= 1.05 else 'unresolved'
            pairs.append({'a': a, 'b': b, 'ratios_a_over_b': ratios, 'decision': decision})
        report.append({'n': n, 'workers': workers, 'variants': summary, 'pairs': pairs})
aa = [float(r['ns_call']) for r in rows if r['kind'] == 'aa']
if len(aa) != 2:
    raise RuntimeError(f'expected 2 A/A rows, found {len(aa)}')
print(json.dumps({'cells': report, 'aa_ratio': aa[0]/aa[1], 'rule': 'Every paired ratio must clear 5 percent; descriptive only.'}, indent=2))
