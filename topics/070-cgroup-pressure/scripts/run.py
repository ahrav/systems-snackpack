#!/usr/bin/env python3
"""Run independent paired processes in user-owned transient systemd cgroups."""
import hashlib, itertools, json, os, pathlib, platform, subprocess, sys, time
if sys.flags.optimize:
    raise SystemExit('validation uses assert: run without python -O or PYTHONOPTIMIZE')
root = pathlib.Path(__file__).resolve().parents[1]
out = pathlib.Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=False)
assert platform.system() == 'Linux'

def run(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, timeout=1800)

files = ['Cargo.toml', 'src/lib.rs', 'examples/quota.rs', 'scripts/run.py', 'scripts/analyze.py']
for name in ['RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_RUSTFLAGS', 'CARGO_BUILD_TARGET']:
    os.environ.pop(name, None)
os.environ['CARGO_TARGET_DIR'] = str(root/'target')
identity = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}
workspace = root.parents[1]
workspace_identity = {p: hashlib.sha256((workspace/p).read_bytes()).hexdigest() for p in ['Cargo.toml','Cargo.lock'] if (workspace/p).is_file()}
allowed = sorted(os.sched_getaffinity(0))
# Choose four distinct physical cores when topology is exported.
cpus, seen = [], set()
for cpu in allowed:
    top = pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
    pair = tuple((top/f).read_text().strip() for f in ['physical_package_id', 'core_id'])
    if pair not in seen:
        seen.add(pair); cpus.append(cpu)
    if len(cpus) == 4: break
assert len(cpus) == 4
meta = dict(source_sha256=identity, workspace_sha256=workspace_identity, hostname=platform.node(), uname=run(['uname','-a']),
            cpu=run(['lscpu']), rustc=run(['rustc','-Vv']), systemd=run(['systemd-run','--version']),
            allowed_cpus=allowed, selected_cpus=cpus, flags='cargo --release; default target features',
            target_features=run(['rustc','--print','cfg']),
            protocol='6 process blocks; all 6 worker permutations; order-balanced policy and size; 200ms idle after one small warmup; allocation/spawn/jobs/join timed; oracle and stdout excluded; counters bracket timer sequentially',
            criterion='lowest median wall_ns, >=5% paired improvement and all six paired wins versus every rival; otherwise unresolved',
            policies=['uncapped','q100','q10'], jobs=[64,4096], steps=1000000)
(out/'metadata.json').write_text(json.dumps(meta,indent=2))
(out/'tests.txt').write_text(run(['cargo','test','--manifest-path',str(root/'Cargo.toml')]))
(out/'build.txt').write_text(run(['cargo','build','--release','--example','quota','--manifest-path',str(root/'Cargo.toml')]))
binary = root/'target/release/examples/quota'
(out/'binary.sha256').write_text(hashlib.sha256(binary.read_bytes()).hexdigest()+'\n')
(out/'job-assembly.txt').write_text(run(['objdump','-d',str(binary)]))
records=[]
for block, order in enumerate(itertools.permutations([1,2,4])):
    policies=['uncapped','q100','q10']
    policies=policies[block%3:]+policies[:block%3]
    for policy in policies:
        for jobs in ([64,4096] if block%2==0 else [4096,64]):
            for workers in order:
                unit=f'codex-topic070-{os.getpid()}-{block}-{policy}-{jobs}-{workers}'
                cmd=['systemd-run','--user','--quiet','--wait','--pipe','--collect','--unit',unit,
                     '-p','RuntimeMaxSec=20s','-p','MemoryMax=128M','-p','CPUWeight=100']
                if policy!='uncapped':
                    cmd += ['-p','CPUQuota=50%','-p',f'CPUQuotaPeriodSec={100 if policy=="q100" else 10}ms']
                cmd += ['taskset','-c',','.join(map(str,cpus)),str(binary),str(workers),str(jobs),'1000000']
                begin=time.monotonic_ns()
                result_process=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                result=result_process.stdout
                if result_process.returncode:
                    (out/f'FAILED-{unit}.txt').write_text(result)
                    raise RuntimeError(result)
                launch_ns=time.monotonic_ns()-begin
                (out/f'{block}-{policy}-{jobs}-{workers}.txt').write_text(result)
                values={k:v for line in result.splitlines() if '=' in line for k,v in [line.split('=',1)]}
                assert values['correct']=='true'
                actual=values['cpu_max'].split()
                expected=['max','100000'] if policy=='uncapped' else (['50000','100000'] if policy=='q100' else ['5000','10000'])
                assert actual==expected, (actual, expected)
                assert int(values['cpus_allowed'].replace(',',''),16)==sum(1<<c for c in cpus), (values['cpus_allowed'], cpus)
                row=dict(block=block,policy=policy,jobs=jobs,workers=workers,launch_ns=launch_ns,
                         **{k:(int(v) if v.isdigit() else v) for k,v in values.items()})
                records.append(row)
                (out/'runs.json').write_text(json.dumps(records,indent=2))
print(json.dumps({'host':platform.node(),'processes':len(records),'output':str(out)}))
