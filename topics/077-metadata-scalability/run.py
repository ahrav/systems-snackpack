#!/usr/bin/env python3
"""Six balanced process pairs per workload; setup is outside the timed region."""
import argparse, csv, hashlib, json, pathlib, platform, statistics, subprocess

p = argparse.ArgumentParser()
p.add_argument('--binary', required=True)
p.add_argument('--out', required=True)
p.add_argument('--source-commit', required=True)
a = p.parse_args()
out = pathlib.Path(a.out)
out.mkdir(parents=True, exist_ok=False)
binary = pathlib.Path(a.binary).resolve()
fields = ['variant', 'workload', 'iterations', 'updates', 'elapsed_ns', 'ns_per_batch', 'snapshot_bytes', 'delta_bytes']

def run(variant, workload, iterations):
    raw = subprocess.check_output([str(binary), variant, workload, str(iterations)], text=True).strip()
    values = raw.split(',')
    if len(values) != len(fields):
        raise ValueError('unexpected benchmark output')
    row: dict = dict(zip(fields, values))
    if (row['variant'], row['workload'], row['iterations']) != (variant, workload, str(iterations)):
        raise ValueError(f'row echoes {values[:3]} for invocation {[variant, workload, str(iterations)]}')
    row['ns_per_batch'] = float(row['ns_per_batch'])
    for key in ['iterations', 'updates', 'elapsed_ns', 'snapshot_bytes', 'delta_bytes']:
        row[key] = int(row[key])
    return row

identity = {'source_commit': a.source_commit, 'platform': platform.platform(),
            'machine': platform.machine(), 'python': platform.python_version(),
            'rustc': subprocess.check_output(['rustc', '-Vv'], text=True),
            'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'scope': 'Warm in-process validated cache application. No transport, encoding, authority writes, allocation, fanout or concurrent readers. Default cargo release. No CPU pinning or frequency control.',
            'decision': 'Winner only if every one of six paired ratios exceeds 1.05; otherwise unresolved.'}
if platform.system() == 'Darwin':
    identity['cpu'] = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
else:
    identity['cpuinfo'] = pathlib.Path('/proc/cpuinfo').read_text()
(out/'identity.json').write_text(json.dumps(identity, indent=2)+'\n')
rows, calibrations, summary = [], [], []
for workload in ['sparse', 'dense', 'hot']:
    iterations = {}
    for variant in ['snapshot', 'delta']:
        row = run(variant, workload, 512)
        calibrations.append(row)
        iterations[variant] = max(128, min(1_000_000, int(80_000_000 / row['ns_per_batch'])))
    ratios = []
    for pair in range(6):
        pair_rows = {}
        order = ['snapshot', 'delta'] if pair % 2 == 0 else ['delta', 'snapshot']
        for position, variant in enumerate(order):
            row = run(variant, workload, iterations[variant])
            row.update(pair=pair, position=position)
            rows.append(row)
            pair_rows[variant] = row['ns_per_batch']
        ratios.append(pair_rows['snapshot']/pair_rows['delta'])
    winner = 'delta' if min(ratios) > 1.05 else 'snapshot' if max(ratios) < 1/1.05 else 'unresolved'
    cell = {'workload':workload, 'winner':winner, 'snapshot_over_delta_ratios':ratios}
    for variant in ['snapshot','delta']:
        values = [r['ns_per_batch']/1000 for r in rows if r['workload']==workload and r['variant']==variant]
        cell[variant] = {'median_us':statistics.median(values), 'min_us':min(values), 'max_us':max(values)}
    summary.append(cell)
    print(json.dumps(cell), flush=True)
with (out/'samples.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields+['pair','position'], lineterminator='\n')
    w.writeheader()
    w.writerows(rows)
(out/'calibrations.json').write_text(json.dumps(calibrations,indent=2)+'\n')
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
