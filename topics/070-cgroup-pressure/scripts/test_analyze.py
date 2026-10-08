#!/usr/bin/env python3
"""analyze.py accepts exactly the frozen 6x3x2x3 matrix and rejects substituted tuples."""
import itertools
import json
import pathlib
import subprocess
import sys
import tempfile
analyze = pathlib.Path(__file__).with_name('analyze.py')

def rows():
    return [dict(block=b, policy=p, jobs=j, workers=w, correct='true', wall_ns=1000*w+b,
                 **{'delta_cpu.stat.usage_usec': 1, 'delta_cpu.pressure.some': 1, 'delta_cpu.stat.throttled_usec': 1})
            for b, p, j, w in itertools.product(range(6), ['uncapped', 'q100', 'q10'], [64, 4096], [1, 2, 4])]

def analyze_exit(matrix, *flags):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(matrix, f)
    try:
        return subprocess.run([sys.executable, *flags, str(analyze), f.name], text=True, capture_output=True, timeout=60).returncode
    finally:
        pathlib.Path(f.name).unlink()

complete = rows()
assert analyze_exit(complete) == 0
substituted = rows()
substituted[0]['workers'] = 3
assert len({(r['block'], r['policy'], r['jobs'], r['workers']) for r in substituted}) == 108
assert analyze_exit(substituted) != 0, 'analyzer accepted an unexpected tuple in place of a required one'
assert analyze_exit(complete[:-1]) != 0
assert analyze_exit(complete, '-O') != 0, 'analyzer ran with assert statements stripped'
print('ok')
