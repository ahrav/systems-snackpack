#!/usr/bin/env python3
"""Print descriptive medians and ranges across paired process observations."""
import json
import statistics
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text())
print('| Mask | Treatment | Batch | Pairs | Fused ns/row | Treatment ns/row | Paired treatment/fused median [min,max] |')
print('|---:|---|---:|---:|---:|---:|---|')
for mask in sorted({r['mask'] for r in rows}, reverse=True):
    for mode, batch in [('row', 1024), ('batch', 64), ('batch', 1024), ('batch', 16384), ('fused', 1024)]:
        selected = [r for r in rows if (r['mask'], r['treatment'], r['batch']) == (mask, mode, batch)]
        base, treatment, ratios = [], [], []
        for pair in sorted({r['pair'] for r in selected}):
            items = {r['arm']: r for r in selected if r['pair'] == pair}
            def per_row(r):
                value = r['result']
                return int(value['warm_ns']) / int(value['repeats']) / int(value['n'])
            a, b = per_row(items['baseline']), per_row(items['treatment'])
            base.append(a)
            treatment.append(b)
            ratios.append(b/a)
            assert items['baseline']['result']['sum'] == items['treatment']['result']['sum']
        print(f'| {mask} | {mode} | {batch} | {len(ratios)} | {statistics.median(base):.3f} | {statistics.median(treatment):.3f} | {statistics.median(ratios):.3f} [{min(ratios):.3f}, {max(ratios):.3f}] |')
print('\nAll first scans follow initialized and oracle-read inputs; they are not cold-cache samples.')
for field in ['process_ns', 'setup_ns', 'first_ns']:
    values = [int(r.get(field, r['result'].get(field))) / 1e6 for r in rows]
    print(f'{field}: median {statistics.median(values):.3f} ms, range [{min(values):.3f}, {max(values):.3f}] across all treatments (descriptive mixture).')
