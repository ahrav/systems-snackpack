#!/usr/bin/env python3
"""Build pinned committed source, check an independent oracle, then measure."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import subprocess

P = Path(__file__).resolve().parents[1]
MASK = (1 << 64) - 1
VARIANTS = ['generic', 'enum', 'dyn-item', 'dyn-batch']

def command(args, **kw):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kw)

def source_hashes(out):
    """SHA-256 of every committed topic source file, keyed by topic-relative path.

    Generated trees (`measurements/`, `__pycache__/`, and the output directory,
    which may sit inside the topic) are not sources. An output directory that
    holds sources would hide them from the record, so it is rejected up front.
    """
    if P.is_relative_to(out) or any(out.is_relative_to(P/d) for d in ('src', 'experiment')):
        raise SystemExit(f'output directory {out} contains topic sources; choose one outside src/ and experiment/')
    return {str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(P.rglob('*')) if f.is_file() and not f.is_relative_to(out)
            and not {'measurements', '__pycache__'} & set(f.parts)}

def oracle(policy, n, seed, dot=False):
    total = 0
    for i in range(n):
        x = (i * 11400714819323198485 + seed) % (1 << 64)
        if dot:
            y = (i * 11400714819323198485 + ((seed + 17) & MASK)) % (1 << 64)
            value = x * y
        elif policy == 'add':
            value = x + 7
        else:
            y = (x * 7) & MASK
            value = (((y * (1 << 13)) & MASK) + (y // (1 << 51))) ^ 0xd1b54a32d192ed03
        total += value
    return total & MASK

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--cpu', type=int, default=0)
    ap.add_argument('--no-affinity', action='store_true')
    a = ap.parse_args()
    out = a.out.resolve()
    sources = source_hashes(out)
    out.mkdir(parents=True, exist_ok=True)
    if not a.no_affinity:
        os.sched_setaffinity(0, {a.cpu})
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    rust = ['rustup', 'run', '1.93.1', 'rustc']
    flags = ['--edition=2024', '-C', 'opt-level=3', '-C', 'target-cpu=native',
             '-C', 'codegen-units=1', '-C', 'lto=off', '-C', 'panic=unwind']
    lib = out / 'libtopic081_rust_runtime.rlib'
    binary = out / 'runtime'
    commands = [rust + flags + ['--crate-type=rlib', '--crate-name', 'topic081_rust_runtime',
                str(P/'src/lib.rs'), '-o', str(lib)],
                rust + flags + [str(P/'src/main.rs'), '--extern', 'topic081_rust_runtime='+str(lib), '-o', str(binary)],
                rust + ['--edition=2024', '--test', str(P/'src/lib.rs'), '-o', str(out/'tests')]]
    for cmd in commands:
        command(cmd)
    (out/'tests.txt').write_text(command([str(out/'tests')]).stdout)
    (out/'doctests.txt').write_text(command(['rustup','run','1.93.1','rustdoc','--edition=2024',
                                           '--test',str(P/'src/lib.rs')]).stdout)
    panic = {}
    for strategy in ['unwind', 'abort']:
        exe = out / ('panic-'+strategy)
        command(rust + ['--edition=2024','-C','panic='+strategy,str(P/'experiment/panic_probe.rs'),'-o',str(exe)])
        r = subprocess.run([str(exe)], text=True, capture_output=True)
        panic[strategy] = dict(returncode=r.returncode, stdout=r.stdout, stderr=r.stderr)
        if strategy == 'unwind':
            assert r.returncode == 0 and 'DROP_MARKER' in r.stderr and 'CAUGHT_MARKER' in r.stdout
        else:
            assert r.returncode != 0 and 'DROP_MARKER' not in r.stderr and 'CAUGHT_MARKER' not in r.stdout
    (out/'panic.json').write_text(json.dumps(panic, indent=2)+'\n')
    def sample(v, policy, n, reps, seed):
        r = command([str(binary),v,policy,str(n),str(reps),str(seed)])
        fields = r.stdout.strip().split(',')
        assert len(fields) == 7
        assert fields[:2] == [v,policy]
        rn, rr, rs, checksum, ns = map(int, fields[2:])
        assert (rn,rr,rs) == (n,reps,seed)
        assert checksum == (oracle(policy,n,seed,v in ['index','zip'])*reps)&MASK
        return ns
    count = 0
    for n in [0,1,2,3,7,8,15,16,31,32,33,129,8192]:
        for seed in [0,1,MASK]:
            for policy in ['add','mix']:
                for v in VARIANTS:
                    sample(v,policy,n,1,seed)
                    count += 1
            for v in ['index','zip']:
                sample(v,'add',n,1,seed)
                count += 1
    (out/'oracle.json').write_text(json.dumps({'independent_cases':count, 'all_passed':True})+'\n')
    # Each family/cell gets common repetitions. Calibrate the fastest candidate
    # to >=30 ms (bounded at 20 million batches), then one warmup per candidate.
    cells = [(p,n,VARIANTS) for p in ['add','mix'] for n in [32,8192]]
    cells += [('dot',n,['index','zip']) for n in [32,8192]]
    rows=[]
    calibration=[]
    for name,n,variants in cells:
        policy = 'add' if name == 'dot' else name
        reps = max(1, 1000000//n)
        times = [sample(v,policy,n,reps,123) for v in variants]
        reps = min(20000000, max(reps, int(reps * 30000000 / max(1,min(times)))+1))
        calibration.append(dict(policy=name,n=n,initial_times_ns=times,reps=reps))
        for v in variants:
            sample(v,policy,n,reps,123)
        # Cyclic order and its reverse in alternate blocks distribute order effects.
        for block in range(6):
            shift=(block//2)%len(variants)
            order=variants[shift:]+variants[:shift]
            if block%2: order=list(reversed(order))
            for position,v in enumerate(order):
                ns=sample(v,policy,n,reps,123)
                rows.append(dict(policy=name,n=n,block=block,position=position,variant=v,
                                 reps=reps,ns=ns,ns_per_item=ns/(reps*n)))
    with (out/'runtime.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (out/'calibration.json').write_text(json.dumps(calibration,indent=2)+'\n')
    meta=dict(host=platform.node(),uname=list(platform.uname()),
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
        rustc=command(rust+['-Vv']).stdout,commands=commands,
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        sources=sources,
        measured_processes=len(rows),warmup_processes=sum(len(v) for _,_,v in cells),
        calibration_processes=sum(len(v) for _,_,v in cells))
    if platform.system()=='Linux':
        meta['lscpu']=command(['lscpu']).stdout
        full=command(['objdump','-d','-C',str(binary)]).stdout
        # Keep complete function blocks for this crate, from the linked executable.
        blocks=re.split(r'(?=^[0-9a-f]+ <)',full,flags=re.M)
        selected=[b for b in blocks if 'topic081_rust_runtime::' in b.split('\n',1)[0]]
        assert selected
        (out/'kernels.asm').write_text('\n'.join(selected))
        (out/'symbols.txt').write_text(command(['nm','-C','-S',str(binary)]).stdout)
        (out/'size.txt').write_text(command(['size',str(binary)]).stdout)
    (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(json.dumps({'host':meta['host'],'oracle_cases':count,'measured_processes':len(rows)}))

if __name__=='__main__':
    main()
