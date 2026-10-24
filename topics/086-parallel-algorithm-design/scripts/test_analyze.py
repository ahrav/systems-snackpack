#!/usr/bin/env python3
"""analyze.py accepts the retained 162+2 row matrix and rejects malformed inputs, with or without -O."""
import csv
import itertools
import pathlib
import subprocess
import sys
import tempfile

analyze = pathlib.Path(__file__).with_name('analyze.py')
MASK = (1 << 64) - 1
CELLS = [(4096, 16), (262144, 8), (4194304, 4)]


def rows():
    out = [{'kind': 'aa', 'block': 0, 'position': pos, 'variant': 'serial', 'n': 262144, 'workers': 1,
            'repeats': 8, 'ns_call': 100000 + pos, 'total': (262144 * 262145 // 2) & MASK} for pos in range(2)]
    for block, order in enumerate(itertools.permutations(['serial', 'local', 'rescan'])):
        cells = [(n, p, reps) for n, reps in CELLS for p in [1, 4, 8]]
        if block % 2:
            cells.reverse()
        for n, p, reps in cells:
            for pos, variant in enumerate(order):
                out.append({'kind': 'measure', 'block': block, 'position': pos, 'variant': variant, 'n': n,
                            'workers': p, 'repeats': reps, 'ns_call': n * (1 + order.index(variant)) + block,
                            'total': (n * (n + 1) // 2) & MASK})
    return out


def analyze_exit(data, *flags, _stdout=False):
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / 'raw.csv'
        with path.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        p = subprocess.run([sys.executable, *flags, str(analyze), str(path)],
                           text=True, capture_output=True, timeout=120, check=False)
        return (p.returncode, p.stdout) if _stdout else p.returncode


def test_complete_matrix_is_accepted():
    assert analyze_exit(rows()) == 0
    assert analyze_exit(rows(), '-O') == 0


def test_substituted_block_is_rejected_without_asserts():
    data = rows()
    victim = next(r for r in data if r['kind'] == 'measure' and r['n'] == 4096
                  and r['workers'] == 8 and r['variant'] == 'local' and r['block'] == 5)
    victim['n'] = 8192  # still 162 measured rows, one cell now has five local timings
    assert analyze_exit(data, '-O') != 0, 'analyzer paired five ratios and reported a decision'
    assert analyze_exit(data) != 0


def test_row_count_is_enforced():
    assert analyze_exit(rows()[:-1], '-O') != 0
    assert analyze_exit(rows() + [dict(rows()[-1], block=6)], '-O') != 0


def test_nonpositive_timing_is_rejected():
    data = rows()
    data[5]['ns_call'] = 0
    assert analyze_exit(data, '-O') != 0


def test_wrong_total_is_rejected():
    data = rows()
    data[7]['total'] = data[7]['total'] ^ 1
    assert analyze_exit(data, '-O') != 0


def test_infinite_timing_is_rejected():
    data = rows()
    data[9]['ns_call'] = 'inf'
    assert analyze_exit(data, '-O') != 0


def test_aa_rows_must_describe_one_serial_cell():
    data = rows()
    data[1]['variant'] = 'local'
    assert analyze_exit(data, '-O') != 0
    data = rows()
    data[1]['workers'] = 8
    assert analyze_exit(data, '-O') != 0


def test_repeat_schedule_is_enforced():
    data = rows()
    for r in data:
        if r['kind'] == 'measure':
            r['repeats'] = 1
    assert analyze_exit(data, '-O') != 0


def test_block_order_is_enforced():
    data = rows()
    block = [r for r in data if r['kind'] == 'measure' and r['n'] == 4096 and r['workers'] == 1 and r['block'] == 0]
    for r in block:  # block 0 must run serial, local, rescan; swap the last two
        r['position'] = {'serial': 0, 'local': 2, 'rescan': 1}[r['variant']]
    assert analyze_exit(data, '-O') != 0


def test_aa_ratio_follows_declared_positions():
    data = rows()
    data[0], data[1] = data[1], data[0]  # same two rows, reversed physical order
    expected = analyze_exit(rows(), '-O', _stdout=True)
    assert analyze_exit(data, '-O', _stdout=True) == expected, 'A/A ratio depends on CSV row order'
    data = rows()
    data[1]['position'] = 0
    assert analyze_exit(data, '-O') != 0
    data = rows()
    data[1]['block'] = 1
    assert analyze_exit(data, '-O') != 0


def test_missing_aa_row_is_rejected():
    data = rows()[1:]
    assert analyze_exit(data, '-O') != 0


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print(name, 'ok')
