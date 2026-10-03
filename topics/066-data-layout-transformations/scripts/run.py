#!/usr/bin/env python3
"""Frozen six-order process experiment. Requires Rust 1.93+ and Python 3.9+."""
import hashlib
import itertools
import json
import os
import platform
import statistics
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
inputs = [root / p for p in ['src/lib.rs', 'examples/compare.rs', 'scripts/run.py']]
manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
(out / 'source.json').write_text(json.dumps(manifest, indent=2) + '\n')
def run(args):
    return subprocess.check_output([str(x) for x in args], text=True, stderr=subprocess.STDOUT)
available = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
if available:
    os.sched_setaffinity(0, {available[0]})
meta = {'hostname': platform.node(), 'machine': platform.machine(), 'uname': list(platform.uname()),
        'available_cpus': available, 'pinned_cpu': available[0] if available else None,
        'logical_cpu_count': os.cpu_count(), 'rustc': run(['rustc', '-Vv']),
        'flags': ['--edition=2024', '-O', '-C', 'target-cpu=native'],
        'target_cfg': run(['rustc', '--print', 'cfg', '-C', 'target-cpu=native'])}
meta['cpu'] = run(['sysctl', '-n', 'machdep.cpu.brand_string']) if sys.platform == 'darwin' else run(['lscpu'])
(out / 'host.json').write_text(json.dumps(meta, indent=2) + '\n')
(out / 'test-build.txt').write_text(run(['rustc', '--edition=2024', '--test', root/'src/lib.rs', '-o', out/'tests']))
(out / 'tests.txt').write_text(run([out/'tests']))
flags = ['--edition=2024', '-O', '-C', 'target-cpu=native']
(out / 'library-build.txt').write_text(run(['rustc', *flags, '--crate-name', 'data_layout_transformations', '--crate-type', 'rlib', root/'src/lib.rs', '-o', out/'libdata_layout_transformations.rlib']))
(out / 'example-build.txt').write_text(run(['rustc', *flags, root/'examples/compare.rs', '--extern', f'data_layout_transformations={out}/libdata_layout_transformations.rlib', '-o', out/'compare']))
(out / 'assembly-build.txt').write_text(run(['rustc', *flags, '--crate-name', 'data_layout_transformations', '--crate-type', 'lib', '--emit=asm', root/'src/lib.rs', '-o', out/'layout.s']))
(out / 'binary.sha256').write_text(hashlib.sha256((out/'compare').read_bytes()).hexdigest()+'\n')
orders = list(itertools.permutations(['aos', 'soa', 'tile']))
# Every candidate occupies every position twice; each pair appears in both orders equally.
workloads = list(itertools.product([31,4096,1048576], ['narrow','wide','indexed'], ['resident','life1','life16']))
records = []
with (out/'processes.jsonl').open('w') as log:
    for n, op, boundary in workloads:
        for block, order in enumerate(orders):
            for position, candidate in enumerate(order):
                rec=json.loads(run([out/'compare',candidate,n,op,boundary]))
                rec.update(block=block,position=position)
                records.append(rec); log.write(json.dumps(rec)+'\n'); log.flush()
        print(f'finished {n} {op} {boundary}', flush=True)
summary=[]
for n,op,boundary in workloads:
    subset=[r for r in records if (r['n'],r['operation'],r['boundary'])==(n,op,boundary)]
    by={c:[r['ns_per_query'] for r in subset if r['candidate']==c] for c in ['aos','soa','tile']}
    med={c:statistics.median(v) for c,v in by.items()}
    fastest=min(med,key=med.get)
    ratios={c:[by[fastest][i]/by[c][i] for i in range(6)] for c in by if c!=fastest}
    # A strict descriptive rule, not a significance test or population confidence interval.
    decisive=all(max(v)<0.95 for v in ratios.values())
    summary.append({'n':n,'operation':op,'boundary':boundary,'median_ns':med,
                    'minmax_ns':{c:[min(v),max(v)] for c,v in by.items()},
                    'lowest_median':fastest,'selection':fastest if decisive else 'unresolved',
                    'paired_fastest_ratios':ratios})
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
assert manifest == {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}, 'source changed during run'
print(f'{len(records)} processes; all checksums passed')
