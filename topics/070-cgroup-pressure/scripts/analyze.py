#!/usr/bin/env python3
"""Summarize one intact runner-produced, single-host runs.json file."""
import json, pathlib, statistics, sys
rows=json.loads(pathlib.Path(sys.argv[1]).read_text())
assert len(rows)==108, 'incomplete experiment: require all 108 process runs'
assert len({(r['block'],r['policy'],r['jobs'],r['workers']) for r in rows})==108
assert all(r['correct']=='true' for r in rows)
for policy in ['uncapped','q100','q10']:
    for jobs in [64,4096]:
        group={w:sorted([r for r in rows if r['policy']==policy and r['jobs']==jobs and r['workers']==w],key=lambda r:r['block']) for w in [1,2,4]}
        med={w:statistics.median(r['wall_ns'] for r in g) for w,g in group.items()}
        best=min(med,key=med.get)
        resolved=all(all(a['wall_ns'] < b['wall_ns'] for a,b in zip(group[best],group[w])) and statistics.median(1-a['wall_ns']/b['wall_ns'] for a,b in zip(group[best],group[w]))>=.05 for w in group if w!=best)
        print(policy,jobs,'selection=',best if resolved else 'unresolved')
        for w,g in group.items():
            times=[r['wall_ns']/1e6 for r in g]
            q=statistics.quantiles(times,n=4,method='inclusive')
            usage=statistics.median(r['delta_cpu.stat.usage_usec']/1000 for r in g)
            pressure=statistics.median(r['delta_cpu.pressure.some']/1000 for r in g)
            throttle=statistics.median(r['delta_cpu.stat.throttled_usec']/1000 for r in g)
            print(f'  w{w}: median={statistics.median(times):.3f} ms IQR=[{q[0]:.3f},{q[2]:.3f}] CPU={usage:.3f} ms PSI_some={pressure:.3f} ms aggregate_throttle={throttle:.3f} ms')
