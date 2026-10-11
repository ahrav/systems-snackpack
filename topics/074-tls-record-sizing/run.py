#!/usr/bin/env python3
"""Replay exactly 108 independent processes; output path must be new.

Every gate is an explicit conditional so `python -O` cannot disable it. Source
hashes are taken before compilation, and source and binary hashes are rechecked
after the campaign, so metadata describes the exact inputs behind every row.
Each row must echo its invocation arguments and report the same loaded-library
identity; metadata.json records that identity under `library` and keeps the
`openssl` CLI banner separately as `openssl_cli`. Rows accumulate in
`runs.jsonl.partial`; `runs.jsonl` exists only after every gate passes, so
`analyze.py` consumes only a validated campaign.
"""
import hashlib,itertools,json,os,pathlib,platform,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parent
if any(k in os.environ for k in ('OPENSSL_CONF','OPENSSL_MODULES','OPENSSL_ia32cap','OPENSSL_armcap','DYLD_INSERT_LIBRARIES','LD_PRELOAD')):sys.exit('declare crypto overrides explicitly in a separate campaign')
OUT=pathlib.Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
sha256=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={f:sha256(ROOT/f) for f in ('probe.c','run.py')}
flags=['-std=c11','-O3','-Wall','-Wextra','-Werror']
pkg=subprocess.check_output(['pkg-config','--cflags','--libs','openssl'],text=True).split()
command=['cc',*flags,str(ROOT/'probe.c'),*pkg,'-o',str(OUT/'probe')]
subprocess.run(command,check=True,capture_output=True)
meta={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hostname':platform.node(),'platform':platform.platform(),'architecture':platform.machine(),'cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else 'uncontrolled macOS scheduling','compiler':subprocess.check_output(['cc','--version'],text=True),'openssl_cli':subprocess.check_output(['openssl','version','-a'],text=True),'command':command,'hashes':sources,'binary_sha256':sha256(OUT/'probe'),'boundary':'steady-state encrypt + memory BIO copies + decrypt + byte-count checks; 8 warmup responses; fixture/key generation/handshake, framing and full-byte oracle, buffers, startup and final teardown excluded; setup and teardown separately recorded; no network','criterion':'winner only if every paired rival/candidate ratio >=1.05 across six balanced blocks; otherwise unresolved, not equivalence'}
if sys.platform=='darwin':meta['cpu_model']=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
else:meta['cpuinfo']=pathlib.Path('/proc/cpuinfo').read_text()
(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
workloads=[('tiny',128,128),('one_k',1024,1024),('sixteen_k',16384,16384),('bulk',1048576,1048576),('tiny_writes',16384,128),('four_k_writes',1048576,4096)]
rows=[]
for block,order in enumerate(itertools.permutations([1024,4096,16384])):
    for name,n,write in workloads[block%len(workloads):]+workloads[:block%len(workloads)]:
        for cap in order:
            reps=max(8,4194304//n);r=subprocess.run([str(OUT/'probe'),str(cap),str(n),str(write),str(reps)],check=True,text=True,capture_output=True)
            row=json.loads(r.stdout)
            if not row['correct']:sys.exit(f'incorrect row rejected: {row}')
            if (row['cap'],row['length'],row['write_size'],row['repeats'])!=(cap,n,write,reps):sys.exit(f'row echoes ({row["cap"]},{row["length"]},{row["write_size"]},{row["repeats"]}) for invocation ({cap},{n},{write},{reps}); rejected')
            if meta.setdefault('library',row['library'])!=row['library']:sys.exit(f"loaded library identity changed during the campaign: {meta['library']} then {row['library']}")
            row.update(workload=name,block=block,order=list(order))
            rows.append(row)
            with (OUT/'runs.jsonl.partial').open('a') as f:f.write(json.dumps(row)+'\n')
    print('block',block,'complete',flush=True)
if len(rows)!=108:sys.exit(f'expected 108 rows, recorded {len(rows)}')
if {f:sha256(ROOT/f) for f in sources}!=sources or sha256(OUT/'probe')!=meta['binary_sha256']:sys.exit('source or binary changed during the campaign; evidence rejected')
(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
(OUT/'runs.jsonl.partial').rename(OUT/'runs.jsonl')
print('108 correct independent processes',flush=True)
