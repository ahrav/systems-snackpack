#!/usr/bin/env python3
"""Six order-balanced blocks; model counts and simulator elapsed time, no device I/O."""
import hashlib, itertools, json, os, pathlib, platform, subprocess, sys, time
root = pathlib.Path(__file__).resolve().parent
out = pathlib.Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
def command(args):
    return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.STDOUT)
inputs = ['Cargo.toml','src/lib.rs','examples/compare.rs','run.py','EXPERIMENT.md']
meta = {'hostname':platform.node(),'architecture':platform.machine(),'uname':list(platform.uname()),
        'cpuinfo':pathlib.Path('/proc/cpuinfo').read_text(),'allowed_cpus':sorted(os.sched_getaffinity(0)),
        'rustc':command(['rustc','-vV']),'lscpu':command(['lscpu']),
        'build_flags':['--edition=2024','-C','opt-level=3','-C','target-cpu=native'],
        'target_features':command(['rustc','--print','cfg','-C','target-cpu=native']),
        'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in inputs}}
(out/'metadata.json').write_text(json.dumps(meta,indent=2))
for name,args in [
 ('test',['rustc','--edition=2024','--test','src/lib.rs','-o',str(out/'tests')]),
 ('library',['rustc','--edition=2024','--crate-name','ssd_gc','--crate-type','rlib','-C','opt-level=3','-C','target-cpu=native','src/lib.rs','-o',str(out/'libssd_gc.rlib')]),
 ('example',['rustc','--edition=2024','-C','opt-level=3','-C','target-cpu=native','examples/compare.rs','--extern','ssd_gc='+str(out/'libssd_gc.rlib'),'-o',str(out/'compare')])]:
    (out/(name+'.log')).write_text(command(args))
(out/'tests.log').write_text(command([str(out/'tests')]))
(out/'doctest.log').write_text(command(['rustdoc','--edition=2024','--test','src/lib.rs','--extern','ssd_gc='+str(out/'libssd_gc.rlib')]))
(out/'clippy.log').write_text(command(['cargo','clippy','--all-targets','--','-D','warnings']))
workloads = [(b,o,p,20000, b*32*o//100*5) for b in (64,256) for o in (50,90) for p in ('uniform','hot','cyclic')]
workloads += [(64,90,'uniform',32,0)]
orders = list(itertools.permutations(('rr','greedy','sample4')))
cpu = meta['allowed_cpus'][0]
with (out/'runs.jsonl').open('w') as file:
    for cell,(b,o,p,w,warm) in enumerate(workloads):
        for block,order in enumerate(orders):
            for position,policy in enumerate(order):
                args=[str(out/'compare'),policy,str(b),str(o),p,str(w),str(warm),str(71+block)]
                begin=time.monotonic_ns()
                row=json.loads(command(['taskset','-c',str(cpu)]+args))
                row.update(cell=cell,block=block,position=position,cpu=cpu,process_wall_ns=time.monotonic_ns()-begin)
                file.write(json.dumps(row)+'\n'); file.flush()
meta['binary_sha256']=hashlib.sha256((out/'compare').read_bytes()).hexdigest()
(out/'metadata.json').write_text(json.dumps(meta,indent=2))
print(json.dumps({'status':'PASS','rows':len(workloads)*18,'host':platform.node(),'output':str(out)}))
