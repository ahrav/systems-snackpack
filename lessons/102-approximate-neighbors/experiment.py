"""Independent SQLite checks and fresh-process balanced timing experiment."""
import hashlib
import itertools
import json
import os
import platform
import random
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from ann import Index

MODES = {'exact': None, 'ivf1': 1, 'ivf4': 4, 'ivf16': 16}


def oracle(points, query, k):
    """SQLite computes and orders its own integer expression over all rows."""
    db = sqlite3.connect(':memory:')
    columns = ','.join('x%d INTEGER' % i for i in range(len(query)))
    db.execute('CREATE TABLE vectors(id INTEGER,' + columns + ')')
    db.executemany('INSERT INTO vectors VALUES (' + ','.join('?' for _ in range(len(query)+1)) + ')',
                   [(i,) + tuple(p) for i, p in enumerate(points)])
    terms = '+'.join('(x%d-(%d))*(x%d-(%d))' % (j, q, j, q) for j, q in enumerate(query))
    result = db.execute('SELECT ' + terms + ' AS d,id FROM vectors ORDER BY d,id LIMIT ?', (k,)).fetchall()
    db.close()
    return result


def check():
    rng = random.Random(102)
    comparisons = 0
    digest = hashlib.sha256()
    for dim in (1, 2, 4):
        for n in (0, 1, 7, 31):
            for _ in range(20):
                points = [tuple(rng.randrange(-10, 11) for _ in range(dim)) for _ in range(n)]
                centers = [tuple(rng.randrange(-10, 11) for _ in range(dim)) for _ in range(4)]
                index = Index(points, centers)
                # Independent assignment expression, separate from ann.distance.
                for owner, ids in enumerate(index.lists):
                    for i in ids:
                        scores = [sum((points[i][j]-c[j])*(points[i][j]-c[j]) for j in range(dim)) for c in centers]
                        assert owner == scores.index(min(scores))
                assert sorted(i for ids in index.lists for i in ids) == list(range(n))
                query = tuple(rng.randrange(-12, 13) for _ in range(dim))
                for k in (0, 1, 5, n+2):
                    truth = oracle(points, query, k)
                    for mode in (None, 4):
                        actual, _ = index.search(query, k, mode)
                        assert actual == truth, (points, query, k, mode, actual, truth)
                        comparisons += 1
                        digest.update(repr(actual).encode())
                    previous = set()
                    for probes in range(1, 5):
                        actual, count = index.search(query, k, probes)
                        chosen = sorted(range(4), key=lambda c: (sum((query[j]-centers[c][j])**2 for j in range(dim)), c))[:probes]
                        ids = [i for c in chosen for i in index.lists[c]] if k else []
                        # Oracle ranks only the selected IDs and restores global IDs.
                        local = oracle([points[i] for i in sorted(ids)], query, k)
                        expected = [(d, sorted(ids)[i]) for d, i in local]
                        assert actual == expected and count == len(ids)
                        overlap = {i for _, i in actual} & {i for _, i in truth}
                        assert previous <= overlap
                        previous = overlap
                        comparisons += 1
    index = Index([(0,), (51,)], [(0,), (100,)])
    assert index.search((49,), 1, 1)[0] == [(2401, 0)]
    assert index.search((49,), 1, 2)[0] == [(4, 1)]
    assert Index([(0,), (0,)], [(0,), (0,)]).search((0,), 2, 2)[0] == [(0, 0), (0, 1)]
    bad_calls = [lambda: Index([], []), lambda: Index([(1, 2)], [(0,)]),
                 lambda: Index([(1.0,)], [(0,)]), lambda: index.search((), 1),
                 lambda: index.search((0,), -1), lambda: index.search((0,), 1, 0),
                 lambda: index.search((0,), 1, 3)]
    for call in bad_calls:
        try:
            call()
        except ValueError:
            pass
        else:
            raise AssertionError('invalid input accepted')
    return {'comparisons': comparisons, 'digest': digest.hexdigest(), 'invalid_inputs_rejected': len(bad_calls), 'boundary_miss_detected': True}


def workload(name):
    rng = random.Random(102)
    centers = list(itertools.product((0, 100), repeat=4))
    n = 64 if name == 'tiny' else 2048
    spread = 8 if name in ('separated', 'tiny') else 70
    def point():
        center = rng.choice(centers)
        return tuple(c + rng.randint(-spread, spread) for c in center)
    return [point() for _ in range(n)], centers, [point() for _ in range(32)]


def worker(name, mode):
    if hasattr(os, 'sched_setaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    points, centers, queries = workload(name)
    start = time.perf_counter_ns()
    index = Index(points, centers)
    build = time.perf_counter_ns() - start
    probe = MODES[mode]
    # One complete query batch warms the interpreter and working set.
    for q in queries:
        index.search(q, 5, probe)
    start = time.perf_counter_ns()
    answers = [index.search(q, 5, probe) for q in queries]
    elapsed = time.perf_counter_ns() - start
    # Ground truth and validation are outside the timed interval.
    hits = 0
    for q, (actual, _) in zip(queries, answers):
        truth = oracle(points, q, 5)
        hits += len({i for _, i in actual} & {i for _, i in truth})
        assert len({i for _, i in actual}) == len(actual)
        assert all(0 <= i < len(points) for _, i in actual)
        if mode in ('exact', 'ivf16'):
            assert actual == truth
    return {'workload': name, 'mode': mode, 'ns_per_query': elapsed/len(queries),
            'recall': hits/(len(queries)*5), 'mean_candidates': sum(c for _, c in answers)/len(queries),
            'build_ns': build, 'list_sizes': list(map(len, index.lists)),
            'affinity': sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None}


def bench():
    rows = []
    modes = list(MODES)
    # Each block pairs a rotated order with its reverse; six samples per mode.
    for name in ('tiny', 'separated', 'overlap'):
        for block in range(3):
            order = modes[block:] + modes[:block]
            for sequence in (order, list(reversed(order))):
                for mode in sequence:
                    row = json.loads(subprocess.check_output([sys.executable, str(Path(__file__).resolve()), 'worker', name, mode]))
                    row['block'] = block
                    rows.append(row)
    cpu = Path('/proc/cpuinfo').read_text() if Path('/proc/cpuinfo').exists() else platform.processor()
    return {'platform': platform.platform(), 'machine': platform.machine(), 'python': sys.version,
            'cpu': cpu, 'samples': rows, 'correctness': check(),
            'source_hashes': {p: hashlib.sha256(Path(__file__).with_name(p).read_bytes()).hexdigest() for p in ('ann.py', 'experiment.py')}}


if __name__ == '__main__':
    command = sys.argv[1]
    result = check() if command == 'check' else worker(*sys.argv[2:]) if command == 'worker' else bench() if command == 'bench' else None
    if result is None:
        raise SystemExit('commands: check, bench, worker <workload> <mode>')
    print(json.dumps(result, indent=2))
