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

if sys.flags.optimize:
    raise SystemExit('validation uses assert: run without python -O or PYTHONOPTIMIZE')

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ['--edition=2024', '-C', 'opt-level=3', '-C', 'target-cpu=native', '-C', 'codegen-units=1', '-C', 'lto=off', '-C', 'panic=unwind']
FIELDS = ['phase', 'rep', 'mode', 'threads', 'ops', 'rounds', 'elapsed_ns', 'checksum']


def run(out, command, name, env=None, timeout=120):
    """Run one command and retain its record as `<name>.json`, including timeouts."""
    before = time.time()
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as expired:
        # TimeoutExpired carries the raw captured bytes even in text mode.
        partial = [None if stream is None else stream.decode(errors='replace') for stream in (expired.stdout, expired.stderr)]
        record = {'command': command, 'started': before, 'returncode': None, 'timeout': timeout, 'stdout': partial[0], 'stderr': partial[1]}
        (out / (name + '.json')).write_text(json.dumps(record, indent=2))
        raise
    record = {'command': command, 'started': before, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    (out / (name + '.json')).write_text(json.dumps(record, indent=2))
    result.check_returncode()
    return result.stdout


def source_hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ROOT.rglob('*')) if p.is_file() and p.suffix in ('.rs', '.py', '.toml')}


def select_cpus(topology, allowed):
    """Eight allowed CPUs on distinct cores of one socket/NUMA node, in `lscpu -p` order.

    Nodes are considered in first-appearance order; the first node exposing eight
    allowed cores is chosen, so a cpuset that fragments an earlier node does not
    reject a host that satisfies the requirement elsewhere.
    """
    nodes = {}
    for line in topology.splitlines():
        if line.startswith('#'):
            continue
        cpu, core, socket, node = map(int, line.split(','))
        if cpu in allowed:
            nodes.setdefault((socket, node), {}).setdefault(core, cpu)
    for cores in nodes.values():
        if len(cores) >= 8:
            return list(cores.values())[:8]
    raise AssertionError('requires eight distinct visible cores in one NUMA node')


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: run.py OUTPUT_DIRECTORY (must not exist yet)')
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    identity: dict = {'platform': platform.platform(), 'hostname': platform.node(), 'source_sha256': source_hashes()}
    identity['rustc'] = run(out, ['rustc', '-Vv'], 'rustc')
    assert identity['rustc'].startswith('rustc 1.93.1 '), 'use the declared Rust 1.93.1 toolchain'
    cpus = []
    if platform.system() == 'Linux':
        topology = run(out, ['lscpu', '-p=CPU,CORE,SOCKET,NODE'], 'topology')
        identity['lscpu'] = run(out, ['lscpu'], 'lscpu')
        cpus = select_cpus(topology, os.sched_getaffinity(0))
    identity['cpus'] = cpus
    identity['affinity_note'] = 'per-worker singleton affinity verified' if cpus else 'uncontrolled local scheduler'
    identity['flags'] = FLAGS
    (out / 'identity.json').write_text(json.dumps(identity, indent=2))
    lib = str(out / 'libreader_writer_collapse.rlib')
    binary = str(out / 'probe')
    run(out, ['rustc', 'src/lib.rs', '--crate-type=rlib', '--crate-name=reader_writer_collapse', *FLAGS, '-o', lib], 'build-library')
    run(out, ['rustc', 'src/main.rs', '--extern', 'reader_writer_collapse=' + lib, *FLAGS, '-o', binary], 'build-probe')
    run(out, ['rustc', '--edition=2024', '--test', 'src/lib.rs', '-o', str(out / 'tests')], 'build-tests')
    run(out, [str(out / 'tests')], 'tests')
    run(out, ['rustdoc', '--edition=2024', '--test', 'src/lib.rs', '--extern', 'reader_writer_collapse=' + lib], 'doctests')
    run(out, [sys.executable, 'experiment/oracle.py', binary], 'oracle')
    identity['binary_sha256'] = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
    (out / 'identity.json').write_text(json.dumps(identity, indent=2))
    env = dict(os.environ)
    if cpus:
        env['BENCH_CPUS'] = ','.join(map(str, cpus))
    else:
        env.pop('BENCH_CPUS', None)
    with (out / 'rows.csv').open('w', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(FIELDS)

        def sample(phase, rep, mode, threads, operations, rounds):
            name = '{}-{}-{}-{}-{}'.format(phase, rep, mode, threads, rounds)
            output = run(out, [binary, 'bench', mode, str(threads), str(operations), str(rounds)], name, env=env, timeout=60)
            row = output.strip().split(',')
            assert len(row) == 6 and row[:4] == [mode, str(threads), str(operations), str(rounds)]
            writer.writerow([phase, rep] + row)
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


if __name__ == '__main__':
    main()
