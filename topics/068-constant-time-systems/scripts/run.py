#!/usr/bin/env python3
"""Replay frozen inputs in an isolated build; retain independent process samples."""
import hashlib,json,os,pathlib,platform,shutil,statistics,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path(sys.argv[1]).resolve(); OUT.mkdir(parents=True,exist_ok=False)
FILES=['Cargo.toml','experiment.lock','src/lib.rs','examples/compare.rs','scripts/run.py']
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
frozen=hashes(); build=OUT/'build-input'; (build/'topic').mkdir(parents=True)
for p in FILES:
 dest=build/'topic'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,dest)
shutil.copy2(ROOT/'experiment.lock',build/'Cargo.lock')
(build/'Cargo.toml').write_text('[workspace]\nmembers=["topic"]\nresolver="3"\n[workspace.package]\nedition="2024"\nrust-version="1.93"\n[workspace.lints.rust]\nmissing_docs="deny"\n[workspace.lints.rustdoc]\nbroken_intra_doc_links="deny"\n')
def capture(args):return subprocess.check_output(args,cwd=build,text=True,stderr=subprocess.STDOUT,timeout=120)
cpus=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else list(range(os.cpu_count()))
prefix=['taskset','-c',str(cpus[0])] if sys.platform=='linux' else []
meta={'hostname':platform.node(),'architecture':platform.machine(),'uname':list(platform.uname()),'available_cpus':cpus,'cpu_model':capture(['lscpu']) if sys.platform=='linux' else capture(['sysctl','-n','machdep.cpu.brand_string']),'rustc':capture(['rustc','-Vv']),'target_cfg':capture(prefix+['rustc','--print','cfg','-C','target-cpu=native']),'flags':'-C target-cpu=native -C lto=off','source_sha256':frozen,'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'design':'12 paired blocks per workload; rotate 3 candidates and reverse each second group of 3; fresh processes; 5ms doubling warmup then one timed batch; timer covers indirect call/black_box/checksum, not allocation/oracle/startup/teardown. Resident small buffers only. Select full-scan lowest median only if all paired competitor/winner ratios have second-smallest >1.02 (interval second..eleventh; 99.365% marginal iid sign interval, no familywise claim). early is security-rejected control; xor is uncertified teaching code; no timing-security certification.'}
midr=pathlib.Path(f'/sys/devices/system/cpu/cpu{cpus[0]}/regs/identification/midr_el1'); meta['arm_midr']=midr.read_text().strip() if midr.exists() else None
(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
env=os.environ.copy();env.pop('CARGO_ENCODED_RUSTFLAGS',None);env.pop('CARGO_BUILD_TARGET',None);env.update(RUSTFLAGS=meta['flags'],CARGO_TARGET_DIR=str(OUT/'target'))
def command(args,log):
 with (OUT/log).open('w') as f:subprocess.run(args,cwd=build,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
command(['cargo','test','--locked','--workspace'],'correctness.log')
command(prefix+['cargo','build','--locked','--release','--example','compare'],'build.log')
exe=OUT/'target/release/examples/compare'; meta['binary_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
command(['objdump','-d',str(exe)] if sys.platform=='linux' else ['otool','-tvV',str(exe)],'linked-disassembly.txt')
command(['nm',str(exe)],'symbols.txt')
rows=[]; candidates=['early','xor','subtle']
with (OUT/'processes.jsonl').open('w') as f:
 for n in [16,32,256,4096]:
  for pattern in ['first','last','equal']:
   for block in range(12):
    order=candidates[block%3:]+candidates[:block%3]
    if (block//3)%2:order=list(reversed(order))
    for c in order:
     started=time.perf_counter_ns();row=json.loads(capture(prefix+[str(exe),c,str(n),pattern]));row.update(block=block,process_wall_ns=time.perf_counter_ns()-started)
     rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
summary=[]
for n in [16,32,256,4096]:
 for pattern in ['first','last','equal']:
  series={c:[next(r['ns_call'] for r in rows if (r['n'],r['pattern'],r['block'],r['candidate'])==(n,pattern,b,c)) for b in range(12)] for c in candidates}
  med={c:statistics.median(v) for c,v in series.items()};best=min(['xor','subtle'],key=med.get)
  other=next(c for c in ['xor','subtle'] if c!=best); ratios=sorted(a/b for a,b in zip(series[other],series[best])); interval=[ratios[1],ratios[10]]
  summary.append({'n':n,'pattern':pattern,'median_ns':med,'range_ns':{c:[min(v),max(v)] for c,v in series.items()},'fastest_equality_only':min(med,key=med.get),'fullscan_selection':best if interval[0]>1.02 else 'unresolved','paired_other_over_best':interval,'lowest_fullscan_median':best})
assert frozen==hashes()
assert (build/'Cargo.lock').read_bytes()==(ROOT/'experiment.lock').read_bytes()
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'output':str(OUT),'processes':len(rows)}))
