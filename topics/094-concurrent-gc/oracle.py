"""Independent Floyd-Warshall reachability oracle; no marking worklist."""
import itertools
import subprocess
import sys


def reachable(edges):
    matrix = [[i == j or edges[i] == j for j in range(3)] for i in range(3)]
    for k in range(3):
        for i in range(3):
            for j in range(3):
                matrix[i][j] |= matrix[i][k] and matrix[k][j]
    return sum(1 << j for j in range(3) if matrix[0][j] or matrix[1][j])


lines, expected = [], []
for edges in itertools.product(range(-1, 3), repeat=3):
    initial = reachable(edges)
    # References come from the initial live set; no resurrection/allocation.
    allowed = [-1] + [i for i in range(3) if initial & (1 << i)]
    for owner1, owner2, new1, new2 in itertools.product(range(3), range(3), allowed, allowed):
        final = list(edges)
        # Sequential stores matter when both owners are equal.
        final[owner1] = new1
        final[owner2] = new2
        live = reachable(final)
        for before1, before2 in itertools.product(range(4), repeat=2):
            for mode in ('stw', 'insertion', 'satb'):
                lines.append(' '.join(map(str, [mode, *edges, before1, owner1, new1, before2, owner2, new2])))
                expected.append((mode, initial, live))
# stderr is inherited so a probe panic stays visible. Checks raise so they hold under python -O.
result = subprocess.run([sys.argv[1], 'batch'], input='\n'.join(lines)+'\n', text=True, stdout=subprocess.PIPE, check=True)
answers = result.stdout.splitlines()
if len(answers) != len(expected):
    raise SystemExit(f'{len(answers)} answers for {len(expected)} cases')
for line, answer, (mode, initial, live) in zip(lines, answers, expected):
    mask = int(answer)
    if mask & live != live:
        raise SystemExit(f'lost live object: {line} mask={mask} live={live}')
    if mode == 'stw' and mask != live:
        raise SystemExit(f'stw retention differs from final reachability: {line} mask={mask} live={live}')
    if mode == 'satb' and mask & initial != initial:
        raise SystemExit(f'satb lost initial object: {line} mask={mask} initial={initial}')
print(f'{len(expected)} oracle comparisons passed; 64 initial graphs, two stores, 16 scan schedules')
