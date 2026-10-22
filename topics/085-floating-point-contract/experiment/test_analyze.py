#!/usr/bin/env python3
"""analyze.py accepts the frozen 12-block matrix per host and rejects malformed inputs."""
import csv
import itertools
import json
import pathlib
import subprocess
import sys
import tempfile

analyze = pathlib.Path(__file__).with_name('analyze.py')
SIZES = (256, 65536, 1048576)
MODES = ('ordered', 'lanes4', 'compensated')


def rows():
    out = []
    orders = list(itertools.permutations(MODES)) * 2
    for n in SIZES:
        for workload in ('positive', 'signed'):
            for rep, order in enumerate(orders):
                for position, method in enumerate(order):
                    out.append({'method': method, 'workload': workload, 'n': n, 'repeats': (1 << 24) // n,
                                'elapsed_ns': 1000 * (1 + MODES.index(method)) + rep,
                                'result_bits': f'{n:016x}', 'rep': rep, 'position': position})
    return out


def write_host(directory, data):
    directory.mkdir(parents=True)
    with (directory / 'samples.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def run(dirs, *flags):
    return subprocess.run([sys.executable, *flags, str(analyze), *map(str, dirs)],
                          text=True, capture_output=True, timeout=120, check=False)


def analyze_exit(data, *flags):
    with tempfile.TemporaryDirectory() as tmp:
        host = pathlib.Path(tmp) / 'host'
        write_host(host, data)
        return run([host], *flags).returncode


def test_complete_matrix_is_accepted():
    assert analyze_exit(rows()) == 0


def test_duplicate_leaf_names_are_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        a, b = pathlib.Path(tmp) / 'arm/results', pathlib.Path(tmp) / 'xxl/results'
        write_host(a, rows())
        write_host(b, rows())
        p = run([a, b])
        assert p.returncode != 0, 'analyzer silently overwrote one host with another'


def test_distinct_leaf_names_are_both_reported():
    with tempfile.TemporaryDirectory() as tmp:
        a, b = pathlib.Path(tmp) / 'arm', pathlib.Path(tmp) / 'xxl'
        write_host(a, rows())
        write_host(b, rows())
        p = run([a, b])
        assert p.returncode == 0, p.stderr
        assert set(json.loads(p.stdout)) == {'arm', 'xxl'}


def test_substituted_block_is_rejected():
    data = rows()
    victim = next(r for r in data if r['n'] == 256 and r['workload'] == 'positive'
                  and r['method'] == 'ordered' and r['rep'] == 11)
    victim['rep'] = 0  # rep 0 twice, rep 11 absent: still twelve rows
    assert analyze_exit(data) != 0, 'analyzer accepted a duplicated block in place of a missing one'


def test_result_bits_disagreement_is_rejected():
    data = rows()
    victim = next(r for r in data if r['n'] == 65536 and r['method'] == 'lanes4')
    victim['result_bits'] = 'deadbeefdeadbeef'
    assert analyze_exit(data) != 0, 'analyzer compared timings of methods that disagree on the result'


def test_nonpositive_timing_is_rejected():
    data = rows()
    data[0]['elapsed_ns'] = -5
    assert analyze_exit(data) != 0


def test_work_mismatch_is_rejected():
    data = rows()
    data[0]['repeats'] = data[0]['repeats'] // 2
    assert analyze_exit(data) != 0


def test_order_coverage_is_enforced():
    data = rows()
    block = [r for r in data if r['n'] == 256 and r['workload'] == 'signed' and r['rep'] == 0]
    for r in block:  # same three methods, same rep, but one permutation now appears three times
        r['position'] = ('lanes4', 'ordered', 'compensated').index(r['method'])
    assert analyze_exit(data) != 0


def test_truncated_input_is_rejected_without_asserts():
    data = rows()[:-1]
    assert analyze_exit(data, '-O') != 0, 'analyzer ran with assert statements stripped'


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(name, 'ok')
