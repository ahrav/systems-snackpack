#!/usr/bin/env python3
"""Replay exactly 108 independent processes; output path must be new."""
import hashlib,itertools,json,os,pathlib,platform,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parent
OUT=pathlib.Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
assert not any(k in os.environ for k in ('OPENSSL_CONF','OPENSSL_MODULES','OPENSSL_ia32cap','OPENSSL_armcap','DYLD_INSERT_LIBRARIES','LD_PRELOAD')), 'declare crypto overrides explicitly in a separate campaign'
flags=['-std=c11','-O3','-Wall','-Wextra','-Werror']
pkg=subprocess.check_output(['pkg-config','--cflags','--libs','openssl'],text=True).split()
command=['cc',*flags,str(ROOT/'probe.c'),*pkg,'-o',str(OUT/'probe')]
subprocess.run(command,check=True,capture_output=True)
meta={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hostname':platform.node(),'platform':platform.platform(),'architecture':platform.machine(),'cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else 'uncontrolled macOS scheduling','compiler':subprocess.check_output(['cc','--version'],text=True),'openssl':subprocess.check_output(['openssl','version','-a'],text=True),'command':command,'hashes':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('probe.c','run.py')},'binary_sha256':hashlib.sha256((OUT/'probe').read_bytes()).hexdigest(),'boundary':'steady-state encrypt + memory BIO copies + decrypt + byte-count checks; 8 warmup responses; fixture/key generation/handshake, framing and full-byte oracle, buffers, startup and final teardown excluded; setup and teardown separately recorded; no network','criterion':'winner only if every paired rival/candidate ratio >=1.05 across six balanced blocks; otherwise unresolved, not equivalence'}
if sys.platform=='darwin':meta['cpu_model']=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
else:meta['cpuinfo']=pathlib.Path('/proc/cpuinfo').read_text()
(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
workloads=[('tiny',128,128),('one_k',1024,1024),('sixteen_k',16384,16384),('bulk',1048576,1048576),('tiny_writes',16384,128),('four_k_writes',1048576,4096)]
rows=[]
for block,order in enumerate(itertools.permutations([1024,4096,16384])):
    for name,n,write in workloads[block%len(workloads):]+workloads[:block%len(workloads)]:
        for cap in order:
            r=subprocess.run([str(OUT/'probe'),str(cap),str(n),str(write),str(max(8,4194304//n))],check=True,text=True,capture_output=True)
            row=json.loads(r.stdout);row.update(workload=name,block=block,order=list(order))
            assert row['correct'];rows.append(row)
            with (OUT/'runs.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print('block',block,'complete',flush=True)
assert len(rows)==108
print('108 correct independent processes',flush=True)
