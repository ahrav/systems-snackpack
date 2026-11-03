#!/usr/bin/env python3
"""SQLite oracle plus balanced fresh-process join timings. Python 3.9+."""
import argparse
import hashlib
import itertools
import json
import os
import platform
import random
import sqlite3
import statistics
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--binary', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--cpu', type=int)
args = parser.parse_args()
if args.cpu is not None:
    os.sched_setaffinity(0, {args.cpu})
binary = str(Path(args.binary).resolve())
rng = random.Random(9701)
arrays = [list(x) for n in range(4) for x in itertools.product([0, 1, 2], repeat=n)]
cases = list(itertools.product(arrays, arrays))
cases += [([rng.choice([0, 1, 7, 2**32-1]) for _ in range(rng.randrange(65))],
           [rng.choice([0, 1, 7, 2**32-1]) for _ in range(rng.randrange(65))]) for _ in range(500)]
db = sqlite3.connect(':memory:')
db.executescript('CREATE TABLE l(k INTEGER); CREATE TABLE r(k INTEGER);')
expected = []
for a, b in cases:
    db.execute('DELETE FROM l')
    db.execute('DELETE FROM r')
    db.executemany('INSERT INTO l VALUES (?)', ((v,) for v in a))
    db.executemany('INSERT INTO r VALUES (?)', ((v,) for v in b))
    expected.append(db.execute('SELECT count(*) FROM l JOIN r ON l.k=r.k').fetchone()[0])
wire = ''.join(','.join(map(str,a))+';'+','.join(map(str,b))+'\n' for a,b in cases)
actual = subprocess.check_output([binary, 'oracle'], input=wire, text=True).splitlines()
assert len(actual) == len(expected)
for line, want in zip(actual, expected):
    assert list(map(int,line.split())) == [want, want], (line,want)

samples, warmups = [], []
# Fixed repetitions for each algorithm within a workload; no data-dependent tuning.
for mode, reps, count in [('independent',1000,4), ('correlated',100,400),
                          ('exclusive',100000,0), ('dense',10,20000)]:
    for alg in ('nested','hash'):
        row = json.loads(subprocess.check_output([binary,mode,alg,str(reps)],text=True))
        assert row['count'] == count
        warmups.append(row)
    for trial in range(8):
        order = ('nested','hash') if trial % 2 == 0 else ('hash','nested')
        for alg in order:
            row = json.loads(subprocess.check_output([binary,mode,alg,str(reps)],text=True))
            assert row['count'] == count
            row.update(trial=trial,reps=reps)
            samples.append(row)
summary = []
for mode in ('independent','correlated','exclusive','dense'):
    subset = [r for r in samples if r['mode']==mode]
    medians = {}
    entry = {'mode':mode}
    for alg in ('nested','hash'):
        vals = [r['ns'] for r in subset if r['algorithm']==alg]
        medians[alg] = statistics.median(vals)
        entry[alg] = {'median_ns':medians[alg], 'min_ns':min(vals), 'max_ns':max(vals)}
    winner = min(medians,key=medians.get)
    loser = 'hash' if winner == 'nested' else 'nested'
    ratios = [next(r['ns'] for r in subset if r['trial']==t and r['algorithm']==loser)/
              next(r['ns'] for r in subset if r['trial']==t and r['algorithm']==winner) for t in range(8)]
    entry['winner'] = winner if min(ratios)>1.05 else 'unresolved (5% paired margin)'
    entry['paired_ratios'] = ratios
    entry['estimated_plan'] = subset[0]['estimated_plan']
    entry['joint_plan'] = subset[0]['joint_plan']
    entry['estimated_plan_regret'] = medians[entry['estimated_plan']]/min(medians.values())
    entry['joint_plan_regret'] = medians[entry['joint_plan']]/min(medians.values())
    summary.append(entry)
report = dict(platform=platform.platform(),machine=platform.machine(),python=platform.python_version(),
              sqlite=sqlite3.sqlite_version, binary_sha256=hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
              affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else 'uncontrolled',
              oracle_cases=len(cases),oracle_comparisons=len(cases)*2,warmups=warmups,samples=samples,summary=summary)
Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'oracle_comparisons':len(cases)*2,'summary':summary},indent=2))
