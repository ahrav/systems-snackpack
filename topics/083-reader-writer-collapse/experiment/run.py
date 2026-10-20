#!/usr/bin/env python3
"""Fixed descriptive comparison. Run from the topic directory; no dependencies."""
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=False)


def run(command, name, env=None, timeout=120):
    before = time.time()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    (OUT / (name + '.json')).write_text(json.dumps(dict(command=command, started=before, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr), indent=2))
    result.check_returncode()
    return result.stdout


identity = dict(platform=platform.platform(), hostname=platform.node(), source_sha256={
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(ROOT.rglob('*')) if p.is_file() and p.suffix in ('.rs', '.py', '.toml')})
identity['rustc'] = run(['rustc', '-Vv'], 'rustc')
assert identity['rustc'].startswith('rustc 1.93.1 '), 'use the declared Rust 1.93.1 toolchain'
cpus = []
if platform.system() == 'Linux':
    topology = run(['lscpu', '-p=CPU,CORE,SOCKET,NODE'], 'topology')
    identity['lscpu'] = run(['lscpu'], 'lscpu')
    allowed = os.sched_getaffinity(0)
    used = set()
    first_location = None
    for line in topology.splitlines():
        if line.startswith('#'):
            continue
        cpu, core, socket, node = map(int, line.split(','))
        if cpu not in allowed:
            continue
        if first_location is None:
            first_location = (socket, node)
        if (socket, node) == first_location and (socket, core) not in used:
            cpus.append(cpu)
            used.add((socket, core))
    assert len(cpus) >= 8, 'requires eight distinct visible cores in one NUMA node'
    cpus = cpus[:8]
identity['cpus'] = cpus
identity['affinity_note'] = 'per-worker singleton affinity verified' if cpus else 'uncontrolled local scheduler'
flags = ['--edition=2024', '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'codegen-units=1', '-C', 'lto=off', '-C', 'panic=unwind']
identity['flags'] = flags
(OUT / 'identity.json').write_text(json.dumps(identity, indent=2))
lib = str(OUT / 'libreader_writer_collapse.rlib')
binary = str(OUT / 'probe')
run(['rustc', 'src/lib.rs', '--crate-type=rlib', '--crate-name=reader_writer_collapse', *flags, '-o', lib], 'build-library')
run(['rustc', 'src/main.rs', '--extern', 'reader_writer_collapse=' + lib, *flags, '-o', binary], 'build-probe')
run(['rustc', '--edition=2024', '--test', 'src/lib.rs', '-o', str(OUT / 'tests')], 'build-tests')
run([str(OUT / 'tests')], 'tests')
run(['rustdoc', '--edition=2024', '--test', 'src/lib.rs', '--extern', 'reader_writer_collapse=' + lib], 'doctests')
run([sys.executable, 'experiment/oracle.py', binary], 'oracle')
identity['binary_sha256'] = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
(OUT / 'identity.json').write_text(json.dumps(identity, indent=2))
env = dict(os.environ)
if cpus:
    env['BENCH_CPUS'] = ','.join(map(str, cpus))
else:
    env.pop('BENCH_CPUS', None)
fields = ['phase', 'rep', 'mode', 'threads', 'ops', 'rounds', 'elapsed_ns', 'checksum']
with (OUT / 'rows.csv').open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    def sample(phase, rep, mode, threads, operations, rounds):
        name = '{}-{}-{}-{}-{}'.format(phase, rep, mode, threads, rounds)
        output = run([binary, 'bench', mode, str(threads), str(operations), str(rounds)], name, env=env, timeout=60)
        row = output.strip().split(',')
        assert len(row) == 6 and row[:4] == [mode, str(threads), str(operations), str(rounds)]
        writer.writerow(dict(zip(fields, [phase, rep] + row)))
        handle.flush()
    # Identical-artifact mechanical A/A, not statistical calibration.
    for label in ('aa0', 'aa1'):
        sample(label, 0, 'rwlock', 4, 250000, 0)
    cells = list(itertools.product((1, 4, 8), (0, 256)))
    modes = ('mutex', 'rwlock', 'snapshot')
    for threads, rounds in cells:
        for mode in modes:
            sample('warmup', 0, mode, threads, 250000 if rounds == 0 else 12000, rounds)
    for rep, order in enumerate(itertools.permutations(modes)):
        for threads, rounds in (cells if rep % 2 == 0 else list(reversed(cells))):
            for mode in order:
                sample('measure', rep, mode, threads, 250000 if rounds == 0 else 12000, rounds)
print('PASS: tests, oracle, A/A mechanics, 18 warmups, 108 measured processes')
