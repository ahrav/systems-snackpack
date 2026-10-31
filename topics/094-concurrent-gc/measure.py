"""Eight fresh-process blocks; all six policy orders plus a reversed pair."""
import itertools
import json
import platform
import subprocess
import sys

binary, dest = sys.argv[1:]
prefix = ['taskset', '-c', '0'] if platform.system() == 'Linux' else []
modes = ('stw', 'insertion', 'satb')
orders = list(itertools.permutations(modes)) + [modes, modes[::-1]]
rows = []
for workload in ('keep', 'delete', 'replace'):
    for mode in modes:
        subprocess.run(prefix+[binary, 'bench', mode, workload], check=True, capture_output=True)
    for block, order in enumerate(orders):
        for mode in order:
            values = list(map(int, subprocess.check_output(prefix+[binary, 'bench', mode, workload], text=True).split()))
            ns, scans, barriers, retained = values
            n = 16384 * 64
            assert barriers == (0 if mode == 'stw' else n)
            assert retained == scans
            assert retained == (n if workload == 'keep' or mode == 'satb' else 64)
            rows.append(dict(workload=workload, block=block, mode=mode, ns=ns, scans=scans, barriers=barriers, retained=retained))
with open(dest, 'w') as f:
    json.dump(dict(host=platform.platform(), machine=platform.machine(), rows=rows), f, indent=2)
print(f'{len(rows)} measured processes, 9 excluded warmups; workload counts passed')
