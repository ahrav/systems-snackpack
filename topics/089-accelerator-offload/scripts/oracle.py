"""Independent tick simulator and arbitrary-precision transform oracle."""
import csv
import io
import itertools
import json
import subprocess
import sys


def tick_total(jobs, slots, durations):
    if jobs == 0:
        return 0
    waiting = [0] * jobs
    active = [None] * 3
    owner = [None] * slots
    completed = 0
    next_input = 0
    # Advance physical ticks and process zero-duration chains to a fixed point.
    for tick in itertools.count():
        changed = True
        while changed:
            changed = False
            for stage, work in enumerate(active):
                if work is not None and work[1] == tick:
                    job = work[0]
                    active[stage] = None
                    waiting[job] = stage + 1
                    if stage == 2:
                        completed += 1
                        owner[job % slots] = None
                    changed = True
            for stage in range(3):
                if active[stage] is not None:
                    continue
                if stage == 0:
                    candidates = [next_input] if next_input < jobs else []
                else:
                    candidates = [j for j in range(jobs) if waiting[j] == stage]
                if not candidates:
                    continue
                job = candidates[0]
                if stage == 0:
                    if owner[job % slots] is not None:
                        continue
                    owner[job % slots] = job
                    next_input += 1
                waiting[job] = -1
                active[stage] = (job, tick + durations[stage])
                changed = True
        if completed == jobs:
            return tick
        assert tick <= jobs * sum(durations)


def expected_values(n, rounds):
    values = [(i * 2654435761) % (2**32) for i in range(n)]
    for r in range(rounds):
        values = [((v ^ (v // 8192)) * 1664525 + 1013904223) % (2**32)
                  for v in values]
    return values


def check(binary):
    rows = csv.DictReader(io.StringIO(subprocess.check_output([binary, 'model-grid'], text=True)))
    model_cases = 0
    for row in rows:
        jobs, slots, h, k, d, total = (int(row[key]) for key in ('jobs','slots','h','k','d','total'))
        observed = tick_total(jobs, slots, (h, k, d))
        assert total == observed, (row, observed)
        model_cases += 1
    transform_cases = 0
    for mode, n, rounds in itertools.product(('element','round'), (0,1,2,7,257), (0,1,2,31,32)):
        actual = list(map(int, subprocess.check_output([binary, 'values', mode, str(n), str(rounds)], text=True).split()))
        assert actual == expected_values(n, rounds), (mode, n, rounds)
        transform_cases += 1
    assert model_cases == 4500
    return {'model_cases':model_cases, 'transform_cases':transform_cases, 'status':'pass'}

if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1]), indent=2))
