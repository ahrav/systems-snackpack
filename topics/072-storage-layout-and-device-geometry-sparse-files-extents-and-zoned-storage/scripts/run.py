#!/usr/bin/env python3
"""Run fixed fresh-process, balanced comparisons on a task-owned Linux directory."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SOURCES = ['Cargo.toml', 'src/lib.rs', 'examples/layout.rs', 'scripts/run.py', 'scripts/summarize.py']
# Cargo reads flags and paths from CARGO_* (including CARGO_ENCODED_RUSTFLAGS) and
# config files; an empty RUSTFLAGS overrides config rustflags.
for name in [n for n in os.environ if n.startswith('CARGO_') and n != 'CARGO_HOME']:
    os.environ.pop(name)
os.environ['RUSTFLAGS'] = ''
os.environ['CARGO_TARGET_DIR'] = str(ROOT/'target')
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=False)
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=False)

def command(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, check=True, **kwargs)

identity = {'sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}}
(OUT/'source-identity.json').write_text(json.dumps(identity, indent=2)+'\n')
cpu = min(os.sched_getaffinity(0))
meta = {'hostname':platform.node(), 'architecture':platform.machine(),
        'uname':list(platform.uname()), 'allowed_cpus':sorted(os.sched_getaffinity(0)),
        'pinned_cpu':cpu, 'arm_midr': (Path('/sys/devices/system/cpu/cpu0/regs/identification/midr_el1').read_text().strip() if Path('/sys/devices/system/cpu/cpu0/regs/identification/midr_el1').exists() else None), 'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'flags':'cargo --release; default target CPU; no RUSTFLAGS; taskset one allowed CPU',
        'source':identity, 'commands':{}}
assert meta['architecture'] in ('aarch64','x86_64')
for args in [['rustc','-Vv'],['rustc','--print','cfg'],['lscpu'],['df','-T',str(DATA)],
             ['findmnt','-T',str(DATA),'-o','TARGET,SOURCE,FSTYPE,OPTIONS'],
             ['lsblk','-o','NAME,TYPE,SIZE,LOG-SEC,PHY-SEC,ZONED,MOUNTPOINT'],
             ['filefrag','-V']]:
    result = subprocess.run(args,text=True,capture_output=True)
    meta['commands'][' '.join(args)] = {'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
(OUT/'host.json').write_text(json.dumps(meta,indent=2)+'\n')
failed_probes = [name for name, r in meta['commands'].items() if r['exit']]
assert not failed_probes, failed_probes
for label,args in [('tests',['cargo','test','--lib','--examples']),('doc',['cargo','test','--doc']),
                   ('clippy',['cargo','clippy','--all-targets','--','-D','warnings']),
                   ('build',['cargo','build','--release','--example','layout','-vv'])]:
    result = subprocess.run(args,text=True,capture_output=True)
    (OUT/(label+'.log')).write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(label)
binary = ROOT/'target/release/examples/layout'
(OUT/'binary.sha256').write_text(hashlib.sha256(binary.read_bytes()).hexdigest()+'\n')
workloads = [('small_empty',65536,'empty'),('small_scatter',65536,'scattered'),
             ('small_dense',65536,'dense'),('large_empty',16777216,'empty'),
             ('large_scatter',16777216,'scattered'),('large_cluster',16777216,'clustered'),
             ('large_dense',16777216,'dense'),('tail_scatter',65553,'scattered')]
candidates = ['dense','sparse','prealloc']
contract = {'workloads':workloads,'candidates':candidates,'process_blocks':6,
 'order':list(itertools.permutations(candidates)), 'warmups_per_candidate_cell':1,
 'primary':'ready_ns + rewrite_ns; each ends in sync_all; verification read between phases',
 'selection':'winner only if every rival / candidate >= 1.05 in all six paired blocks; otherwise unresolved',
 'dispersion':'median and min/max across six independent processes per candidate-cell',
 'excluded':'process startup, precomputed offsets and buffers, full byte oracles, reporting, close/unlink',
 'controls':'new private regular files on existing filesystem; no global cache drop; buffered IO; overwrite is cache-warm after verification; no crash/power-loss or physical SSD inference'}
(OUT/'contract.json').write_text(json.dumps(contract,indent=2)+'\n')
with (OUT/'runs.jsonl').open('w') as log:
    for cell,length,pattern in workloads:
        for candidate in candidates:
            r=json.loads(command(['taskset','-c',str(cpu),str(binary),str(DATA),candidate,str(length),pattern]).stdout)
            r.update(cell=cell,phase='warmup',block=-1); log.write(json.dumps(r)+'\n'); log.flush()
        for block,order in enumerate(itertools.permutations(candidates)):
            for slot,candidate in enumerate(order):
                r=json.loads(command(['taskset','-c',str(cpu),str(binary),str(DATA),candidate,str(length),pattern]).stdout)
                r.update(cell=cell,phase='measured',block=block,slot=slot)
                log.write(json.dumps(r)+'\n'); log.flush()
# Small retained diagnostic files: maps are queried after validation and close.
# Unwritten extent flags remain useful; SEEK classification can change after reads.
for candidate in candidates:
    command([str(binary),str(DATA),candidate,'16777216','scattered','keep'])
    files=list(DATA.glob('probe-*.dat')); assert len(files)==1
    file=files[0]
    result=command(['filefrag','-v',str(file)])
    (OUT/(candidate+'-filefrag.txt')).write_text(result.stdout+result.stderr)
    (OUT/(candidate+'-stat.txt')).write_text(command(['stat','-c','size=%s blocks_512=%b io_hint=%o',str(file)]).stdout)
    file.unlink()
assert not list(DATA.iterdir())
(OUT/'complete.json').write_text(json.dumps({'measured_processes':144,'warmup_processes':24,'map_processes':3,'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
print(json.dumps({'complete':str(OUT),'hostname':platform.node()}))
