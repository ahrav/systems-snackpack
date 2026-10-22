"""Descriptive within-host paired ratios; no population or causal inference."""
import csv
import itertools
import json
from pathlib import Path
import statistics
import sys

out = {}
for directory in map(Path, sys.argv[1:]):
    with (directory/'samples.csv').open() as f:
        rows = list(csv.DictReader(f))
    cells = {}
    for n in (256, 65536, 1048576):
        for workload in ('positive', 'signed'):
            times = {}
            for mode in ('ordered', 'lanes4', 'compensated'):
                r = sorted((r for r in rows if int(r['n']) == n and r['workload'] == workload and r['method'] == mode), key=lambda r: int(r['rep']))
                assert len(r) == 12
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
