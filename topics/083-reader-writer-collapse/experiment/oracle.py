#!/usr/bin/env python3
"""Independent time-step scheduler and arbitrary-precision arithmetic oracle."""
import itertools
import subprocess
import sys


def schedule(prefer, length, writer_at, reader_at, write_time, read_time):
    writer_start = reader_start = None
    writer_end = reader_end = None
    for tick in range(length + write_time + read_time + reader_at + 1):
        active_a = tick < length
        active_b = reader_end is not None and tick < reader_end
        active_w = writer_end is not None and tick < writer_end
        writer_waiting = writer_at <= tick and writer_start is None
        if writer_waiting and not active_a and not active_b:
            writer_start, writer_end = tick, tick + write_time
            active_w = True
        if reader_at <= tick and reader_start is None and not active_w:
            if not prefer or not writer_waiting:
                reader_start, reader_end = tick, tick + read_time
        if writer_start is not None and reader_start is not None:
            return writer_start, reader_start
    raise AssertionError('schedule did not complete')


def reference(generation, request, rounds):
    mask = (1 << 64) - 1
    value = generation ^ ((generation * 100) & mask) ^ request
    for _ in range(rounds):
        value = value * 6364136223846793005 & mask
        value = (((value << 13) | (value >> 51)) + 1) & mask
    return value


def check(binary):
    cases = [(p, length, w, r, wd, rd)
             for p in (0, 1) for length in range(3, 13)
             for w in range(length - 1) for r in range(w + 1, length)
             for wd, rd in itertools.product((1, 3), (1, 4, 15))]
    text = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
    result = subprocess.run([binary, 'model'], input=text, text=True, capture_output=True, check=True)
    rows = result.stdout.splitlines()
    assert len(rows) == len(cases)
    for case, row in zip(cases, rows):
        assert tuple(map(int, row.split(','))) == schedule(*case), (case, row)
    arithmetic = list(itertools.product((0, 7, (1 << 64) - 1), (0, 1, 700, (1 << 64) - 1), (0, 1, 2, 256)))
    result = subprocess.run([binary, 'compute'], input=''.join(' '.join(map(str, x)) + '\n' for x in arithmetic), text=True, capture_output=True, check=True)
    rows = result.stdout.splitlines()
    assert len(rows) == len(arithmetic)
    for case, row in zip(arithmetic, rows):
        assert int(row) == reference(*case), (case, row)
    print('PASS: {} schedule cases, {} arithmetic cases'.format(len(cases), len(arithmetic)))


if __name__ == '__main__':
    check(sys.argv[1])
