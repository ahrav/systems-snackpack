"""Run six fresh-process pairs per footprint; retain every measured observation."""
import json
import os
from pathlib import Path
import subprocess
import sys

exe = str(Path(sys.argv[1]).resolve())
cpu = min(os.sched_getaffinity(0))
for mib in (2, 64):
    for mode in ('base', 'huge'):
        subprocess.run(['taskset', '-c', str(cpu), exe, mode, str(mib)],
                       check=True, stdout=subprocess.DEVNULL)
    for pair in range(6):
        for position, mode in enumerate(('base', 'huge') if pair % 2 == 0 else ('huge', 'base')):
            row = json.loads(subprocess.check_output(
                ['taskset', '-c', str(cpu), exe, mode, str(mib)], text=True))
            row.update(pair=pair, position=position, cpu=cpu)
            print(json.dumps(row), flush=True)
