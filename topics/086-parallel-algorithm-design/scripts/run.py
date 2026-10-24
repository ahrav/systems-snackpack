#!/usr/bin/env python3
"""Fixed descriptive comparison; no adaptive sampling or outlier removal."""
import csv
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

binary, directory = sys.argv[1:]
out = Path(directory)
out.mkdir(parents=True, exist_ok=False)
metadata = {'host': platform.node(), 'platform': platform.platform(), 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'pid': os.getpid()}
if hasattr(os, 'sched_getaffinity'):
    allowed = sorted(os.sched_getaffinity(0))
    # The declared campaign uses CPUs 0..7, verified as distinct visible cores.
    if not set(range(8)).issubset(allowed):
        raise RuntimeError(f'CPUs 0..7 must all be allowed; inherited {allowed}')
    metadata['inherited_affinity'] = allowed
    os.sched_setaffinity(0, range(8))
    metadata['affinity'] = sorted(os.sched_getaffinity(0))
    if metadata['affinity'] != list(range(8)):
        raise RuntimeError(f'pinning left affinity {metadata["affinity"]}')
else:
    metadata['affinity'] = 'uncontrolled local diagnostic'
(out / 'runner.json').write_text(json.dumps(metadata, indent=2) + '\n')
header = ['kind', 'block', 'position', 'variant', 'n', 'workers', 'repeats', 'ns_call', 'total']
with (out / 'raw.csv').open('w') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    def trial(kind, block, pos, v, n, p, reps):
        command = [binary, 'bench', v, str(n), str(p), str(reps)]
        attempt = {'kind': kind, 'block': block, 'position': pos, 'command': command}
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            attempt.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            with (out / 'attempts.jsonl').open('a') as log: log.write(json.dumps(attempt) + '\n')
            result.check_returncode()
            fields = result.stdout.strip().split(',')
            if len(fields) != 6 or fields[:4] != [v, str(n), str(p), str(reps)]:
                raise RuntimeError(f'probe output {result.stdout!r} does not describe {command}')
            writer.writerow([kind, block, pos] + fields)
            f.flush()
        except BaseException as error:
            (out / 'failure.json').write_text(json.dumps({'attempt': attempt, 'error': repr(error)}, indent=2))
            raise
    # Identical binary/path through both labels; mechanical check, not noise calibration.
    for pos in range(2): trial('aa', 0, pos, 'serial', 262144, 1, 8)
    for block, order in enumerate(itertools.permutations(['serial', 'local', 'rescan'])):
        cells = [(n, p, reps) for n, reps in [(4096, 16), (262144, 8), (4194304, 4)] for p in [1, 4, 8]]
        if block % 2: cells.reverse()
        for n, p, reps in cells:
            for pos, variant in enumerate(order): trial('measure', block, pos, variant, n, p, reps)
print(json.dumps({'status': 'complete', 'measured_processes': 162, 'aa_processes': 2}))
