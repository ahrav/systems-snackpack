import json,statistics,pathlib,sys
root=pathlib.Path(sys.argv[1]);rows=[json.loads(x) for x in (root/'runs.jsonl').read_text().splitlines()]
summary=[]
for workload in dict.fromkeys(r['workload'] for r in rows):
    group=[r for r in rows if r['workload']==workload]
    caps=sorted({r['cap'] for r in group});by={c:{r['block']:r['ns_per_response'] for r in group if r['cap']==c} for c in caps}
    assert all(len(v)==6 for v in by.values())
    wins=[c for c in caps if all(by[other][b]/by[c][b]>=1.05 for other in caps if other!=c for b in range(6))]
    record={'workload':workload,'winner':wins[0] if wins else 'unresolved','candidates':{str(c):{'median_us':statistics.median(by[c].values())/1000,'min_us':min(by[c].values())/1000,'max_us':max(by[c].values())/1000,'records':next(r['records'] for r in group if r['cap']==c),'wire_bytes':next(r['wire_bytes'] for r in group if r['cap']==c)} for c in caps}}
    summary.append(record)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
