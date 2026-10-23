"""Exact rational sums and rational per-operation rounding, independent of Rust."""
from fractions import Fraction as Q
import itertools
import json
import math
import random
import struct
import subprocess
import sys


def bits(x):
    return struct.pack('>d', x).hex()


def value(s):
    return struct.unpack('>d', bytes.fromhex(s))[0]


def rounded_add(a, b):
    return float(Q(a) + Q(b))


def order_reference(xs):
    s = 0.0
    for x in xs:
        s = rounded_add(s, x)
    return s


def lane_reference(xs):
    s = [order_reference(xs[i::4]) for i in range(4)]
    return rounded_add(rounded_add(s[0], s[1]), rounded_add(s[2], s[3]))


def verify(binary):
    cases = []
    # Integer numerators provide an exact oracle for the benchmark input domain.
    for n in [0, 1, 2, 3, 4, 5, 7, 8, 15, 16, 17, 31, 32, 33, 255, 256, 257, 1023]:
        for seed in range(12):
            rng = random.Random(seed)
            xs = [rng.randrange(-1024, 1024) / 1024 for _ in range(n)]
            cases.append(('sum', xs, True))
    m = float(2**54)
    # Every distinct permutation has exact sum 2; only compensation must recover it.
    for xs in sorted(set(itertools.permutations([m, 1.0, -m, 1.0]))):
        cases.append(('sum', xs, False))
    for count in [1, 2, 3, 7, 16, 127, 1024]:
        cases.append(('sum', [m, 1.0, -m, 1.0] * count, False))
    # Independently verify both rounding contracts for FMA across several exponents.
    for exponent in range(27, 53):
        x = 2.0 ** -exponent
        cases.append(('fma', [1.0 + x, 1.0 - x, -1.0], False))
    payload = ''.join(op + ' ' + ' '.join(map(bits, xs)) + '\n' for op, xs, _ in cases)
    p = subprocess.run([binary, 'probe'], input=payload, text=True, capture_output=True, check=True)
    lines = p.stdout.splitlines()
    assert len(lines) == len(cases)
    mismatches = {'ordered': 0, 'lanes4': 0}
    checks = 0
    for (op, xs, exact_domain), line in zip(cases, lines):
        got = list(map(value, line.split()))
        if op == 'sum':
            exact = float(sum(map(Q, xs), Q(0)))
            expected = [order_reference(xs), lane_reference(xs), exact]
            assert list(map(bits, got)) == list(map(bits, expected)), (op, xs, got, expected)
            if exact_domain:
                assert got == [exact] * 3
            else:
                for i, name in enumerate(mismatches):
                    mismatches[name] += got[i] != exact
            checks += 3
        else:
            a, b, c = map(Q, xs)
            expected = [float(Q(float(a*b)) + c), float(a*b+c)]
            assert list(map(bits, got)) == list(map(bits, expected)), (got, expected)
            checks += 2
    report = {'cases': len(cases), 'value_checks': checks,
              'accuracy_counterexamples': mismatches,
              'status': 'pass',
              'limits': 'Finite dyadic cases and cancellation fixtures; no general compensated correct-rounding claim.'}
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    verify(sys.argv[1])
