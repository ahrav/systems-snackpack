"""Independent SC schedule oracle; no claim about weaker memory orderings."""
import itertools


def check(order, parity=True, validate=True):
    seq, x, y = 0, 0, 0
    committed = (0, 0)
    allowed = set()
    reading = False
    r = []
    wi = ri = 0
    for actor in order:
        if actor == 'W':
            generation, step = divmod(wi, 4)
            value = generation + 1
            if step == 0: seq += 1
            elif step == 1: x = value
            elif step == 2: y = value + value
            else:
                seq += 1
                committed = (value, value + value)
            wi += 1
        else:
            if ri == 0:
                reading = True
                allowed.add(committed)
            r.append([seq, x, y, seq][ri])
            ri += 1
        if reading: allowed.add(committed)
        if ri == 4:
            accepted = (not parity or r[0] % 2 == 0) and (not validate or r[0] == r[3])
            return not accepted or tuple(r[1:3]) in allowed
    raise AssertionError('incomplete reader')


def schedules(writes):
    n = writes * 4 + 4
    for reader_positions in itertools.combinations(range(n), 4):
        reader_positions = set(reader_positions)
        yield ''.join('R' if i in reader_positions else 'W' for i in range(n))


def main():
    rows = [row for n in range(1, 5) for row in schedules(n)]
    assert all(check(row) for row in rows)
    for name, kwargs in [('missing parity', {'parity': False}), ('missing validation', {'validate': False})]:
        witness = next(row for row in rows if not check(row, **kwargs))
        print(name + ' counterexample: ' + witness)
    # A 2-bit counter repeats after two writes. A reader can copy x before,
    # y after, and see the same even generation across both updates.
    seq_before, read_x = 0, 0
    seq_after, read_y = (seq_before + 4) % 4, 4
    assert seq_before == seq_after and read_y != read_x * 2
    # Two concurrent begins can make an even value while writers are active.
    seq, x, y = 0, 0, 0
    seq += 1  # writer A begins
    seq += 1  # writer B begins without serialization
    x = 1     # A has updated only x
    assert seq % 2 == 0 and y != x * 2
    print('PASS: %d SC schedules; parity, validation, wrap, serialization counterexamples' % len(rows))


if __name__ == '__main__': main()
