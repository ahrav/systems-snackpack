#!/usr/bin/env python3
"""Compare Rust schedules against a closed-form round/rank oracle, not a queue."""
import subprocess
import sys

lines = subprocess.check_output([sys.argv[1]], text=True).splitlines()
assert len(lines) == 864
for line in lines:
    inputs, output = line.split('|')
    a, b, c, budget = map(int, inputs.split())
    expected = []
    for token, size in enumerate([a, b, c]):
        if size:
            rounds = (size + budget - 1) // budget
            for turn in range(rounds + 1):
                n = min(budget, max(0, size - turn * budget))
                expected.append((turn, token, n))
    expected.sort()
    encoded = ','.join('%d:%d' % (token, n) for _, token, n in expected)
    assert output == encoded, (line, encoded)
print('PASS: 864 schedules against independent round/rank oracle')
