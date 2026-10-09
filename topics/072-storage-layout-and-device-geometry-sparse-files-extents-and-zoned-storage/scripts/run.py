#!/usr/bin/env python3
"""Run fixed fresh-process, balanced comparisons on a task-owned Linux directory."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import time

if sys.flags.optimize:
    raise SystemExit('validation uses assert: run without python -O or PYTHONOPTIMIZE')
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
SOURCES = ['Cargo.toml', 'src/lib.rs', 'examples/layout.rs', 'scripts/run.py', 'scripts/summarize.py']
# Cargo reads flags, paths and the compiler from CARGO_* (including
# CARGO_ENCODED_RUSTFLAGS), RUSTC, RUSTC_WRAPPER, RUSTC_WORKSPACE_WRAPPER and config
# files. Environment values take precedence over config files: an empty RUSTFLAGS
# overrides config rustflags and an empty wrapper disables a configured wrapper.
for name in [n for n in os.environ if n.startswith('CARGO_') and n != 'CARGO_HOME']:
    os.environ.pop(name)
# A dynamic-loader interposer can replace the storage calls under measurement.
assert not {'LD_PRELOAD', 'LD_AUDIT'} & set(os.environ), sorted({'LD_PRELOAD', 'LD_AUDIT'} & set(os.environ))
# An absolute RUSTC survives a PATH rewritten through Cargo's [env] table.
rustc_path = shutil.which('rustc')
assert rustc_path, 'rustc is required on PATH'
os.environ.update(RUSTFLAGS='', RUSTC=rustc_path, RUSTC_WRAPPER='', RUSTC_WORKSPACE_WRAPPER='',
                  CARGO_TARGET_DIR=str(ROOT/'target'))
# These environment variables pin release-profile codegen settings to Cargo's documented
# defaults and take precedence over [profile.release] in Cargo config files.
os.environ.update(CARGO_PROFILE_RELEASE_OPT_LEVEL='3', CARGO_PROFILE_RELEASE_DEBUG='false',
                  CARGO_PROFILE_RELEASE_DEBUG_ASSERTIONS='false', CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS='false',
                  CARGO_PROFILE_RELEASE_LTO='false', CARGO_PROFILE_RELEASE_PANIC='unwind',
                  CARGO_PROFILE_RELEASE_INCREMENTAL='false', CARGO_PROFILE_RELEASE_CODEGEN_UNITS='16')
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=False)
DATA = ROOT / 'data'
DATA.mkdir(exist_ok=False)

def command(args, **kwargs):
    return subprocess.run(args, text=True, capture_output=True, check=True, **kwargs)

# An explicit host target outranks a configured build.target.
host_target = next(line.split()[1] for line in command(['rustc','-vV']).stdout.splitlines() if line.startswith('host: '))
os.environ['CARGO_BUILD_TARGET'] = host_target
def source_hashes():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}

identity = {'sha256': source_hashes()}
(OUT/'source-identity.json').write_text(json.dumps(identity, indent=2)+'\n')
cpu = min(os.sched_getaffinity(0))
midr = Path(f'/sys/devices/system/cpu/cpu{cpu}/regs/identification/midr_el1')
meta = {'hostname':platform.node(), 'architecture':platform.machine(),
        'uname':list(platform.uname()), 'allowed_cpus':sorted(os.sched_getaffinity(0)),
        'pinned_cpu':cpu, 'arm_midr': (midr.read_text().strip() if midr.exists() else None), 'start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
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
# The contract requires a disk-backed directory; memory-backed filesystems measure RAM.
fstype = command(['findmnt','-n','-o','FSTYPE','-T',str(DATA)]).stdout.strip()
assert fstype not in ('tmpfs','ramfs','devtmpfs'), fstype
for label,args in [('tests',['cargo','test','--lib','--examples']),('doc',['cargo','test','--doc']),
                   ('clippy',['cargo','clippy','--all-targets','--','-D','warnings']),
                   ('build',['cargo','build','--release','--example','layout','-vv'])]:
    result = subprocess.run(args,text=True,capture_output=True)
    (OUT/(label+'.log')).write_text(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(label)
# The -vv log holds the exact rustc invocation. Package-specific profile tables in Cargo
# config files can override the release settings above, so these assertions verify
# rustc's target and codegen flags.
running = [line for line in (OUT/'build.log').read_text().splitlines() if 'Running `' in line and '--crate-name layout' in line]
assert len(running) == 1, len(running)
tokens = shlex.split(running[0].split('Running `', 1)[1].rsplit('`', 1)[0])
codegen = sorted(tokens[i+1] for i, t in enumerate(tokens[:-1]) if t == '-C')
assert tokens[tokens.index('--target')+1] == host_target, tokens
assert 'opt-level=3' in codegen and 'codegen-units=16' in codegen, codegen
unexpected = [c for c in codegen if c.split('=')[0] in ('lto','panic','debug-assertions','overflow-checks','incremental','debuginfo','target-cpu','target-feature','linker','link-arg','link-args','relocation-model','code-model')]
assert not unexpected, unexpected
messages = [json.loads(line) for line in command(['cargo','build','--release','--example','layout','--message-format=json']).stdout.splitlines()]
executables = [m['executable'] for m in messages if m.get('reason') == 'compiler-artifact' and m.get('executable')]
assert len(executables) == 1, executables
# Measurements run a private copy of the artifact held in the evidence directory.
binary = Path(shutil.copy2(executables[0], OUT/'layout'))
assert source_hashes() == identity['sha256'], 'sources changed during the Cargo gates'
binary_sha256 = hashlib.sha256(binary.read_bytes()).hexdigest()
(OUT/'binary.sha256').write_text(binary_sha256+'\n')
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
assert source_hashes() == identity['sha256'], 'sources changed during measurement'
assert hashlib.sha256(binary.read_bytes()).hexdigest() == binary_sha256, 'binary changed during measurement'
(OUT/'complete.json').write_text(json.dumps({'measured_processes':144,'warmup_processes':24,'map_processes':3,'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})+'\n')
print(json.dumps({'complete':str(OUT),'hostname':platform.node()}))
