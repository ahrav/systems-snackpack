#!/usr/bin/env python3
"""Check checksum, exactly-once coverage, and split completion independently."""
import csv
import io
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ['-std=c11', '-O3', '-Wall', '-Wextra', '-Werror', '-pthread']
MASK = (1 << 64) - 1


def run(command, timeout=60):
    return subprocess.run(list(map(str, command)), check=True, capture_output=True,
                          text=True, timeout=timeout).stdout


def oracle(n, rounds, skew):
    total = 0
    for i in range(n):
        value = i + 0x9e3779b97f4a7c15
        for _ in range(rounds * (skew if i % 19 == 0 else 1)):
            value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & MASK
            value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & MASK
        total = (total + (value ^ (value >> 31))) & MASK
    return total


def build(source, binary):
    run(['cc', *FLAGS, source, '-o', binary])


def validate():
    source = (ROOT / 'work_stealing_bench.c').read_text()
    with tempfile.TemporaryDirectory(prefix='topic087-check-') as tmp:
        tmp = Path(tmp)
        binary = tmp / 'bench'
        build(ROOT / 'work_stealing_bench.c', binary)
        model = run(['python3', ROOT / 'work_stealing_demo.py', '--self-test']).strip()
        self_test = run([binary, '--self-test']).strip()
        cases = 0
        for n in [1, 2, 19, 127, 1024]:
            expected = oracle(n, 3, 5)
            for workers in [1, 2, 4]:
                for grain in [1, 64, 1024]:
                    result = run([binary, '--n', n, '--workers', workers, '--grain', grain,
                                  '--rounds', 3, '--skew', 5, '--reps', 1])
                    rows = list(csv.DictReader(io.StringIO(result)))
                    assert len(rows) == 3
                    assert all(int(row['checksum']) == expected for row in rows)
                    cases += 1

        # Per-index coverage catches omissions and duplicates that aggregate sums can hide.
        coverage = source.replace('static uint64_t range_sum(',
                                  'static atomic_uint visits[1024];\nstatic uint64_t range_sum(')
        coverage = coverage.replace('out += item(i, rounds, skew);',
                                    '{ atomic_fetch_add(&visits[i], 1); out += item(i, rounds, skew); }')
        pos = coverage.rfind('  return 0;')
        coverage = coverage[:pos] + '  for (uint32_t i = 0; i < n; ++i) if (atomic_load(&visits[i]) != 1) abort();\n' + coverage[pos:]
        path = tmp / 'coverage.c'
        path.write_text(coverage)
        build(path, tmp / 'coverage')
        for grain in [1, 7, 64, 1024]:
            run([tmp / 'coverage', '--n', 1024, '--grain', grain, '--workers', 4,
                 '--rounds', 2, '--skew', 3, '--reps', 1, '--mode', 'steal'])

        before = 'atomic_fetch_add(&s->outstanding, 1);\n      if (!push(&s->queues[arg->id], (Task){mid, t.hi})) abort();'
        after = 'if (!push(&s->queues[arg->id], (Task){mid, t.hi})) abort();\n      atomic_fetch_add(&s->outstanding, 1);'
        assert source.count(before) == 1
        split_results = {}
        for name, code in [('fixed', source), ('publish_before_count_mutant', source.replace(before, after))]:
            code = code.replace('static void *steal_worker(void *ptr) {',
                                'static atomic_uint probe_split, probe_done, probe_seen, probe_remaining;\nstatic void *steal_worker(void *ptr) {')
            code = code.replace('if (atomic_load(&s->outstanding) == 0) break;', '''unsigned remaining = atomic_load(&s->outstanding);
      if (atomic_load(&probe_split) && atomic_load(&probe_done)) {
        atomic_store(&probe_remaining, remaining);
        atomic_store(&probe_seen, 1);
      }
      if (remaining == 0) break;''')
            code = code.replace('uint32_t mid = t.lo + (t.hi - t.lo) / 2;',
                                'uint32_t mid = t.lo + (t.hi - t.lo) / 2;\n      atomic_store(&probe_split, 1);')
            code = code.replace('if (!push(&s->queues[arg->id], (Task){mid, t.hi})) abort();',
                                'if (!push(&s->queues[arg->id], (Task){mid, t.hi})) abort();\n      while (!atomic_load(&probe_seen)) sched_yield();')
            code = code.replace('if (!push(&s->queues[arg->id], (Task){t.lo, mid})) abort();',
                                'if (!push(&s->queues[arg->id], (Task){t.lo, mid})) abort();\n      atomic_store(&probe_split, 0);')
            code = code.replace('atomic_fetch_sub(&s->outstanding, 1);',
                                'atomic_fetch_sub(&s->outstanding, 1);\n    atomic_store(&probe_done, 1);')
            pos = code.rfind('  return 0;')
            code = code[:pos] + '  printf("remaining=%u\\n", atomic_load(&probe_remaining));\n' + code[pos:]
            path = tmp / (name + '.c')
            path.write_text(code)
            build(path, tmp / name)
            output = run([tmp / name, '--n', 2, '--workers', 2, '--grain', 1,
                          '--rounds', 1, '--skew', 1, '--reps', 1, '--mode', 'steal'], timeout=10)
            observed = int(output.strip().splitlines()[-1].split('=')[1])
            assert observed == (1 if name == 'fixed' else 0), output
            split_results[name] = observed
        return dict(model=model, native_self_test=self_test, independent_oracle_cases=cases,
                    exactly_once_cases=4, forced_split_remaining=split_results)


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
