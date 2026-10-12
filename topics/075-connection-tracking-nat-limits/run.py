#!/usr/bin/env python3
"""Six paired order-balanced process blocks; all-pair 1.05x speedup selection, no retries."""
import argparse, csv, hashlib, itertools, json, os, pathlib, platform, statistics, subprocess
p=argparse.ArgumentParser(); p.add_argument('--out', required=True); p.add_argument('--source-id', required=True); a=p.parse_args()
root=pathlib.Path(__file__).resolve().parent
out=pathlib.Path(a.out).resolve(); out.mkdir(parents=True,exist_ok=False)
def run(cmd):
    r=subprocess.run(cmd,cwd=root,text=True,capture_output=True)
    if r.returncode: raise RuntimeError(f'{cmd}: {r.returncode}\n{r.stdout}\n{r.stderr}')
    return r.stdout+r.stderr
inputs=['Cargo.toml','src/lib.rs','examples/ports.rs','run.py']
meta={'source_id':a.source_id,'hostname':platform.node(),'uname':list(platform.uname()),'source_sha256':{x:hashlib.sha256((root/x).read_bytes()).hexdigest() for x in inputs},'flags':'rustc -C opt-level=3 -C target-cpu=native; edition 2024','boundary':'full=pool construction,prefill,events,result writes,checksum,pool drop; steady=events,result writes,checksum; result-buffer allocation/drop,trace generation,oracle,process startup excluded','warmup':'one fresh process/candidate/cell; each process also validates its candidate before timing so no cold-cache claim','selection':'unique winner must achieve rival_ns/candidate_ns >=1.05 in all six paired blocks; otherwise unresolved','samples':'six fresh processes per candidate/cell, all six permutations','available_cpus':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else os.cpu_count()}
for name,cmd in [('rustc',['rustc','-Vv']),('cpu',['lscpu']),('kernel',['uname','-a'])]:
    try: meta[name]=run(cmd)
    except (RuntimeError,FileNotFoundError) as e: meta[name]=str(e)
(out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
for name,cmd in [('tests',['cargo','test','--release','--lib']),('doc',['cargo','test','--doc']),('clippy',['cargo','clippy','--all-targets','--','-D','warnings'])]: (out/(name+'.log')).write_text(run(cmd))
(out/'build.log').write_text(run(['rustc','--crate-name','connection_tracking_nat_limits','--crate-type','rlib','--edition=2024','-C','opt-level=3','-C','target-cpu=native','src/lib.rs','-o',str(out/'libports.rlib')]))
(out/'build.log').open('a').write(run(['rustc','--edition=2024','-C','opt-level=3','-C','target-cpu=native','--extern',f'connection_tracking_nat_limits={out}/libports.rlib','examples/ports.rs','-o',str(out/'ports')]))
(out/'codegen.s').write_text(run(['rustc','--crate-name','connection_tracking_nat_limits','--crate-type','rlib','--edition=2024','-C','opt-level=3','-C','target-cpu=native','--emit=asm','src/lib.rs','-o','-']))
meta['binary_sha256']=hashlib.sha256((out/'ports').read_bytes()).hexdigest(); (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
prefix=['taskset','-c',str(meta['available_cpus'][0])] if isinstance(meta['available_cpus'],list) else []
rows=[]; warm=[]
for case,mode in itertools.product(['tiny','crowded','full','spread','skew','short'],['full','steady']):
    for candidate in ['scan','bitmap','tree']: warm.append(run(prefix+[str(out/'ports'),candidate,case,mode]).strip())
    for block,order in enumerate(itertools.permutations(['scan','bitmap','tree'])):
        for candidate in order:
            values=run(prefix+[str(out/'ports'),candidate,case,mode]).strip().split(',')
            row={'block':block,'candidate':values[0],'case':values[1],'mode':values[2],'ns':int(values[3]),'events':int(values[4]),'checksum':int(values[5])}; rows.append(row)
    (out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
(out/'warmup.txt').write_text('\n'.join(warm)+'\n')
summary=[]
for case,mode in itertools.product(['tiny','crowded','full','spread','skew','short'],['full','steady']):
    samples={c:[r['ns'] for r in rows if (r['candidate'],r['case'],r['mode'])==(c,case,mode)] for c in ['scan','bitmap','tree']}
    winners=[c for c in samples if all(all(y/x>=1.05 for x,y in zip(samples[c],samples[other])) for other in samples if other!=c)]
    summary.append({'case':case,'mode':mode,'winner':winners[0] if len(winners)==1 else 'unresolved','samples_ns':samples,'median_min_max_ns':{c:[statistics.median(v),min(v),max(v)] for c,v in samples.items()}})
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary))
