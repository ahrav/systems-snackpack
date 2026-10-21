"""Reproduce descriptive summaries and the declared six-pair selection rule."""
import csv
import itertools
import json
from pathlib import Path
import statistics
import sys

root = Path(sys.argv[1])
summary = {}
for host in ('arm', 'xxl'):
    rows = list(csv.DictReader((root / host / 'samples.csv').open()))
    if len(rows) != 54:
        raise RuntimeError('expected exactly 54 samples per host')
    cells = []
    for n in (1024, 262144, 16777216):
        by = {m: sorted([r for r in rows if int(r['n']) == n and r['mode'] == m],
                        key=lambda r: int(r['rep'])) for m in ('split', 'blocked', 'fused')}
        modes = {}
        for m, rr in by.items():
            if [int(r['rep']) for r in rr] != list(range(6)):
                raise RuntimeError('missing or duplicate process block')
            if any(int(r['passes']) * n != 1 << 26 for r in rr):
                raise RuntimeError('work mismatch')
            values = [float(r['ns_per_item']) for r in rr]
            if any(v <= 0 for v in values):
                raise RuntimeError('invalid elapsed value')
            modes[m] = dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
        if len({r['checksum'] for rr in by.values() for r in rr}) != 1:
            raise RuntimeError('candidate checksum mismatch')
        pairs = []
        for a, b in itertools.combinations(by, 2):
            ratios = [float(y['ns_per_item']) / float(x['ns_per_item']) for x, y in zip(by[a], by[b])]
            lo, hi = min(ratios), max(ratios)
            result = a if lo > 1.05 else b if hi < 1/1.05 else 'tie' if lo >= 1/1.05 and hi <= 1.05 else 'unresolved'
            pairs.append(dict(a=a, b=b, b_over_a_ratios=ratios, result=result))
        cells.append(dict(n=n, modes=modes, pairs=pairs))
    summary[host] = cells
print(json.dumps(summary, indent=2))
