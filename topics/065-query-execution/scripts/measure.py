#!/usr/bin/env python3
"""Balanced paired processes; inner scans are not independent observations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

phase = sys.argv[1]
cpu = min(os.sched_getaffinity(0))
binary = Path('target/release/examples/probe').resolve()
records = []
treatments = [('row', 1024), ('batch', 64), ('batch', 1024), ('batch', 16384), ('fused', 1024)]
for mask in [63, 1]:
    for mode, batch in treatments:
        for pair in range(6 if phase == 'final' else 2):
            arms = [('baseline', 'fused', 1024), ('treatment', mode, batch)]
            if pair % 2:
                arms.reverse()
            for position, (arm, selected_mode, selected_batch) in enumerate(arms):
                argv = ['taskset', '-c', str(cpu), str(binary), selected_mode,
                        '1048576', str(mask), str(selected_batch), '32']
                start = time.monotonic_ns()
                output = subprocess.check_output(argv, text=True).strip()
                elapsed = time.monotonic_ns() - start
                fields = dict(item.split('=') for item in output.split(','))
                records.append(dict(mask=mask, treatment=mode, batch=batch, pair=pair,
                                    position=position, arm=arm, cpu=cpu, argv=argv,
                                    process_ns=elapsed, result=fields))
                Path('evidence/processes.json').write_text(json.dumps(records, indent=2)+'\n')
print(f'{phase}: {len(records)} processes, CPU {cpu}; two masks, four treatments and A/A control')
