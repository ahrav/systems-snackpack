#!/usr/bin/env python3
"""Native exact-source runner. Output is external to the source tree."""
import hashlib,json,os,pathlib,platform,statistics,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True,exist_ok=False)
SOURCES=['Cargo.toml','build.rs','c/kernel.c','src/lib.rs','examples/compare.rs','scripts/run.py']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
def capture(args):
    r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,cwd=ROOT)
    if r.returncode:raise RuntimeError(str(args)+'\n'+r.stdout)
    return r.stdout
available=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else list(range(os.cpu_count()))
meta={'hostname':platform.node(),'architecture':platform.machine(),'uname':list(platform.uname()),'cpus_available':available,'affinity_cpu':available[0] if sys.platform=='linux' else None,'rustc':capture(['rustc','-Vv']),'cc_command':os.environ.get('CC','cc'),'cc':capture([os.environ.get('CC','cc'),'--version']),'source_sha256':hashes,'rustflags':'-C target-cpu=native -C lto=off','c_flags':'-std=c11 -O3 -fno-lto -Wall -Wextra -Werror '+('-mcpu=native' if platform.machine() in ['aarch64','arm64'] else '-march=native'),'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'design':'10 paired balanced blocks, rotating order then reverse; fixed 10ms doubling calibration before timed loop; fresh process per candidate/workload; medians and paired order-statistic interval [2nd,9th] for 10 pairs (97.85% marginal under iid continuous pairs); fastest declared only when all paired competitor/candidate interval lower ends exceed 1.02; otherwise unresolved; no multiplicity-adjusted simultaneous claim.'}
meta['cpu_model']=capture(['lscpu']) if sys.platform=='linux' else capture(['sysctl','-n','machdep.cpu.brand_string'])
meta['cpu_identification']=pathlib.Path('/proc/cpuinfo').read_text() if sys.platform=='linux' else meta['cpu_model']
meta['arm_midr']=pathlib.Path('/sys/devices/system/cpu/cpu0/regs/identification/midr_el1').read_text().strip() if pathlib.Path('/sys/devices/system/cpu/cpu0/regs/identification/midr_el1').exists() else None
meta['target_cfg']=capture(['rustc','--print','cfg','-C','target-cpu=native'])
(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
env=os.environ.copy();env.pop('CARGO_ENCODED_RUSTFLAGS',None);env.update(RUSTFLAGS=meta['rustflags'],TOPIC67_NATIVE='1',CARGO_TARGET_DIR=str(OUT/'target'))
def command(args,log):
    with (OUT/log).open('w') as f:
        subprocess.run(args,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
command(['cargo','test','--manifest-path',str(ROOT/'Cargo.toml')],'correctness.log')
command(['cargo','build','--release','--example','compare','--manifest-path',str(ROOT/'Cargo.toml')],'build.log')
exe=OUT/'target/release/examples/compare'
meta['binary_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
if sys.platform=='linux':
    command(['objdump','-d',str(exe)],'linked-disassembly.txt')
    command(['nm','-n',str(exe)],'symbols.txt')
else:
    command(['otool','-tvV',str(exe)],'linked-disassembly.txt')
prefix=['taskset','-c',str(available[0])] if sys.platform=='linux' else []
candidates=['rust','scalar','chunk256','batch','copy']; rows=[]
with (OUT/'processes.jsonl').open('w') as f:
    for n in [1,31,4096,1048576]:
        for rounds in [0,16]:
            for block in range(10):
                order=candidates[block%5:]+candidates[:block%5]
                if block>=5:order=list(reversed(order))
                for candidate in order:
                    start=time.perf_counter_ns()
                    row=json.loads(subprocess.check_output(prefix+[str(exe),candidate,str(n),str(rounds)],text=True,timeout=120))
                    row.update(block=block,process_wall_ns=time.perf_counter_ns()-start)
                    rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
summary=[]
for n in [1,31,4096,1048576]:
 for rounds in [0,16]:
    series={c:[next(r['ns_request'] for r in rows if (r['n'],r['rounds'],r['block'],r['candidate'])==(n,rounds,b,c)) for b in range(10)] for c in candidates}
    med={c:statistics.median(v) for c,v in series.items()}; best=min(med,key=med.get)
    intervals={c:[sorted(a/b for a,b in zip(series[c],series[best]))[i] for i in [1,8]] for c in candidates if c!=best}
    summary.append({'n':n,'rounds':rounds,'median_ns':med,'range_ns':{c:[min(v),max(v)] for c,v in series.items()},'lowest_median':best,'selection':best if all(v[0]>1.02 for v in intervals.values()) else 'unresolved','paired_ratio_intervals_to_lowest':intervals})
assert hashes=={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'output':str(OUT),'processes':len(rows),'summary':summary}))
