from pathlib import Path
import json,statistics,sys
base=Path(sys.argv[1]); result={}; lines=['| Host / workload | Dense ms | Sparse ms | Prealloc ms | Selected |','|---|---:|---:|---:|---|']
for host in ['arm','x86']:
    rows=[json.loads(l) for l in (base/host/'evidence/runs.jsonl').read_text().splitlines()]; rows=[r for r in rows if r['phase']=='measured']
    result[host]={}
    for cell in dict.fromkeys(r['cell'] for r in rows):
        groups={c:sorted([r for r in rows if r['cell']==cell and r['candidate']==c],key=lambda r:r['block']) for c in ['dense','sparse','prealloc']}
        for c,v in groups.items():
            blocks=[r['block'] for r in v]
            if blocks!=list(range(6)):
                raise ValueError(f'{host}/{cell}/{c}: measured blocks {blocks}, expected exactly one of each 0..5')
        times={c:[(r['ready_ns']+r['rewrite_ns'])/1e6 for r in v] for c,v in groups.items()}
        winners=[c for c in groups if all(all(b/a>=1.05 for a,b in zip(times[c],times[d])) for d in groups if d!=c)]
        stats={c:{'median_ms':statistics.median(t),'min_ms':min(t),'max_ms':max(t),'allocated_bytes':sorted(set(r['blocks_512']*512 for r in groups[c])),'ready_median_ms':statistics.median(r['ready_ns']/1e6 for r in groups[c]),'rewrite_median_ms':statistics.median(r['rewrite_ns']/1e6 for r in groups[c]),'cleanup_median_ms':statistics.median(r['cleanup_ns']/1e6 for r in groups[c])} for c,t in times.items()}
        selected=winners[0] if winners else 'unresolved'
        result[host][cell]={'selected':selected,'stats':stats,'paired_ratios':{f'{d}/{c}':[b/a for a,b in zip(times[c],times[d])] for c in groups for d in groups if c!=d}}
        lines.append('| '+host+' / '+cell+' | '+' | '.join(f"{stats[c]['median_ms']:.3f} [{stats[c]['min_ms']:.3f}, {stats[c]['max_ms']:.3f}]" for c in groups)+' | '+selected+' |')
(base/'summary.json').write_text(json.dumps(result,indent=2)+'\n'); (base/'results.md').write_text('\n'.join(lines)+'\n'); print('\n'.join(lines))
