"""Fresh-process campaign. Python 3.9 compatible; retain each individual run."""
import argparse
import itertools
import json
import pathlib
import statistics
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--milliseconds', type=int, default=300)
    p.add_argument('--cpus', default='')
    args = p.parse_args()
    modes = ['seq', 'fallback', 'rw']
    workloads = ['none', 'paced', 'held', 'hot']
    prefix = ['taskset', '-c', args.cpus] if args.cpus else []
    partial = pathlib.Path(args.out + '.partial')
    rows = []
    counts = ['reads', 'odd', 'changed', 'fallback', 'min_reader_reads', 'writes', 'skipped_slots']
    def run(mode, workload, block, warmup):
        command = prefix + [str(pathlib.Path(args.binary).resolve()), mode, workload, '4', str(args.milliseconds)]
        row = json.loads(subprocess.check_output(command, text=True, timeout=20))
        expected = {'mode': mode, 'workload': workload, 'readers': 4}
        if ({key: row.get(key) for key in expected} != expected
                or any(type(row.get(key)) is not int or row[key] < 0 for key in counts)
                or type(row.get('seconds')) not in (int, float) or row['seconds'] <= 0
                or row['reads'] <= 0 or row['min_reader_reads'] <= 0
                or (row['writes'] > 0) != (workload != 'none')):
            raise SystemExit('row does not match its command: %s -> %s' % (command, row))
        row.update(block=block, warmup=warmup, command=command)
        rows.append(row)
        partial.write_text(json.dumps(rows, indent=2) + '\n')
    for workload in workloads:
        for mode in modes: run(mode, workload, -1, True)
        for block, order in enumerate(itertools.permutations(modes)):
            for mode in order: run(mode, workload, block, False)
    for workload in workloads:
        for mode in modes:
            group = [r for r in rows if not r['warmup'] and r['mode'] == mode and r['workload'] == workload]
            rates = [r['reads'] / r['seconds'] / 1e6 for r in group]
            retries = [(r['odd'] + r['changed']) / r['reads'] for r in group]
            writes = [r['writes'] / r['seconds'] for r in group]
            fallback = [r['fallback'] / r['reads'] * 100 for r in group]
            print('%-5s %-8s reads M/s median %.3f [%.3f, %.3f]; failures/read %.3f; fallback %.3f%%; writes/s %.0f' % (workload, mode, statistics.median(rates), min(rates), max(rates), statistics.median(retries), statistics.median(fallback), statistics.median(writes)))
    partial.replace(args.out)


if __name__ == '__main__': main()
