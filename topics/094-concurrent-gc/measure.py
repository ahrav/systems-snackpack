"""Eight fresh-process blocks; all six policy orders plus a reversed pair."""
import itertools
import json
import os
import platform
import subprocess
import sys

binary, dest = sys.argv[1:]
# Pin to the lowest CPU already in the allowed set, which also holds inside cpuset-restricted cgroups.
cpu = None
if hasattr(os, 'sched_getaffinity'):
    cpu = min(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
modes = ('stw', 'insertion', 'satb')
orders = list(itertools.permutations(modes)) + [modes, modes[::-1]]
rows = []
# Opening dest in write mode validates the path and truncates previous results before benchmarks start.
try:
    f = open(dest, 'w')  # noqa: SIM115
except OSError as e:
    raise SystemExit(f'cannot write {dest}: {e}') from None
with f:
    for workload in ('keep', 'delete', 'replace'):
        for mode in modes:
            subprocess.run([binary, 'bench', mode, workload], check=True, capture_output=True)
        for block, order in enumerate(orders):
            for mode in order:
                values = list(map(int, subprocess.check_output([binary, 'bench', mode, workload], text=True).split()))
                ns, scans, barriers, retained = values
                n = 16384 * 64
                # Checks raise so they hold under python -O.
                if barriers != (0 if mode == 'stw' else n):
                    raise SystemExit(f'{workload} {mode}: barriers={barriers}')
                if retained != scans:
                    raise SystemExit(f'{workload} {mode}: retained={retained} scans={scans}')
                if retained != (n if workload == 'keep' or mode == 'satb' else 64):
                    raise SystemExit(f'{workload} {mode}: retained={retained}')
                rows.append(dict(workload=workload, block=block, mode=mode, ns=ns, scans=scans, barriers=barriers, retained=retained))
    json.dump({'host': platform.platform(), 'machine': platform.machine(), 'cpu': cpu, 'rows': rows}, f, indent=2)
print(f'{len(rows)} measured processes, 9 excluded warmups; workload counts passed')
