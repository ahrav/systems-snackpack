#!/usr/bin/env python3
"""Run a balanced fresh-process comparison on four distinct Linux cores."""
import argparse
import csv
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import tempfile
from datetime import datetime, timezone
from validate import ROOT, FLAGS, build, run, validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error(f'{args.output} is not empty; each campaign needs its own output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    topology = run(['lscpu', '-p=CPU,CORE,SOCKET,NODE'])
    allowed = os.sched_getaffinity(0)
    nodes = {}
    for line in topology.splitlines():
        if line.startswith('#'):
            continue
        cpu, core, socket, node = map(int, line.split(','))
        if cpu in allowed:
            nodes.setdefault(node, {}).setdefault((socket, core), cpu)
    candidates = [sorted(cores.values()) for cores in nodes.values() if len(cores) >= 4]
    assert candidates, 'four distinct allowed cores on one node required'
    cpus = candidates[0][:4]
    os.sched_setaffinity(0, cpus)
    metadata = dict(time_utc=datetime.now(timezone.utc).isoformat(), source_commit=args.source_commit,
                    hostname=platform.node(), platform=platform.platform(), architecture=platform.machine(),
                    cpu_set=cpus, topology=topology, lscpu=run(['lscpu']),
                    compiler=run(['cc', '--version']), flags=FLAGS, n=262144, rounds=32, workers=4,
                    protocol='One untimed warmup per mode/cell; six permutations; fresh process per sample; one invocation per process; thread startup and cleanup included.',
                    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in [ROOT/'work_stealing_bench.c', ROOT/'work_stealing_demo.py',
                                             ROOT/'scripts/validate.py', Path(__file__)]})
    (args.output/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.output/'validation.json').write_text(json.dumps(validate(), indent=2)+'\n')
    modes = ['serial', 'static', 'steal']
    cells = list(itertools.product([1, 16], [1, 64, 1024]))
    random.Random(87).shuffle(cells)
    rows = []
    with tempfile.TemporaryDirectory(prefix='topic087-bench-') as tmp:
        binary = Path(tmp)/'bench'
        build(ROOT/'work_stealing_bench.c', binary)
        metadata['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        with (args.output/'attempts.jsonl').open('w') as attempts:
            for skew, grain in cells:
                expected = None
                orders = [modes] + list(itertools.permutations(modes))
                for block, order in enumerate(orders):
                    for position, mode in enumerate(order):
                        command = [str(binary), '--n', '262144', '--workers', '4', '--rounds', '32',
                                   '--skew', str(skew), '--grain', str(grain), '--reps', '1', '--mode', mode]
                        identity = {'mode': mode, 'n': '262144', 'workers': '4', 'grain': str(grain), 'rounds': '32', 'skew': str(skew)}
                        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
                        attempts.write(json.dumps(dict(command=command, block=block, position=position,
                                                       exit_code=result.returncode, stdout=result.stdout,
                                                       stderr=result.stderr))+'\n')
                        attempts.flush()
                        assert result.returncode == 0, result.stderr
                        data = list(csv.DictReader(io.StringIO(result.stdout)))
                        assert len(data) == 1
                        row = data[0]
                        assert {key: row[key] for key in identity} == identity, row
                        if expected is None:
                            expected = row['checksum']
                        assert row['checksum'] == expected
                        if block:
                            rows.append(dict(block=block, position=position, **row))
    assert len(rows) == 108
    with (args.output/'raw.csv').open('w') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for skew, grain in sorted(cells):
        for mode in modes:
            samples = [int(r['elapsed_ns']) for r in rows if int(r['skew']) == skew and int(r['grain']) == grain and r['mode'] == mode]
            summary.append(dict(skew=skew, grain=grain, mode=mode, count=len(samples),
                                median_ns=statistics.median(samples), min_ns=min(samples), max_ns=max(samples)))
    metadata['measured_processes'] = len(rows)
    metadata['warmup_processes'] = 18
    (args.output/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(host=platform.node(), measured_processes=len(rows), cpu_set=cpus)))


if __name__ == '__main__':
    main()
