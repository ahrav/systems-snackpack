#!/usr/bin/env python3
"""Six balanced process blocks; no timing-driven reruns. Usage: run.py BINARY OUTDIR."""
import hashlib, itertools, json, os, pathlib, platform, statistics, subprocess, sys
binary = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=False)
def capture(args):
    p=subprocess.run(args, text=True, capture_output=True, check=True)
    return p.stdout
meta={"hostname":platform.node(),"uname":list(platform.uname()),"available_cpus":len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count(),"compiler":capture(['rustc','-Vv']),"flags":"cargo build --release --example placement; default target features; no target-cpu=native","binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"runner_sha256":hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),"cpu":capture(['sysctl','-n','machdep.cpu.brand_string']) if sys.platform=='darwin' else capture(['lscpu']),"selection":"For each workload and timing boundary, candidate beats every eligible rival by >=5% in ALL six process pairs. Otherwise unresolved. Report all-scheme and HRW/ring64-only eligibility separately.","boundary":"steady: 262144 prehashed-key owner calls plus wrapping checksum and black_box; excludes input, map construction, output and drop. cold: map allocation/build plus first 128 or32768 lookups; excludes input and drop; first pass, not hardware cache flush. One untimed in-process pass before steady; one external warmup per candidate/workload.","independent_unit":"process; six blocks alternate forward/reverse order; 4 candidates x9workloads x6=216 measured plus36 warmup processes"}
(out/'host.json').write_text(json.dumps(meta,indent=2))
(out/'correctness.txt').write_text(capture([str(binary),'check']))
(out/'movement.csv').write_text(capture([str(binary),'movement']))
kinds=['mod','hrw','ring1','ring64']; rows=[]
for n,pattern in itertools.product([8,64,256],['small','uniform','hot']):
    for kind in kinds: capture([str(binary),kind,str(n),pattern])
    for block in range(6):
        for kind in (kinds if block%2==0 else kinds[::-1]):
            row=json.loads(capture([str(binary),kind,str(n),pattern]));row['block']=block
            rows.append(row)
            with (out/'raw.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
summary=[]
for n,pattern in itertools.product([8,64,256],['small','uniform','hot']):
    cell={'nodes':n,'pattern':pattern,'candidates':{}}
    grouped={kind:sorted([r for r in rows if (r['nodes'],r['pattern'],r['kind'])==(n,pattern,kind)],key=lambda r:r['block']) for kind in kinds}
    for kind, rs in grouped.items():
        assert len({r['checksum'] for r in rs})==1
        ns=[r['ns']/r['lookups'] for r in rs]; cold=[r['cold_ns']/1e3 for r in rs]
        cell['candidates'][kind]={'ns_per_lookup_median':statistics.median(ns),'ns_per_lookup_range':[min(ns),max(ns)],'build_first_pass_us_median':statistics.median(cold),'build_first_pass_us_range':[min(cold),max(cold)],'heap_payload_bytes':rs[0]['bytes']}
    for boundary in ['ns','cold_ns']:
        for group, eligible in [('all',kinds),('balanced_options',['hrw','ring64'])]:
            wins=[c for c in eligible if all(all(r[boundary]/s[boundary]>=1.05 for r,s in zip(grouped[other],grouped[c])) for other in eligible if other!=c)]
            cell[f'{boundary}_{group}_winner']=wins[0] if len(wins)==1 else 'unresolved'
    summary.append(cell)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({'measured_processes':len(rows),'summary':str(out/'summary.json')}))
