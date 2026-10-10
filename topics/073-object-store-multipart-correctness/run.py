"""Six balanced blocks, one fresh process per candidate and cell per block."""
import csv, hashlib, itertools, json, os, pathlib, platform, statistics, subprocess, sys
root = pathlib.Path(__file__).resolve().parent
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=False)
def run(args):
    return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.STDOUT)
meta = {"hostname": platform.node(), "uname": list(platform.uname()), "available_cpus": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(), "toolchain": run(["rustc", "-Vv"]), "flags": "cargo release default; no RUSTFLAGS; no explicit target features", "boundary": "allocate, validate, normalize, produce output, drop; source generation/oracle/process startup excluded", "selection": "candidate <= 0.95*rival in ALL six paired process blocks against every rival; otherwise unresolved", "inputs": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and ('target' not in p.parts) and p.suffix in ['.rs','.toml','.py']}}
assert not os.environ.get('RUSTFLAGS'), 'clear RUSTFLAGS before running'
if sys.platform == 'darwin': meta['cpu'] = run(['sysctl','-n','machdep.cpu.brand_string'])
else: meta['cpu'] = run(['lscpu']); meta['features'] = run(['rustc','--print','cfg'])
(out/'host.json').write_text(json.dumps(meta,indent=2)+'\n')
for name, args in [('test',['cargo','test']),('clippy',['cargo','clippy','--all-targets','--','-D','warnings']),('build',['cargo','build','--release','--example','manifest'])]:
    (out/f'{name}.log').write_text(run(args))
binary = root/'target/release/examples/manifest'
# Cargo workspace replay may use a shared target; runner accepts an explicit path.
if len(sys.argv)>2: binary=pathlib.Path(sys.argv[2]).resolve()
meta['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
(out/'host.json').write_text(json.dumps(meta,indent=2)+'\n')
cells=[(8,'ordered',1),(8,'shuffle',4),(1024,'reverse',1),(1024,'shuffle',4),(10000,'ordered',1),(10000,'shuffle',4)]
rows=[]
for n,order,copies in cells:
    for c in ['sort','tree','slots']: run([str(binary),c,str(n),order,str(copies)])
    for block, candidates in enumerate(itertools.permutations(['sort','tree','slots'])):
        for c in candidates:
            cmd=[str(binary),c,str(n),order,str(copies)]
            if hasattr(os,'sched_getaffinity'):cmd=['taskset','-c',str(min(os.sched_getaffinity(0)))]+cmd
            line=run(cmd).strip(); (out/'processes.txt').open('a').write(f'{block},{line}\n')
            rows.append({'cell':f'{n}-{order}-{copies}','block':block,'candidate':c,'ns':float(line.split(',')[-1])})
(out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
report=[]
for n,order,copies in cells:
    cell=f'{n}-{order}-{copies}'; values={c:[r['ns'] for r in rows if r['cell']==cell and r['candidate']==c] for c in ['sort','tree','slots']}
    winners=[c for c in values if all(all(x<=.95*y for x,y in zip(values[c],values[r])) for r in values if r!=c)]
    report.append({'cell':cell,'winner':winners[0] if len(winners)==1 else 'unresolved','ns':{c:{'median':statistics.median(v),'min':min(v),'max':max(v)} for c,v in values.items()}})
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
