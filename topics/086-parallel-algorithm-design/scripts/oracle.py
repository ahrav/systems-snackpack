#!/usr/bin/env python3
"""Independent arbitrary-precision prefix oracle for the probe stdin protocol."""
import json
import random
import subprocess
import sys

rng = random.Random(86)
mask = (1 << 64) - 1
cases = [[], [0], [mask], [mask, 1, 2], [3, 1, 4, 1, 5, 9, 2, 6]]
for n in list(range(2, 34)) + [63, 64, 65, 127, 257]:
    cases.append([rng.getrandbits(64) for _ in range(n)])
rows = [(v, p, xs) for xs in cases for p in [1, 3, 8] for v in ['serial', 'local', 'rescan']]
request = '\n'.join(f'{v} {p} ' + ' '.join(map(str, xs)) for v, p, xs in rows) + '\n'
result = subprocess.run([sys.argv[1], 'oracle'], input=request, text=True, capture_output=True, check=True, timeout=120)
lines = result.stdout.splitlines()
if len(lines) != len(rows):
    raise RuntimeError(f'probe answered {len(lines)} of {len(rows)} requests')
values = 0
for (variant, workers, xs), line in zip(rows, lines):
    total, prefixes = line.split(';')
    actual = [] if not prefixes else [int(x) for x in prefixes.split(',')]
    expected = [sum(xs[:i]) & mask for i in range(len(xs))]
    if actual != expected or int(total) != sum(xs) & mask:
        raise RuntimeError(f'mismatch: {variant} {workers} {xs} -> {total};{actual}, expected {sum(xs) & mask};{expected}')
    values += len(actual) + 1
print(json.dumps({'input_cases': len(cases), 'variant_worker_cases': len(rows), 'checked_values_including_totals': values, 'seed': 86, 'status': 'pass'}))
