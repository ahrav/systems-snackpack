#!/usr/bin/env python3
"""Select a per-workload winner only from a complete 108-row campaign.

Every workload needs all three caps across all six blocks; a lone candidate
can never win by comparing against an empty rival set. Gates are explicit
conditionals so `python -O` cannot disable them.
"""
import json,statistics,pathlib,sys
CAPS=[1024,4096,16384];WORKLOADS=['tiny','one_k','sixteen_k','bulk','tiny_writes','four_k_writes'];BLOCKS=list(range(6))
root=pathlib.Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'runs.jsonl').read_text().splitlines()]
if len(rows)!=len(CAPS)*len(WORKLOADS)*len(BLOCKS):sys.exit(f'expected {len(CAPS)*len(WORKLOADS)*len(BLOCKS)} rows, found {len(rows)}')
if sorted({r['workload'] for r in rows})!=sorted(WORKLOADS):sys.exit(f"expected workloads {WORKLOADS}, found {sorted({r['workload'] for r in rows})}")
summary=[]
for workload in WORKLOADS:
    group=[r for r in rows if r['workload']==workload]
    caps=sorted({r['cap'] for r in group});by={c:{r['block']:r['ns_per_response'] for r in group if r['cap']==c} for c in caps}
    if caps!=CAPS:sys.exit(f'{workload}: expected candidates {CAPS}, found {caps}; no winner can be selected from a partial candidate set')
    if any(sorted(v)!=BLOCKS for v in by.values()):sys.exit(f'{workload}: every candidate needs blocks {BLOCKS}, found {{c:sorted(v) for c,v in by.items()}}')
    wins=[c for c in caps if all(by[other][b]/by[c][b]>=1.05 for other in caps if other!=c for b in BLOCKS)]
    record={'workload':workload,'winner':wins[0] if wins else 'unresolved','candidates':{str(c):{'median_us':statistics.median(by[c].values())/1000,'min_us':min(by[c].values())/1000,'max_us':max(by[c].values())/1000,'records':next(r['records'] for r in group if r['cap']==c),'wire_bytes':next(r['wire_bytes'] for r in group if r['cap']==c)} for c in caps}}
    summary.append(record)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
