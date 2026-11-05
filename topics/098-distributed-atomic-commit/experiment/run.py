#!/usr/bin/env python3
"""Run correctness graphs from an extracted committed workspace."""
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[3]
topic = pathlib.Path(__file__).resolve().parents[1]
out = pathlib.Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)

def run(args, **kw):
    return subprocess.run(args, cwd=root, check=True, text=True, **kw)

metadata = {'platform': platform.platform(), 'machine': platform.machine(),
            'python': sys.version, 'source_commit': sys.argv[2],
            'rust': run(['rustc', '+1.93.1', '-Vv'], capture_output=True).stdout}
cpu = pathlib.Path('/proc/cpuinfo')
if cpu.exists():
    (out / 'cpuinfo.txt').write_text(cpu.read_text())
(out / 'host.json').write_text(json.dumps(metadata, indent=2) + '\n')
with (out / 'cargo-test.log').open('w') as log:
    run(['cargo', '+1.93.1', 'test', '-p', 'distributed-atomic-commit'], stdout=log, stderr=subprocess.STDOUT)
for mode, n in [('safe', 2), ('safe', 3), ('timeout', 2), ('early', 2)]:
    graph = out / f'{mode}-{n}.tsv'
    with graph.open('w') as stream:
        run(['cargo', '+1.93.1', 'run', '-q', '-p', 'distributed-atomic-commit', '--example', 'explore',
             '--', mode, str(n)], stdout=stream)
    with (out / f'{mode}-{n}.json').open('w') as stream:
        run([sys.executable, str(topic / 'experiment/oracle.py'), str(graph)], stdout=stream)
(out / 'sha256.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(out.iterdir()) if p.is_file() and p.name != 'sha256.json'}, indent=2) + '\n')
print(json.dumps({'result': 'PASS', 'output': str(out)}))
