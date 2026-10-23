"""Descriptive within-host paired ratios; no population or causal inference."""
import csv
import itertools
import json
from pathlib import Path
import statistics
import sys

out = {}
for directory in map(Path, sys.argv[1:]):
    if directory.name in out:
        raise RuntimeError(f'duplicate result directory name: {directory.name}')
    with (directory/'samples.csv').open() as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 216:
        raise RuntimeError(f'{directory}: expected exactly 216 measured processes, found {len(rows)}')
    cells = {}
    for n in (256, 65536, 1048576):
        for workload in ('positive', 'signed'):
            cell = [r for r in rows if int(r['n']) == n and r['workload'] == workload]
            blocks = {}
            for r in cell:
                blocks.setdefault(int(r['rep']), {})[int(r['position'])] = r['method']
            orders = sorted(tuple(b.get(p) for p in range(3)) for b in blocks.values())
            if orders != sorted(list(itertools.permutations(('ordered', 'lanes4', 'compensated'))) * 2):
                raise RuntimeError(f'{workload}/{n}: blocks do not cover the six orders exactly twice')
            if len({r['result_bits'] for r in cell}) != 1:
                raise RuntimeError(f'{workload}/{n}: methods disagree on result_bits')
            times = {}
            for mode in ('ordered', 'lanes4', 'compensated'):
                r = sorted((r for r in cell if r['method'] == mode), key=lambda r: int(r['rep']))
                if [int(x['rep']) for x in r] != list(range(12)):
                    raise RuntimeError(f'{workload}/{n}/{mode}: missing or duplicate process block')
                if any(int(x['elapsed_ns']) <= 0 or n * int(x['repeats']) != 1 << 24 for x in r):
                    raise RuntimeError(f'{workload}/{n}/{mode}: invalid elapsed time or work')
                times[mode] = [int(x['elapsed_ns']) / (n * int(x['repeats'])) for x in r]
            pairs = {}
            for a,b in itertools.combinations(times, 2):
                ratios = [x/y for x,y in zip(times[a],times[b])]
                if min(ratios)>1.05: choice=b+' faster'
                elif max(ratios)<1/1.05: choice=a+' faster'
                elif min(ratios)>=1/1.05 and max(ratios)<=1.05: choice='practical tie'
                else: choice='unresolved'
                pairs[a+'/'+b] = {'ratios': ratios, 'median': statistics.median(ratios), 'min': min(ratios), 'max': max(ratios), 'selection':choice}
            cells[f'{workload}/{n}'] = {'ns_per_item':{k:{'median':statistics.median(v),'min':min(v),'max':max(v)} for k,v in times.items()},'paired':pairs}
    out[directory.name]=cells
print(json.dumps(out,indent=2))
