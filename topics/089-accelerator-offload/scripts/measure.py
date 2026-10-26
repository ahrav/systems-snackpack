"""Ten fresh-process pairs per cell; balanced AB/BA order, warm buffers."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from oracle import expected_values

binary = str(Path(sys.argv[1]).resolve())
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
prefix = []
cpu = None
if hasattr(os, 'sched_getaffinity'):
    cpu = min(os.sched_getaffinity(0))
    prefix = ['taskset', '-c', str(cpu)]
identity = {
    'system': platform.platform(), 'machine': platform.machine(), 'host':platform.node(),
    'python':platform.python_version(), 'rustc':subprocess.check_output(['rustc','-Vv'],text=True),
    'binary_sha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
    'pinned_cpu':cpu, 'source_commit':os.environ.get('SOURCE_COMMIT','unset'),
    'trials':10, 'warmups_per_process':1,
    'timed_scope':'transform only; input/output preallocated, reused; checksum after timing',
    'flags':'cargo build --release; default release profile; no target-cpu override',
    'controls':'single thread, alternating AB/BA; frequency, thermals, SMT siblings and host load uncontrolled',
}
if platform.system() == 'Linux':
    identity['lscpu'] = subprocess.check_output(['lscpu'],text=True)
else:
    identity['cpu'] = subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
(out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
rows = []
summaries = []
for n in (256,65536,1048576):
    for rounds in (1,32):
        expected = sum(expected_values(n, rounds))
        reps = max(1, min(10000, 2000000 // (n*rounds)))
        cell = {'element':[], 'round':[]}
        for trial in range(10):
            order = ('element','round') if trial % 2 == 0 else ('round','element')
            for position, mode in enumerate(order):
                line = subprocess.check_output(prefix+[binary,'bench',mode,str(n),str(rounds),str(reps)],text=True).strip()
                got_mode, got_n, got_rounds, got_reps, ns, checksum = next(csv.reader(io.StringIO(line)))
                assert (got_mode,int(got_n),int(got_rounds),int(got_reps),int(checksum)) == (mode,n,rounds,reps,expected)
                ns_per_call = int(ns)/reps
                rows.append([trial,position,mode,n,rounds,reps,int(ns),ns_per_call,int(checksum)])
                cell[mode].append(ns_per_call)
        ratios = [a/b for a,b in zip(cell['element'],cell['round'])]
        if all(r > 1.05 for r in ratios):
            verdict = 'round wins in all 10 pairs by >5%'
        elif all(r < 1/1.05 for r in ratios):
            verdict = 'element wins in all 10 pairs by >5%'
        elif all(1/1.05 <= r <= 1.05 for r in ratios):
            verdict = 'practical tie within 5% in all 10 pairs'
        else:
            verdict = 'unresolved under declared paired rule'
        summaries.append({'n':n, 'rounds':rounds, 'verdict':verdict,
            'element_over_round_ratios':ratios,
            **{m:{'median_us':statistics.median(v)/1000,'min_us':min(v)/1000,'max_us':max(v)/1000} for m,v in cell.items()}})
        with (out/'rows.csv').open('w') as f:
            writer=csv.writer(f); writer.writerow(['trial','position','variant','n','rounds','reps','total_ns','ns_per_call','checksum']); writer.writerows(rows)
        (out/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
        print(json.dumps(summaries[-1]), flush=True)
