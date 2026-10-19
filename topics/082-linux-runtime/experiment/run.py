#!/usr/bin/env python3
"""Linux experiment runner: serial processes, fixed CPU, balanced pair order."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
topic = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
cpu = int(sys.argv[2]) if len(sys.argv) > 2 else min(os.sched_getaffinity(0))
assert cpu in os.sched_getaffinity(0)

def call(args):
    return subprocess.check_output([str(x) for x in args], cwd=root, text=True, stderr=subprocess.STDOUT, timeout=180)

facts = {'host': platform.node(), 'uname': platform.uname()._asdict(), 'cpu': cpu,
         'rust': call(['rustc', '-Vv']), 'cc': call(['cc', '--version']),
         'libc': call(['getconf', 'GNU_LIBC_VERSION']), 'lscpu': call(['lscpu']),
         'affinity': sorted(os.sched_getaffinity(0)),
         'source_hashes': {str(p.relative_to(topic)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(topic.rglob('*')) if p.is_file() and 'measurements' not in p.parts}}
(out/'host.json').write_text(json.dumps(facts, indent=2)+'\n')
logs = []
for cmd in [
 ['cargo', 'test', '--locked', '-p', 'topic082-linux-runtime'],
 ['cargo', 'clippy', '--locked', '-p', 'topic082-linux-runtime', '--all-targets', '--', '-D', 'warnings'],
 ['cargo', 'build', '--locked', '--release', '-p', 'topic082-linux-runtime', '--example', 'oracle_cases'],
 ['python3', topic/'experiment/oracle.py', root/'target/release/examples/oracle_cases'],
 ['python3', topic/'experiment/epoll_checks.py'],
]:
    logs.append('$ '+' '.join(map(str,cmd))+'\n'+call(cmd))
for name in ['clock', 'events']:
    logs.append(call(['cc','-O3','-std=c11','-Wall','-Wextra','-Werror',topic/('experiment/'+name+'.c'),'-o',out/name]))
logs.append(call(['taskset','-c',cpu,out/'clock','check']))
logs.append(call([out/'events']))
(out/'validation.txt').write_text('\n'.join(logs))
# Same fixed count in both treatments. Warm each clock/mode once, then six pairs.
rows = []
for clock in ['monotonic','cpu']:
    for mode in ['libc','syscall']:
        r = json.loads(call(['taskset','-c',cpu,out/'clock',mode,clock,1000000]))
        r.update(phase='warmup', block=-1); rows.append(r)
    for block in range(6):
        order = ['libc','syscall'] if block % 2 == 0 else ['syscall','libc']
        for mode in order:
            r = json.loads(call(['taskset','-c',cpu,out/'clock',mode,clock,1000000]))
            r.update(phase='measured', block=block); rows.append(r)
(out/'runs.json').write_text(json.dumps(rows,indent=2)+'\n')
# Trace only short diagnostic runs, never the timed campaign.
for clock in ['monotonic','cpu']:
    for mode in ['libc','syscall']:
        trace = out/('strace-'+clock+'-'+mode+'.txt')
        p = subprocess.run(['strace','-c','-e','trace=clock_gettime','-o',str(trace),
                            str(out/'clock'),mode,clock,'1000'], cwd=root,
                           text=True, capture_output=True, timeout=30)
        (out/('trace-command-'+clock+'-'+mode+'.txt')).write_text(p.stdout+p.stderr+'\nexit='+str(p.returncode)+'\n')
        if p.returncode:
            print('Trace limitation:',p.stderr)
print('PASS: correctness and 24 measured + 4 warmup processes; evidence:',out)
