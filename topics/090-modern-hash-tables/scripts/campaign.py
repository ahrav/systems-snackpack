#!/usr/bin/env python3
"""Six permutation-balanced blocks; every sample is a fresh process."""
import argparse, csv, itertools, json, os, platform, subprocess
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--binary', required=True)
p.add_argument('--out', required=True)
a=p.parse_args()
out=Path(a.out); out.mkdir(parents=True, exist_ok=True)
if hasattr(os, 'sched_setaffinity'):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
workloads=['small_hit50','small_miss87','large_hit50','large_miss87','large_deleted_miss','large_rebuilt_miss']
variants=['plain','tagged','std']
orders=list(itertools.permutations(variants))
metadata={'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,'rustc':subprocess.check_output(['rustc','--version','--verbose'],text=True),'controls':'one worker; eight warm-query passes; setup/oracle excluded; six balanced fresh-process blocks; no clock/thermal/load control'}
metadata['cpu'] = subprocess.check_output(['lscpu'] if platform.system() == 'Linux' else ['sysctl', '-n', 'machdep.cpu.brand_string'], text=True)
(out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
with (out/'samples.csv').open('w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['variant','workload','seed','live','capacity','tombstones','operations','ns','checksum','probes_one_pass','equalities_one_pass'])
    for workload in workloads:
        for v in variants:
            subprocess.run([a.binary,v,workload,'100'],check=True,stdout=subprocess.DEVNULL)
        for block,order in enumerate(orders):
            for v in order:
                row=subprocess.check_output([a.binary,v,workload,str(1000+block)],text=True).strip().split(',')
                assert len(row)==11
                w.writerow(row); f.flush()
        print(workload+' complete',flush=True)
