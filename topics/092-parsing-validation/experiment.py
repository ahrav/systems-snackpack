#!/usr/bin/env python3
"""Independent oracle, fixed workloads, fresh-process balanced measurements."""
import argparse
import hashlib
import itertools
import json
import os
import platform
import random
import re
import statistics
import subprocess
from pathlib import Path


def oracle(data):
    if re.fullmatch(rb'(?:(?:0|[1-9][0-9]{0,9})\n)*', data) is None:
        return None
    values = [int(field) for field in data.splitlines()]
    return values if all(v <= 0xffffffff for v in values) else None


def verify(binary, cases):
    request = ''.join(data.hex() + '\n' for data in cases)
    result = subprocess.run([str(binary), 'verify'], input=request, text=True, capture_output=True, check=True)
    lines = result.stdout.splitlines()
    if len(lines) != len(cases) * 3:
        raise RuntimeError(f'parser output differs from oracle: {len(lines)} lines for {len(cases)} inputs')
    for index, data in enumerate(cases):
        values = oracle(data)
        expected = 'ERR' if values is None else 'OK' + ''.join(f' {value}' for value in values)
        for arm in range(3):
            if lines[index * 3 + arm] != expected:
                raise RuntimeError(f'parser output differs from oracle: input {index} arm {arm} {data[:40]!r}')
    return len(cases) * 3


def correctness(binary):
    alphabet = [0, 10, 13, 43, 48, 49, 57, 255]
    cases = [bytes(items) for n in range(6) for items in itertools.product(alphabet, repeat=n)]
    seed = b'12\n0\n4294967295\n'
    for index in range(len(seed)):
        for value in range(256):
            cases.append(seed[:index] + bytes([value]) + seed[index + 1:])
    rng = random.Random(92001)
    for _ in range(2000):
        values = [rng.randrange(2**32) for _ in range(rng.randrange(20))]
        data = ''.join(f'{value}\n' for value in values).encode()
        cases.append(data)
        if data:
            index = rng.randrange(len(data))
            cases.append(data[:index] + bytes([rng.randrange(256)]) + data[index + 1:])
    cases.extend([b'4294967296\n', b'99999999999\n', b'000000000000\n', b'1\n2', '١\n'.encode()])
    checks = 0
    for index in range(0, len(cases), 2048):
        checks += verify(binary, cases[index:index + 2048])
    return {'inputs': len(cases), 'parser_comparisons': checks, 'oracle': 'Python bytes regex + arbitrary-precision int; exact vectors'}


def workloads():
    rng = random.Random(92002)
    values = {
        'tiny': [rng.randrange(1000) for _ in range(32)],
        'short': [rng.randrange(10) for _ in range(32768)],
        'long': [rng.randrange(1_000_000_000, 2**32) for _ in range(32768)],
        'mixed': [rng.randrange(10**rng.randrange(1, 10)) for _ in range(32768)],
        'large': [rng.randrange(2**32) for _ in range(262144)],
    }
    data = {name: ''.join(f'{value}\n' for value in items).encode() for name, items in values.items()}
    for name, index in [('invalid_early', 0), ('invalid_late', len(data['mixed']) - 2)]:
        buf = bytearray(data['mixed'])
        buf[index] = ord('x')
        data[name] = bytes(buf)
    return data


def command_output(command):
    run = subprocess.run(command, capture_output=True, text=True)
    return {'command': command, 'returncode': run.returncode, 'stdout': run.stdout.strip(), 'stderr': run.stderr.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('binary', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--verify-only', action='store_true')
    args = ap.parse_args()
    binary = args.binary.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    meta = {'platform': platform.platform(), 'machine': platform.machine(), 'hostname': platform.node(),
            'toolchain': command_output(['rustc', '+1.93.1', '-vV']), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'build': 'cargo build --release; Rust 1.93.1; default target CPU; no RUSTFLAGS',
            'rules': 'six permutation-balanced blocks; win iff all six paired times >5% faster; tie iff all within 5%; otherwise unresolved; descriptive only',
            'timing': 'warm reusable input/output/scratch; includes validation, conversion, output writes; excludes file I/O, initial allocation, checksum and oracle',
            'limits': 'single thread; clock, thermals, system load and SMT sibling uncontrolled; no cold-cache claim',
            'correctness': correctness(binary)}
    if hasattr(os, 'sched_getaffinity'):
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {allowed[0]})
        meta['affinity'] = sorted(os.sched_getaffinity(0))
        meta['cpu'] = command_output(['lscpu'])
    else:
        meta['affinity'] = 'OS scheduled'
        meta['cpu'] = command_output(['sysctl', '-n', 'machdep.cpu.brand_string'])
    data = workloads()
    meta['workloads'] = {name: {'bytes': len(buf), 'sha256': hashlib.sha256(buf).hexdigest(), 'valid': oracle(buf) is not None} for name, buf in data.items()}
    meta['workload_parser_comparisons'] = verify(binary, list(data.values()))
    (args.output / 'metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
    print(json.dumps(meta['correctness']), flush=True)
    if args.verify_only:
        return
    paths = {}
    for name, buf in data.items():
        paths[name] = args.output / (name + '.input')
        paths[name].write_bytes(buf)
    algorithms = ['fused', 'split', 'indexed']
    raw = []
    def sample(name, algorithm, block):
        iters = 200000 if name == 'invalid_early' else max(4, min(100000, 16 * 1024 * 1024 // len(data[name])))
        run = subprocess.run([str(binary), 'bench', algorithm, str(paths[name]), str(iters)], capture_output=True, text=True, check=True)
        arm, size, repetitions, ns, valid, count, checksum = run.stdout.strip().split(',')
        expected = oracle(data[name])
        # Explicit checks run under -O, which strips assert statements.
        if arm != algorithm or int(size) != len(data[name]) or int(repetitions) != iters:
            raise RuntimeError(f'benchmark output differs from oracle: {name} {algorithm} header {run.stdout.strip()!r}')
        if (valid == 'true') != (expected is not None) or int(count) != (len(expected) if expected is not None else 0) \
                or int(checksum) != (sum(expected) if expected is not None else 0):
            raise RuntimeError(f'benchmark output differs from oracle: {name} {algorithm} {run.stdout.strip()!r}')
        return {'workload': name, 'algorithm': arm, 'block': block, 'bytes': int(size), 'iterations': iters,
                'total_ns': int(ns), 'ns_per_batch': int(ns) / iters, 'accepted': valid == 'true', 'count': int(count), 'checksum': int(checksum)}
    for name in data:
        for algorithm in algorithms:
            raw.append(sample(name, algorithm, -1))
    for block, order in enumerate(itertools.permutations(algorithms)):
        names = list(data)
        names = names[block % len(names):] + names[:block % len(names)]
        for name in names:
            for algorithm in order:
                raw.append(sample(name, algorithm, block))
        print(f'block {block + 1}/6 complete', flush=True)
    (args.output / 'samples.json').write_text(json.dumps(raw, indent=2) + '\n')
    summary = []
    pairs = []
    for name, buf in data.items():
        times = {}
        for algorithm in algorithms:
            values = [row['ns_per_batch'] for row in raw if row['workload'] == name and row['algorithm'] == algorithm and row['block'] >= 0]
            times[algorithm] = values
            med = statistics.median(values)
            summary.append({'workload': name, 'algorithm': algorithm, 'median_ns': med, 'min_ns': min(values), 'max_ns': max(values),
                            'GB_per_s': len(buf) / med if oracle(buf) is not None else None})
        for left, right in itertools.combinations(algorithms, 2):
            ratio = [a / b for a, b in zip(times[left], times[right])]
            decision = left if all(r < 1 / 1.05 for r in ratio) else right if all(r > 1.05 for r in ratio) else 'tie' if all(1 / 1.05 <= r <= 1.05 for r in ratio) else 'unresolved'
            pairs.append({'workload': name, 'left': left, 'right': right, 'decision': decision, 'ratios': ratio})
    (args.output / 'summary.json').write_text(json.dumps({'summary': summary, 'pairs': pairs}, indent=2) + '\n')
    for path in paths.values():
        path.unlink()  # Deterministic inputs are regenerated by workloads(); hashes are retained.
    print(f'{len(raw) - 21} measured processes, 21 warmups; all outputs verified', flush=True)


if __name__ == '__main__':
    main()
